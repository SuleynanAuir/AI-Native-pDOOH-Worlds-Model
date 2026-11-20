"""Project-local storage with atomic writes and per-project process locks."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import threading
import uuid

try:
    import fcntl
except ImportError:
    fcntl=None

_guard=threading.RLock()
_locks={}


def directory(root, project_id):
    if not re.fullmatch(r'[0-9a-f]{32}',project_id): raise ValueError('项目 ID 无效')
    path=Path(root)/'planning'/project_id
    if not path.is_dir(): raise FileNotFoundError('项目不存在')
    return path


def save(path, project):
    temp=path/f'.{uuid.uuid4().hex}.tmp'
    temp.write_text(json.dumps(project,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    temp.replace(path/'project.json')


def create(root, project):
    pid=uuid.uuid4().hex
    path=Path(root)/'planning'/pid; path.mkdir(parents=True)
    project['id']=pid; save(path,project)
    return project


@contextmanager
def locked(root,pid):
    path=directory(root,pid)
    with _guard:
        project_lock=_locks.setdefault(pid,threading.RLock())
    with project_lock:
        with (path/'.lock').open('a') as lock:
            if fcntl: fcntl.flock(lock,fcntl.LOCK_EX)
            try:
                project=json.loads((path/'project.json').read_text(encoding='utf-8'))
                yield path,project
            finally:
                if fcntl: fcntl.flock(lock,fcntl.LOCK_UN)
