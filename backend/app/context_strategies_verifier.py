"""Reference answers and deterministic scoring. Never imported by payload construction."""
import re
import unicodedata

from app.context_strategies_models import Specification, strict_json
from app.fact_extractor import scalar, user_assertions

SHARED = {"goal": "бронирование переговорных", "platform": "Android", "deadline_weeks": 6,
          "pilot_users": 37, "offline_schedule": True, "stores_card_data": False,
          "style": "спокойный", "auth": "magic_link", "approver": "Мира"}
ALTERNATIVES = {"A": {"payment": "on_site", "confirmation": "immediate"},
                "B": {"payment": "link", "confirmation": "admin"}}


def equal(actual, expected):
    if type(actual) is not type(expected): return False
    if isinstance(actual, str):
        return unicodedata.normalize("NFC", actual.strip()) == expected
    return actual == expected


def expected(variant):
    return {**{("shared", k): v for k, v in SHARED.items()},
            **{(variant, k): v for k, v in ALTERNATIVES[variant].items()}}


def quality(reply, variant):
    try:
        result = Specification.model_validate(strict_json(reply)).model_dump()
    except (ValueError, TypeError):
        return {"score": None, "total": 11, "reason": "invalid_structured_output", "fields": {}}
    checks = {key: equal(result[key], value) for (_, key), value in expected(variant).items()}
    return {"score": sum(checks.values()), "total": 11, "reason": None, "fields": checks}


def assistant_assertions(text):
    if re.fullmatch(r"\s*Принято\.?\s*", text, re.I): return {}
    stripped = text.strip()
    if stripped.startswith("{"):
        values = strict_json(stripped)
        scope = values.pop("scope", None)
        if scope is not None and scope not in ("shared", "A", "B"): raise ValueError()
        if not values: raise ValueError()
        if scope is None and any(k not in SHARED for k in values): raise ValueError()
        if any(type(v) not in (str, int, bool, type(None)) for v in values.values()): raise ValueError()
        return {(scope or "shared", k): v for k, v in values.items()}
    scope = "shared"
    pairs = {}
    for part in re.split(r"[\r\n;,]+", stripped):
        part = part.strip()
        if not part: continue
        marker = re.fullmatch(r"(?:Область требований:|scope=)\s*(shared|A|B)\.?", part)
        if marker:
            scope = marker[1]
            continue
        match = re.fullmatch(r"(?:(shared|A|B)\.)?([a-z][a-z0-9_]*)\s*=\s*(.+?)", part)
        if not match: raise ValueError()
        actual_scope = match[1] or scope
        if not match[1] and actual_scope == "shared" and match[2] not in SHARED: raise ValueError()
        identity = (actual_scope, match[2])
        if identity in pairs: raise ValueError()
        pairs[identity] = scalar(match[3])
    if not pairs: raise ValueError()
    return pairs


def retention(sources, facts, variant, user_order):
    """user_order contains IDs/ordinals only, never excluded audit text."""
    state, rank, conflicts = {}, {}, set()
    for f in facts:
        key = (f["scope"], f["key"])
        state[key] = f["value"] if f["state"] == "set" else None
        rank[key] = user_order[f["user_id"]]
    try:
        assistant_order = -1
        for message in sources:
            if message["role"] == "user":
                assistant_order = user_order[message["message_id"]]
                values = {k: v[0] for k, v in user_assertions(message["content"]).items()}
                for key, value in values.items():
                    order = user_order[message["message_id"]]
                    if order >= rank.get(key, -1):
                        state[key], rank[key] = value, order
                        conflicts.discard(key)
            else:
                for key, value in assistant_assertions(message["content"]).items():
                    if rank.get(key, -1) > assistant_order: continue
                    if key in state and not equal(value, state[key]): conflicts.add(key)
                    elif key not in state: state[key] = value
    except (ValueError, TypeError, KeyError):
        return {"score": None, "total": 11, "reason": "unverifiable_restatement", "fields": {}}
    checks = {k: (scope, k) not in conflicts and equal(state.get((scope, k)), value)
              for (scope, k), value in expected(variant).items()}
    return {"score": sum(checks.values()), "total": 11, "reason": None, "fields": checks}
