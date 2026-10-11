"""Optional untrusted conversation data; no HTTP dependencies or persistence."""
import json

MAX_HISTORY_BYTES = 8192


def history_bytes(history):
    return json.dumps(history, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def check_history(history):
    if not isinstance(history, list) or len(history) > 2:
        raise ValueError("История должна содержать до двух пар.")
    for pair in history:
        if (not isinstance(pair, dict) or set(pair) != {"user", "assistant"}
                or any(not isinstance(v, str) or not v.strip() for v in pair.values())
                or len(pair["user"]) > 2000):
            raise ValueError("Недопустимая пара истории.")
    try:
        if len(history_bytes(history)) > MAX_HISTORY_BYTES:
            raise ValueError("История превышает 8 KiB.")
    except UnicodeError:
        raise ValueError("Некорректный Unicode истории.") from None
    return history
