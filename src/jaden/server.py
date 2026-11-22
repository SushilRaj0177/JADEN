"""JADEN: HTTP API server.

    jaden serve --port 8000

A small JSON API over everything JADEN does, using only the standard library,
so applications in any language can use it without embedding Python. Every
endpoint accepts GET with query parameters or POST with a JSON body.

    GET  /v1/normalize?q=港区芝公園4-2-8        resolve, verify, format (one record)
    GET  /v1/validate?q=...&strict=1          status only
    GET  /v1/suggest?q=東京都港区芝&limit=10     autocomplete
    GET  /v1/postal/105-0011                  postal code -> addresses
    GET  /v1/reverse?lat=35.6586&lon=139.7454 coordinate -> nearest town
    GET  /v1/compare?a=...&b=...              are two addresses the same place?
    GET  /v1/resolve?q=錦町1番2号&name=...       candidate municipalities with calibrated probabilities
    POST /v1/extract   {"text": "..."}        addresses inside a text
    POST /v1/batch     {"addresses": [...]}   many addresses at once
    GET  /v1                                  endpoint list and data versions
    GET  /health
    GET  /                                    interactive demo page

Nothing leaves the machine: all lookups use the bundled data. The server binds
to 127.0.0.1 unless told otherwise. Errors are JSON ({"error": {"code", "message"}});
POST bodies must be JSON sent as application/json (so a web page cannot post to a
local server without the browser asking first).
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlsplit

MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_EXTRACT_CHARS = 100_000      # extraction time grows with the text; more than this is not one document
SOCKET_TIMEOUT = 30              # seconds a client may take to send its request
DEFAULT_MAX_BATCH = 1000
_WEB_DIR = Path(__file__).parent / "web"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _flag(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on") if value is not None else False


def _required(params: Dict[str, Any], name: str) -> str:
    value = params.get(name)
    if value is not None and not isinstance(value, str):
        raise ApiError(400, "bad_parameter", f"parameter '{name}' must be a string")
    if value is None or not value.strip():
        raise ApiError(400, "missing_parameter", f"parameter '{name}' is required")
    return value


def _optional_text(params: Dict[str, Any], name: str) -> str:
    value = params.get(name)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ApiError(400, "bad_parameter", f"parameter '{name}' must be a string")
    return value


def _int(params: Dict[str, Any], name: str, default: int, low: int, high: int) -> int:
    raw = params.get(name)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise ApiError(400, "bad_parameter", f"parameter '{name}' must be an integer")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(400, "bad_parameter", f"parameter '{name}' must be an integer") from None
    if not low <= value <= high:
        raise ApiError(400, "bad_parameter", f"parameter '{name}' must be between {low} and {high}")
    return value


def address_record(address: str, strict: bool = False, fix: bool = False) -> Dict[str, Any]:
    """One address resolved and validated, as a single JSON-ready record."""
    from .engine import get_engine
    engine = get_engine()
    res = engine.normalize(address, autocorrect=fix)
    val = engine.validate(address, strict=strict, autocorrect=fix, normalized=res)
    data = res.to_dict()
    data.pop("latency_microseconds", None)
    usable = res.confidence_score > 0
    return {
        "input": address,
        "status": val.status,
        "valid": val.valid,
        "message": val.message,
        "warnings": [w for w in val.warnings if w not in val.message],
        "canonical": res.canonical if usable else None,
        "hyphenated": data.get("hyphenated"),
        "english": res.romaji,
        "kana": res.kana,
        "lines": list(res.lines()) if usable else [],
        "lg_code": val.lg_code,
        "postal_code": res.components.postal_code,
        "precision": val.precision,
        "verification_level": val.verification_level,
        "location": ({"latitude": res.latitude, "longitude": res.longitude, "level": res.location_level}
                     if res.latitude is not None else None),
        "candidates": list(val.ambiguous_candidates),
        "suggestions": list(res.suggestions),
        "components": data["components"] if usable else None,
    }


class JadenApi:
    """The endpoints, independent of the HTTP plumbing (also handy for tests)."""

    def __init__(self, max_batch: int = DEFAULT_MAX_BATCH) -> None:
        self.max_batch = max_batch
        self.started = time.time()
        self.routes: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "/v1/normalize": self.normalize,
            "/v1/validate": self.validate,
            "/v1/geocode": self.geocode,
            "/v1/suggest": self.suggest,
            "/v1/postal": self.postal,
            "/v1/reverse": self.reverse,
            "/v1/compare": self.compare,
            "/v1/resolve": self.resolve,
            "/v1/extract": self.extract,
            "/v1/batch": self.batch,
            "/v1": self.index,
            "/health": self.health,
        }

    def warm_up(self) -> None:
        """Loads the data once so the first request is as fast as the rest."""
        from .data.gazetteer import get_gazetteer
        from .lookup import lookup_postal
        from .lookup import suggest
        from .resolve import resolve
        address_record("東京都港区芝公園4-2-8")
        lookup_postal("105-0011")
        get_gazetteer().nearest_towns(35.6586, 139.7454)
        suggest("しば")          # builds the prefix indexes
        resolve("錦町1番2号")    # loads the resolver's prior

    # ----------------------------------------------------------- endpoints
    def health(self, params: Dict[str, Any]) -> Any:
        return {"status": "ok", "uptime_seconds": round(time.time() - self.started, 1)}

    def index(self, params: Dict[str, Any]) -> Any:
        from . import __version__
        from .data.gazetteer import get_gazetteer
        prov = get_gazetteer().provenance()
        return {
            "name": "JADEN", "version": __version__,
            "endpoints": sorted(k for k in self.routes if k.startswith("/v1/")),
            "data": {"built": prov.get("built"),
                     "towns": prov.get("towns", {}).get("dataset"),
                     "town_records": prov.get("towns", {}).get("records"),
                     "postal_records": prov.get("postal", {}).get("records"),
                     "attribution": prov.get("towns", {}).get("attribution")},
            "limits": {"max_batch": self.max_batch, "max_body_bytes": MAX_BODY_BYTES},
        }

    def normalize(self, params: Dict[str, Any]) -> Any:
        return address_record(_required(params, "q"), strict=_flag(params.get("strict")), fix=_flag(params.get("fix")))

    def validate(self, params: Dict[str, Any]) -> Any:
        from .engine import get_engine
        val = get_engine().validate(_required(params, "q"), strict=_flag(params.get("strict")),
                                    autocorrect=_flag(params.get("fix")))
        return val.to_dict()

    def geocode(self, params: Dict[str, Any]) -> Any:
        from .geocoding import geocode
        return geocode(_required(params, "q"), provider="offline").to_dict()

    def suggest(self, params: Dict[str, Any]) -> Any:
        from .lookup import suggest
        q = _optional_text(params, "q")
        found = suggest(q, limit=_int(params, "limit", 10, 1, 50))
        return {"query": q, "suggestions": [s.to_dict() for s in found]}

    def postal(self, params: Dict[str, Any]) -> Any:
        from .lookup import lookup_postal
        code = _required(params, "code")
        if "/" in code:
            raise ApiError(404, "not_found", f"no such endpoint: /v1/postal/{code}")
        found = lookup_postal(code)
        if not found:
            raise ApiError(404, "not_found", f"no address for postal code '{code}'")
        return {"postal_code": found[0].postal_code, "addresses": [p.to_dict() for p in found]}

    def reverse(self, params: Dict[str, Any]) -> Any:
        from .lookup import reverse_geocode
        try:
            lat, lon = float(_required(params, "lat")), float(_required(params, "lon"))
            found = reverse_geocode(lat, lon, limit=_int(params, "limit", 1, 1, 20))
        except ValueError as exc:
            raise ApiError(400, "bad_parameter", str(exc) or "lat and lon must be numbers") from None
        return {"query": {"latitude": lat, "longitude": lon}, "results": [r.to_dict() for r in found]}

    def compare(self, params: Dict[str, Any]) -> Any:
        from .matching import compare, match_key
        a, b = _required(params, "a"), _required(params, "b")
        result = compare(a, b).to_dict()
        result["key_a"], result["key_b"] = match_key(a), match_key(b)
        return result

    def extract(self, params: Dict[str, Any]) -> Any:
        from .extract import extract_addresses
        text = _required(params, "text")
        if len(text) > MAX_EXTRACT_CHARS:
            raise ApiError(413, "too_large", f"'text' is limited to {MAX_EXTRACT_CHARS:,} characters per request")
        return {"addresses": [x.to_dict() for x in extract_addresses(text)]}

    def resolve(self, params: Dict[str, Any]) -> Any:
        import dataclasses
        from .resolve import resolve
        result = dataclasses.asdict(resolve(_required(params, "q"), _optional_text(params, "name")))
        result["candidates"] = result["candidates"][:_int(params, "limit", 10, 1, 60)]
        return result

    def batch(self, params: Dict[str, Any]) -> Any:
        addresses = params.get("addresses")
        if not isinstance(addresses, list) or not all(isinstance(a, str) for a in addresses):
            raise ApiError(400, "bad_parameter", "'addresses' must be a JSON array of strings")
        if len(addresses) > self.max_batch:
            raise ApiError(413, "too_many", f"at most {self.max_batch} addresses per request")
        strict, fix = _flag(params.get("strict")), _flag(params.get("fix"))
        results = [address_record(a, strict=strict, fix=fix) for a in addresses]
        summary: Dict[str, int] = {}
        for r in results:
            summary[r["status"]] = summary.get(r["status"], 0) + 1
        return {"count": len(results), "summary": summary, "results": results}

    # ------------------------------------------------------------ dispatch
    def handle(self, path: str, params: Dict[str, Any]) -> Any:
        path = path.rstrip("/") or "/"
        if path.startswith("/v1/postal/"):
            params = {**params, "code": unquote(path[len("/v1/postal/"):])}
            path = "/v1/postal"
        handler = self.routes.get(path)
        if handler is None:
            raise ApiError(404, "not_found", f"no such endpoint: {path}")
        return handler(params)


def _make_handler(api: JadenApi, cors: Optional[str], quiet: bool) -> type:
    class Handler(BaseHTTPRequestHandler):
        server_version = "JADEN"
        protocol_version = "HTTP/1.1"
        timeout = SOCKET_TIMEOUT   # a client that stops sending does not hold a thread for ever

        def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None) -> None:
            # Errors raised by the HTTP layer itself (bad request line, URI too long, unknown method) as JSON too
            self.close_connection = True
            text = message or self.responses.get(code, ("error",))[0]
            try:
                self._json(code, {"error": {"code": f"http_{code}", "message": text}})
            except OSError:
                pass

        def handle_one_request(self) -> None:
            try:
                super().handle_one_request()
            except (ConnectionResetError, BrokenPipeError, TimeoutError):
                # The client went away: nothing to answer, nothing to log as an error
                self.close_connection = True

        def log_message(self, fmt: str, *args: Any) -> None:
            if not quiet:
                sys.stderr.write(f"{self.address_string()} {fmt % args}\n")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            if cors:
                self.send_header("Access-Control-Allow-Origin", cors)
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _error(self, exc: ApiError) -> None:
            self._json(exc.status, {"error": {"code": exc.code, "message": exc.message}})

        def _dispatch(self, params: Dict[str, Any]) -> None:
            split = urlsplit(self.path)
            query = {k: v[-1] for k, v in parse_qs(split.query, keep_blank_values=True).items()}
            try:
                self._json(200, api.handle(split.path, {**query, **params}))
            except ApiError as exc:
                self._error(exc)
            except Exception as exc:  # an unexpected failure must not take the server down
                sys.stderr.write(f"error on {split.path}: {exc!r}\n")
                self._error(ApiError(500, "internal_error", "internal error"))

        def do_OPTIONS(self) -> None:
            self._send(204, b"", "text/plain")

        def do_HEAD(self) -> None:
            self.do_GET()

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
                return
            if path in ("/", "/index.html"):
                page = _WEB_DIR / "index.html"
                if page.exists():
                    self._send(200, page.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._error(ApiError(404, "not_found", "the demo page is not installed"))
                return
            self._dispatch({})

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0:
                self._error(ApiError(400, "bad_request", "invalid Content-Length"))
                return
            if length > MAX_BODY_BYTES:
                self.close_connection = True
                self._error(ApiError(413, "too_large", f"request body is limited to {MAX_BODY_BYTES} bytes"))
                return
            content_type = (self.headers.get("Content-Type") or "").lower()
            if length and "json" not in content_type:
                self.close_connection = True
                self._error(ApiError(415, "unsupported_media_type", "send the body as application/json"))
                return
            raw = self.rfile.read(length) if length else b""
            if len(raw) < length:
                self.close_connection = True
                self._error(ApiError(400, "bad_request", "the body is shorter than its Content-Length"))
                return
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._error(ApiError(400, "bad_json", "the request body must be UTF-8 JSON"))
                return
            if not isinstance(body, dict):
                self._error(ApiError(400, "bad_json", "the request body must be a JSON object"))
                return
            self._dispatch(body)

    return Handler


def create_server(host: str = "127.0.0.1", port: int = 8000, cors: Optional[str] = None, quiet: bool = False,
                  max_batch: int = DEFAULT_MAX_BATCH, warm_up: bool = True) -> ThreadingHTTPServer:
    """Builds the server without starting it (``port=0`` picks a free port)."""
    api = JadenApi(max_batch=max_batch)
    if warm_up:
        api.warm_up()
    server = ThreadingHTTPServer((host, port), _make_handler(api, cors, quiet))
    server.daemon_threads = True
    return server


def serve(host: str = "127.0.0.1", port: int = 8000, cors: Optional[str] = None, quiet: bool = False,
          max_batch: int = DEFAULT_MAX_BATCH) -> int:
    """Runs the API server until interrupted."""
    sys.stderr.write("Loading address data...\n")
    server = create_server(host, port, cors=cors, quiet=quiet, max_batch=max_batch)
    bound_host, bound_port = str(server.server_address[0]), server.server_address[1]
    sys.stderr.write(f"JADEN API listening on http://{bound_host}:{bound_port}  (demo page at /, endpoints at /v1)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nStopping.\n")
    finally:
        server.server_close()
    return 0


def endpoint_list() -> List[Tuple[str, str]]:
    """(endpoint, description) pairs, for documentation."""
    return [
        ("/v1/normalize?q=", "resolve, verify and format one address"),
        ("/v1/validate?q=", "validation status only"),
        ("/v1/geocode?q=", "offline coordinates"),
        ("/v1/suggest?q=&limit=", "autocomplete"),
        ("/v1/postal/<code>", "postal code to addresses"),
        ("/v1/reverse?lat=&lon=", "coordinate to nearest town"),
        ("/v1/compare?a=&b=", "are two addresses the same place"),
        ("/v1/resolve?q=&name=", "candidate municipalities with calibrated probabilities"),
        ("/v1/extract", "addresses inside a text (POST {\"text\"})"),
        ("/v1/batch", "many addresses (POST {\"addresses\": [...]})"),
    ]
