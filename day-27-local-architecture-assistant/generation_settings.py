"""Small opt-in overrides; absent overrides preserve the Day 28 wire contract."""
import math


def settings(temperature=0, keep_alive=0):
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("temperature должен быть конечным числом 0..2.")
    if not ((type(keep_alive) is int and keep_alive == 0) or keep_alive == "5m"):
        raise ValueError("keep_alive должен быть 0 или 5m.")
    return {"temperature": temperature, "keep_alive": keep_alive}
