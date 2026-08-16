from __future__ import annotations


def clamp_percent(value: object) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def format_bytes(value: object) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—"
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.0f} {unit}" if unit in {"B", "KB", "MB"} else f"{amount:.1f} {unit}"
        amount /= 1024


def format_uptime(value: object) -> str:
    try:
        seconds = max(0, int(float(value)))
    except (TypeError, ValueError):
        return "—"
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"
