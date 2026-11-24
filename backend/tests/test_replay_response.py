import gzip,json
from flask import Flask
from app.audience.replay_response import replay_response,completed
from app.audience.world import write_json


def test_compressed_cache_etag_and_source_invalidation(tmp_path):
    app=Flask(__name__);p=tmp_path/'hour.json';write_json(p,{'round':1,'data':['sample']*1000})
    with app.test_request_context(headers={'Accept-Encoding':'gzip'}):
        r=replay_response(p);tag=r.headers['ETag'];assert r.headers['Content-Encoding']=='gzip'
        assert json.loads(gzip.decompress(r.data))['data']['round']==1
        assert len(r.data)<p.stat().st_size/5
    with app.test_request_context(headers={'If-None-Match':tag}):assert replay_response(p).status_code==304
    write_json(p,{'round':2})
    with app.test_request_context(headers={'If-None-Match':tag}):
        r=replay_response(p);assert r.status_code==200 and r.json['data']['round']==2


def test_repair_and_completed_index(tmp_path):
    app=Flask(__name__);p=tmp_path/'hour.json';p.write_text('')
    def repair():
        value={'round':5};write_json(p,value);return value
    with app.test_request_context():assert replay_response(p,repair).json['data']['round']==5
    state=tmp_path/'state.json';write_json(state,{'items':{'s':{'status':'running','scene_id':'a'}}});assert not completed(state)
    write_json(state,{'items':{'s':{'status':'completed','scene_id':'a'}}});assert completed(state)=={'a'}
