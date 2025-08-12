from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .config import Config
from ..core.context import get_request_id  # <<< 新增

# 过滤掉 logging.LogRecord 的“内置字段”，其余都当作 extra 合并
_SKIP = {
    "name","msg","args","levelname","levelno","pathname","filename","module",
    "exc_info","exc_text","stack_info","lineno","funcName","created","msecs",
    "relativeCreated","thread","threadName","processName","process","asctime"
}

def _gather_extra(record: logging.LogRecord) -> dict:
    out = {}
    for k, v in record.__dict__.items():
        if k not in _SKIP and not k.startswith("_"):
            out[k] = v
    # 注入 request_id（若 middleware 已设置）
    rid = get_request_id()
    if rid and "request_id" not in out:
        out["request_id"] = rid
    return out

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
        }
        extra = _gather_extra(record)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

PRETTY_FMT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
DATE_FMT = "%H:%M:%S"

def init_logging(cfg: Optional[Config] = None) -> None:
    cfg = cfg or Config.load()
    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.logging.level.upper(), logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)

    ch = logging.StreamHandler()
    ch.setFormatter(JsonFormatter() if cfg.logging.format == "json"
                    else logging.Formatter(PRETTY_FMT, DATE_FMT))
    root.addHandler(ch)

    if cfg.logging.file:
        log_path = Path(cfg.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_path,
            maxBytes=cfg.logging.rotate_mb * 1024 * 1024,
            backupCount=cfg.logging.rotate_backups,
        )
        fh.setFormatter(JsonFormatter() if cfg.logging.format == "json"
                        else logging.Formatter(PRETTY_FMT, DATE_FMT))
        root.addHandler(fh)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
