"""Always-visible 1C route inbound log: stdout + file on the uploads volume."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("1c_route_inbound")

_LOG_NAME = "1c_route_inbound.log"


def _file_path() -> Path:
    root = os.getenv("MOBILE_UPLOAD_ROOT", "/data/mobile_uploads").strip() or "/data/mobile_uploads"
    return Path(root) / _LOG_NAME


def emit_1c_inbound(message: str) -> None:
    """Write a line that `docker logs | grep 1c_route_inbound` and the volume file both see."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"1c_route_inbound {stamp} {message}".replace("\n", "\\n")
    print(line, flush=True)
    try:
        logger.info("%s", line)
    except Exception:
        pass
    try:
        path = _file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"1c_route_inbound file_write_failed {exc}", flush=True)


def configure_1c_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
    for name in (
        "1c_route_inbound",
        "api",
        "api.api_server",
        "mobile_api",
        "mobile_api.legacy_route_api",
    ):
        log = logging.getLogger(name)
        log.setLevel(logging.INFO)
        if not any(isinstance(item, logging.StreamHandler) for item in log.handlers):
            log.addHandler(handler)
