"""Structured operational metadata only: never log prompts, responses or headers."""
import json
import logging
import os
import sys
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

request_id = ContextVar('request_id', default=None)
_logger = None

def log_dir():
    return Path(os.getenv('DATA_DIR',str(Path(__file__).resolve().parents[1]/'data'))) / 'logs'

def logger():
    global _logger
    if _logger is None:
        target=log_dir();target.mkdir(parents=True,exist_ok=True)
        output=logging.getLogger('caihe.operations');output.setLevel(logging.INFO);output.propagate=False
        file=RotatingFileHandler(target/'api.jsonl',maxBytes=5*1024*1024,backupCount=3,encoding='utf-8')
        output.addHandler(file);output.addHandler(logging.StreamHandler(sys.__stderr__))
        _logger=output
    return _logger

def emit(event, **fields):
    record={'time':datetime.now(timezone.utc).isoformat(),'event':event,'request_id':request_id.get(),**fields}
    logger().info(json.dumps(record,ensure_ascii=False,separators=(',',':')))

def task_calls(task_id):
    records=[]
    # Bounded recent history, including one rollover. No request/response body is stored.
    for file in (log_dir()/'api.jsonl.1',log_dir()/'api.jsonl'):
        if not file.exists():continue
        with file.open(encoding='utf-8') as source:
            for line in deque(source,maxlen=10000):
                try: record=json.loads(line)
                except ValueError:continue
                if record.get('task_id')==task_id and record.get('event','').startswith('model.'):
                    records.append(record)
    return records[-300:]
