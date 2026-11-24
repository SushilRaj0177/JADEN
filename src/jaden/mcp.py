"""JADEN as an MCP server: AI assistants call the address functions as tools.

    jaden mcp

Speaks the Model Context Protocol over stdin/stdout (newline-delimited JSON-RPC 2.0), using only the
standard library, so a desktop assistant or an agent framework can check an address instead of
guessing it. Register it in the client's MCP settings, for example:

    {"mcpServers": {"jaden": {"command": "jaden", "args": ["mcp"]}}}

Every tool runs offline on the bundled data.
"""

import dataclasses
import json
import sys
from typing import Any, Callable, Dict, List, Optional, TextIO, Tuple

from .core.text import load_json

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def _str(description: str) -> Dict[str, Any]:
    return {"type": "string", "description": description}


def _schema(required: List[str], **props: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


_ADDRESS = _str("A Japanese address as written, e.g. '東京都港区芝公園4-2-8'")


def _normalize(args: Dict[str, Any]) -> Any:
    from .server import address_record
    return address_record(args["address"], strict=bool(args.get("strict")), fix=bool(args.get("fix")))


def _validate(args: Dict[str, Any]) -> Any:
    from .engine import get_engine
    return get_engine().validate(args["address"], strict=bool(args.get("strict"))).to_dict()


def _resolve(args: Dict[str, Any]) -> Any:
    from .resolve import resolve
    result = dataclasses.asdict(resolve(args["address"], args.get("name") or ""))
    result["candidates"] = result["candidates"][:10]
    return result


def _extract(args: Dict[str, Any]) -> Any:
    from .extract import extract_addresses
    from .server import MAX_EXTRACT_CHARS
    text = args["text"]
    if len(text) > MAX_EXTRACT_CHARS:
        raise ValueError(f"'text' is limited to {MAX_EXTRACT_CHARS:,} characters")
    return {"addresses": [x.to_dict() for x in extract_addresses(text)]}


def _postal(args: Dict[str, Any]) -> Any:
    from .lookup import lookup_postal
    found = lookup_postal(args["postal_code"])
    return {"postal_code": args["postal_code"], "addresses": [p.to_dict() for p in found]}


def _compare(args: Dict[str, Any]) -> Any:
    from .matching import compare
    return compare(args["a"], args["b"]).to_dict()


def _suggest(args: Dict[str, Any]) -> Any:
    from .lookup import suggest
    limit = args.get("limit", 10)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise ValueError("'limit' must be an integer from 1 to 50")
    return {"suggestions": [s.to_dict() for s in suggest(args["text"], limit=limit)]}


def _fields(args: Dict[str, Any]) -> Any:
    from .fields import FIELD_NAMES, check_fields
    for key in FIELD_NAMES:
        if not isinstance(args.get(key, ""), str):
            raise ValueError(f"'{key}' must be a string")
    if not any(args.get(k) for k in FIELD_NAMES):
        raise ValueError(f"give at least one of: {', '.join(FIELD_NAMES)}")
    return check_fields(**{k: args.get(k, "") for k in FIELD_NAMES}, strict=bool(args.get("strict"))).to_dict()


_FLAG_STRICT = {"type": "boolean", "description": "Refuse towns and 丁目 that cannot be checked against the registries"}

TOOLS: Dict[str, Tuple[str, Dict[str, Any], Callable[[Dict[str, Any]], Any]]] = {
    "normalize_address": (
        "Normalize, verify and format one Japanese address. Returns the status (ACCEPTED, AMBIGUOUS, "
        "MALFORMED, UNSUPPORTED), a reason code, the canonical form, the English (romaji) form, the "
        "kana reading, the postal code, coordinates and every component. Use it before relying on an address.",
        _schema(["address"], address=_ADDRESS, strict=_FLAG_STRICT,
                fix={"type": "boolean", "description": "Correct a misspelt town when one spelling clearly fits"}),
        _normalize),
    "validate_address": (
        "Check whether a Japanese address exists: status, reason code, a message in English and Japanese, "
        "and the candidates when it is ambiguous.",
        _schema(["address"], address=_ADDRESS, strict=_FLAG_STRICT), _validate),
    "resolve_address": (
        "For an address that leaves out its municipality (e.g. '錦町1番2号'), rank the candidate "
        "municipalities with calibrated probabilities. 'answered' is true (and lg_code set) only when reliable; "
        "otherwise ask the user which candidate is meant.",
        _schema(["address"], address=_ADDRESS,
                name=_str("Optional company or facility name at the address (extra evidence)")), _resolve),
    "check_address_fields": (
        "Check an address entered in separate form fields (postal code, prefecture, city, line1 = town and "
        "numbers, line2 = building and room). Reports each field that disagrees (with the right value) "
        "and returns the corrected fields.",
        _schema([], postal_code=_str("Postal code"), prefecture=_str("Prefecture"), city=_str("Municipality"),
                line1=_str("Town and block numbers"), line2=_str("Building, floor, room"), strict=_FLAG_STRICT),
        _fields),
    "extract_addresses": (
        "Find every Japanese address inside a text (an email, a web page, a document).",
        _schema(["text"], text=_str("The text to search")), _extract),
    "lookup_postal_code": (
        "List the addresses a Japanese postal code covers.",
        _schema(["postal_code"], postal_code=_str("Seven-digit postal code, e.g. '105-0011'")), _postal),
    "compare_addresses": (
        "Decide whether two Japanese addresses are the same place, with the reason.",
        _schema(["a", "b"], a=_str("First address"), b=_str("Second address")), _compare),
    "suggest_addresses": (
        "Autocomplete a partly typed Japanese address or postal code (kanji or kana).",
        _schema(["text"], text=_str("What has been typed so far, e.g. '東京都港区しば'"),
                limit={"type": "integer", "minimum": 1, "maximum": 50, "description": "At most this many (default 10)"}),
        _suggest),
}


def _tool_list() -> List[Dict[str, Any]]:
    return [{"name": name, "description": desc, "inputSchema": schema} for name, (desc, schema, _) in TOOLS.items()]


def _call(params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    if not isinstance(name, str) or name not in TOOLS:
        raise _RpcError(-32602, f"unknown tool: {name!r}")
    _desc, schema, func = TOOLS[name]
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise _RpcError(-32602, "'arguments' must be an object")
    try:
        for key in schema["required"]:
            if key not in args:
                raise ValueError(f"'{key}' is required")
        unknown = set(args) - set(schema["properties"])
        if unknown:
            raise ValueError(f"unknown argument(s): {', '.join(sorted(unknown))}")
        for key, value in args.items():      # every argument has the type its schema declares
            kind = schema["properties"][key].get("type")
            ok = {"string": isinstance(value, str), "boolean": isinstance(value, bool),
                  "integer": isinstance(value, int) and not isinstance(value, bool)}.get(kind, True)
            if not ok:
                raise ValueError(f"'{key}' must be a {kind}")
        result = func(args)
    except ValueError as exc:   # a tool error is reported to the model, not as a protocol error
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    text = json.dumps(result, ensure_ascii=False)
    return {"content": [{"type": "text", "text": text}], "structuredContent": result, "isError": False}


class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def handle(message: Any) -> Optional[Dict[str, Any]]:
    """One JSON-RPC message in, the response out (None for notifications)."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None,
                "error": {"code": -32600, "message": "invalid request"}}
    method, params, msg_id = message["method"], message.get("params") or {}, message.get("id")
    if "id" not in message:          # notification (initialized, cancelled, ...): no reply
        return None
    if msg_id is not None and (isinstance(msg_id, bool) or not isinstance(msg_id, (str, int))):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request: bad id"}}
    try:
        if not isinstance(params, dict):
            raise _RpcError(-32602, "'params' must be an object")
        if method == "initialize":
            from . import __version__
            asked = params.get("protocolVersion")
            result: Dict[str, Any] = {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "jaden", "version": __version__},
                "instructions": "Offline Japanese address tools. Check an address with normalize_address "
                                "before using it; never invent a municipality: use resolve_address and ask "
                                "when its answer is empty."}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": _tool_list()}
        elif method == "tools/call":
            result = _call(params)
        else:
            raise _RpcError(-32601, f"method not found: {method}")
    except _RpcError as exc:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:  # noqa: BLE001  (a bug must not kill the session)
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": f"internal error: {exc}"}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def serve_stdio(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    """Reads one JSON-RPC message per line until stdin closes. Replies are pure ASCII JSON, so a console
    code page (Windows) cannot garble them; input is read as UTF-8."""
    reconfigure = getattr(stdin, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = load_json(line)
        except (ValueError, RecursionError):
            reply: Optional[Dict[str, Any]] = {"jsonrpc": "2.0", "id": None,
                                               "error": {"code": -32700, "message": "parse error"}}
        else:
            if isinstance(message, list) and not message:
                reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request: empty batch"}}
                stdout.write(json.dumps(reply) + "\n")
                stdout.flush()
                continue
            if isinstance(message, list):   # batches (older protocol versions)
                replies = [r for r in (handle(m) for m in message) if r is not None]
                if replies:
                    stdout.write(json.dumps(replies) + "\n")
                    stdout.flush()
                continue
            reply = handle(message)
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()
    return 0
