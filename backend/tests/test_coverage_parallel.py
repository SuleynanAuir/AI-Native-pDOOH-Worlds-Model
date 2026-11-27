import threading
import time
from types import SimpleNamespace
from app.audience import coverage, store, planning, investment_evidence
from app.audience.world import read_json, write_json


def test_parallel_coverage_preserves_completed_and_bounds_workers(tmp_path, monkeypatch):
    cid='a'*32
    project=store.create(tmp_path,dict(frames=[],ad_setup={}))
    pid=project['id']
    campaign=tmp_path/'campaign_experiments'/cid
    campaign.mkdir(parents=True)
    write_json(campaign/'state.json',{'spec':{'campaign':{}}})
    write_json(campaign/'research.json',{})
    frames=[dict(screen_id=str(i),key=str(i)) for i in range(8)]
    monkeypatch.setattr(planning,'clean',lambda *args:frames)
    monkeypatch.setattr(investment_evidence,'resolve',lambda *args:dict(screens={},fingerprint='test'))
    folder=coverage.path(tmp_path,pid,cid);folder.mkdir()
    write_json(folder/'state.json',dict(status='interrupted',items={'0':dict(status='completed',scene_id='retained')},fingerprint='test'))
    lock=threading.Lock();active=0;peak=0;visited=[]
    barrier=threading.Barrier(3)
    class Client:
        def post(self,url,json):
            nonlocal active,peak
            if url.endswith('geo-inventory'):return SimpleNamespace(status_code=200,json={'data':{'id':'inventory','frames':frames}})
            assert url.endswith('locate-frame')
            with lock:
                active+=1;peak=max(peak,active);visited.append(json['frame_key'])
            barrier.wait(timeout=3)
            with lock:active-=1
            return SimpleNamespace(status_code=400,json={'error':'provider unavailable'})
    app=SimpleNamespace(config={'UPLOAD_FOLDER':str(tmp_path)},test_client=Client)
    coverage.start(app,pid,cid)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        state=read_json(folder/'state.json')
        if state['status']!='running':break
        time.sleep(.02)
    assert state['status']=='interrupted'
    assert peak==3
    assert '0' not in visited
    assert state['done']==1
    assert state['items']['0']['scene_id']=='retained'
    assert state['workers']==3


def test_progress_externalizes_inputs_without_losing_resume_data(tmp_path):
    from app.audience.coverage import externalize_inputs,input_path
    items={'screen':dict(status='completed',context={'map':'x'*100000},template={'groups':[1,2]},run_id='r')}
    externalize_inputs(tmp_path,items)
    assert items['screen']['status']=='completed' and items['screen']['run_id']=='r'
    assert 'context' not in items['screen'] and 'template' not in items['screen']
    assert read_json(input_path(tmp_path,'screen'))=={'context':{'map':'x'*100000},'template':{'groups':[1,2]}}
    externalize_inputs(tmp_path,items)
    assert read_json(input_path(tmp_path,'screen'))['template']=={'groups':[1,2]}
