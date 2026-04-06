from datetime import datetime, UTC


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()