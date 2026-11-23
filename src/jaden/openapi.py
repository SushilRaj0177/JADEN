"""OpenAPI 3.1 description of the HTTP API (served at /v1/openapi.json).

Import it into Postman, Swagger UI or a client generator to call `jaden serve` from any language.
"""

from typing import Any, Dict, List

from .models.validation import REASONS


def _q(name: str, description: str, required: bool = False, kind: str = "string",
       example: Any = None) -> Dict[str, Any]:
    param: Dict[str, Any] = {"name": name, "in": "query", "required": required, "description": description,
                             "schema": {"type": kind}}
    if example is not None:
        param["example"] = example
    return param


_STRICT = _q("strict", "1 = refuse towns and 丁目 that cannot be checked against the registries", kind="boolean")
_FIX = _q("fix", "1 = correct a misspelt town when one spelling clearly fits", kind="boolean")
_ADDRESS = _q("q", "the address, as written", required=True, example="東京都港区芝公園4-2-8")

_STATUS = {"type": "string", "enum": ["ACCEPTED", "AMBIGUOUS", "MALFORMED", "UNSUPPORTED"]}
_REASON = {"type": "string", "enum": sorted(REASONS),
           "description": "Stable reason code; each belongs to one status: "
                          + ", ".join(f"{k} ({v})" for k, v in REASONS.items())}

_SCHEMAS: Dict[str, Any] = {
    "Error": {"type": "object", "properties": {"error": {"type": "object", "properties": {
        "code": {"type": "string"}, "message": {"type": "string"}}}}},
    "Validation": {"type": "object", "properties": {
        "raw_input": {"type": "string"}, "status": _STATUS, "valid": {"type": "boolean"}, "reason": _REASON,
        "message": {"type": "string"}, "message_ja": {"type": "string"},
        "confidence_score": {"type": "number"}, "lg_code": {"type": ["string", "null"]},
        "is_ambiguous": {"type": "boolean"}, "ambiguous_candidates": {"type": "array", "items": {"type": "string"}},
        "verification_level": {"type": "string"}, "precision": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}}}},
    "Address": {"type": "object", "properties": {
        "input": {"type": "string"}, "status": _STATUS, "valid": {"type": "boolean"}, "reason": _REASON,
        "message": {"type": "string"}, "message_ja": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "canonical": {"type": ["string", "null"], "example": "東京都港区芝公園4丁目2番8号"},
        "hyphenated": {"type": ["string", "null"]}, "english": {"type": ["string", "null"]},
        "kana": {"type": ["string", "null"]}, "lines": {"type": "array", "items": {"type": "string"}},
        "lg_code": {"type": ["string", "null"]}, "postal_code": {"type": ["string", "null"]},
        "precision": {"type": "string"}, "verification_level": {"type": "string"},
        "location": {"type": ["object", "null"], "properties": {
            "latitude": {"type": "number"}, "longitude": {"type": "number"}, "level": {"type": "string"}}},
        "candidates": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
        "components": {"type": ["object", "null"]}}},
}


def _get(summary: str, params: List[Dict[str, Any]], schema: Dict[str, Any]) -> Dict[str, Any]:
    return {"get": {"summary": summary, "parameters": params, "responses": {
        "200": {"description": "OK", "content": {"application/json": {"schema": schema}}},
        "400": {"description": "missing or bad parameter",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}}}}


def _post(summary: str, body: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    return {"post": {"summary": summary,
                     "requestBody": {"required": True, "content": {"application/json": {"schema": body}}},
                     "responses": {
                         "200": {"description": "OK", "content": {"application/json": {"schema": schema}}},
                         "400": {"description": "bad JSON or parameter"},
                         "413": {"description": "body, text or batch too large"},
                         "415": {"description": "body not sent as application/json"}}}}


def openapi_spec(version: str, max_batch: int) -> Dict[str, Any]:
    obj = {"type": "object"}
    ref = {"$ref": "#/components/schemas/Address"}
    return {
        "openapi": "3.1.0",
        "info": {"title": "JADEN", "version": version,
                 "description": "Offline Japanese address normalization, validation and lookup. "
                                "Every GET endpoint also accepts POST with the same fields as a JSON body."},
        "paths": {
            "/v1/normalize": _get("Resolve, verify and format one address", [_ADDRESS, _STRICT, _FIX], ref),
            "/v1/validate": _get("Validation status and reason only", [_ADDRESS, _STRICT, _FIX],
                                 {"$ref": "#/components/schemas/Validation"}),
            "/v1/geocode": _get("Offline coordinates", [_ADDRESS], obj),
            "/v1/suggest": _get("Autocomplete (kanji or kana prefix)",
                                [_q("q", "what has been typed so far", example="東京都港区芝"),
                                 _q("limit", "1-50, default 10", kind="integer")], obj),
            "/v1/postal/{code}": {"get": {"summary": "Postal code to addresses", "parameters": [
                {"name": "code", "in": "path", "required": True, "schema": {"type": "string"}, "example": "105-0011"}],
                "responses": {"200": {"description": "OK"}, "404": {"description": "unknown postal code"}}}},
            "/v1/reverse": _get("Coordinate to the nearest towns", [
                _q("lat", "latitude", True, "number", 35.6586), _q("lon", "longitude", True, "number", 139.7454),
                _q("limit", "1-20, default 1", kind="integer")], obj),
            "/v1/compare": _get("Are two addresses the same place?", [
                _q("a", "first address", True), _q("b", "second address", True)], obj),
            "/v1/resolve": _get("Candidate municipalities with calibrated probabilities", [
                _q("q", "the address", True, example="錦町1番2号"),
                _q("name", "side information such as a facility or company name"),
                _q("limit", "1-60, default 10", kind="integer")], obj),
            "/v1/fields": _get("An address in separate form fields, each checked against the others", [
                _q("postal_code", "postal code", example="105-0011"), _q("prefecture", "prefecture", example="東京都"),
                _q("city", "municipality", example="港区"), _q("line1", "town and numbers", example="芝公園4-2-8"),
                _q("line2", "building, floor, room"), _STRICT], obj),
            "/v1/label": _get("The address split into lines for a label or fixed-length fields", [
                _ADDRESS, _q("width", "characters (or bytes) per line, 4-200, default 20", kind="integer"),
                _q("lines", "at most this many lines, 1-20, default 3", kind="integer"),
                _q("count", "'chars' (default) or 'bytes' (Shift_JIS: full-width 2, half-width 1)"),
                _q("fullwidth", "1 = digits, letters and hyphens in full width", kind="boolean"),
                _q("postal", "1 = the postal code on a line of its own first", kind="boolean"), _FIX], obj),
            "/v1/extract": _post("Addresses inside a text",
                                 {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
                                 obj),
            "/v1/batch": _post(f"Many addresses at once (at most {max_batch})",
                               {"type": "object", "required": ["addresses"], "properties": {
                                   "addresses": {"type": "array", "items": {"type": "string"}, "maxItems": max_batch},
                                   "strict": {"type": "boolean"}, "fix": {"type": "boolean"}}},
                               {"type": "object", "properties": {
                                   "count": {"type": "integer"}, "summary": obj,
                                   "results": {"type": "array", "items": ref}}}),
            "/v1": _get("Endpoint list and data versions", [], obj),
            "/v1/openapi.json": _get("This description", [], obj),
            "/health": _get("Liveness", [], obj),
        },
        "components": {"schemas": _SCHEMAS},
    }
