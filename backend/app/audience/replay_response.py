"""Bounded, stat-invalidated compressed transport for recorded replay artifacts."""
from collections import OrderedDict
from functools import lru_cache
import gzip,hashlib,json,threading
from pathlib import Path
from flask import Response,request
from .world import read_json
_cache=OrderedDict();_lock=threading.Lock();_limit=32*1024*1024


def stamp(path):
    s=Path(path).stat();return (str(path),s.st_mtime_ns,s.st_size,s.st_ino)


@lru_cache(maxsize=32)
def _rounds(key):return read_json(Path(key[0]))['meta']['rounds']


def rounds(path):return _rounds(stamp(path))


@lru_cache(maxsize=16)
def _completed(key):
    return frozenset(i.get('scene_id') for i in read_json(Path(key[0])).get('items',{}).values() if i.get('status')=='completed')


def completed(path):return _completed(stamp(path))


def replay_response(path,repair=None):
    path=Path(path)
    try:key=stamp(path)
    except FileNotFoundError:
        if repair is None:raise
        repair();key=stamp(path)
    with _lock:
        value=_cache.get(key)
        if value:_cache.move_to_end(key)
    if value is None:
        try:data=read_json(path)
        except ValueError:
            if repair is None:raise
            data=repair();key=stamp(path)
        raw=json.dumps(dict(success=True,data=data),ensure_ascii=False,separators=(',',':')).encode()
        payload=gzip.compress(raw,compresslevel=1,mtime=0)
        value=(payload,hashlib.sha256(payload).hexdigest())
        with _lock:
            _cache[key]=value
            while len(_cache)>32 or sum(len(v[0]) for v in _cache.values())>_limit:_cache.popitem(last=False)
    payload,tag=value
    response=Response(status=304) if request.if_none_match.contains_weak(tag) else Response(payload if request.accept_encodings['gzip']>0 else gzip.decompress(payload),mimetype='application/json')
    if response.status_code==200 and request.accept_encodings['gzip']>0:response.headers['Content-Encoding']='gzip'
    response.set_etag(tag,weak=True);response.headers['Cache-Control']='private, max-age=0, must-revalidate';response.headers['Vary']='Accept-Encoding'
    return response
