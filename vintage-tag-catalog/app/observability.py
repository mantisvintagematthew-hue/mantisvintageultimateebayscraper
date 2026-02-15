from __future__ import annotations

import contextvars
import logging
import uuid


_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="")


class RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get() or "-"
        return True



def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s run_id=%(run_id)s %(name)s %(message)s"))
    handler.addFilter(RunIdFilter())
    root.addHandler(handler)
    root.setLevel(level)



def start_run_id() -> str:
    rid = uuid.uuid4().hex[:12]
    _run_id.set(rid)
    return rid



def get_run_id() -> str:
    return _run_id.get() or ""
