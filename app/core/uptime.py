import time

_start_time = time.time()


def get_uptime_seconds() -> float:
    return round(time.time() - _start_time, 1)
