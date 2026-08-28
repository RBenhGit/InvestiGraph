"""camelCase <-> snake_case JSON key conversion.

`history/models.py`'s Pydantic models (and every other model this web layer
serializes) use snake_case field names, matching this codebase's own style —
none of them declare camelCase aliases (confirmed in the Phase 4-6 convergence
review). The verbatim Eps_Evaluation front end (`web/static/app.js`,
`valuations.js`) was written against camelCase JSON and is being kept
unmodified, so every request body this layer parses and every response body
it returns needs this conversion at the boundary — used symmetrically by the
history and valuations routes in `web/app.py`.
"""

from __future__ import annotations

import re
from typing import Any

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def snake_to_camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(word.capitalize() for word in rest)


def keys_to_snake_case(value: Any) -> Any:
    if isinstance(value, dict):
        return {camel_to_snake(k): keys_to_snake_case(v) for k, v in value.items()}
    if isinstance(value, list):
        return [keys_to_snake_case(v) for v in value]
    return value


def keys_to_camel_case(value: Any) -> Any:
    if isinstance(value, dict):
        return {snake_to_camel(k): keys_to_camel_case(v) for k, v in value.items()}
    if isinstance(value, list):
        return [keys_to_camel_case(v) for v in value]
    return value
