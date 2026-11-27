import importlib.util
from pathlib import Path


def test_lightweight_checkpoints_keep_full_terminal_day(monkeypatch,tmp_path):
    file=Path(__file__).resolve().parents[1]/'scripts/run_audience_world_fast.py'
    spec=importlib.util.spec_from_file_location('fast_worker',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    writes=[]
    monkeypatch.setattr(module,'write_full_json',lambda path,value:writes.append((Path(path).name,value.copy())))
    for hour in range(1,25):module.write_json(tmp_path/'state.json',{'status':'running','current_round':hour})
    module.write_json(tmp_path/'state.json',{'status':'completed','current_round':24,'snapshots':list(range(25))})
    assert len([v for name,v in writes if name=='progress.json'])==25
    full=[v for name,v in writes if name=='state.json']
    assert len(full)==7 and len(full[-1]['snapshots'])==25
