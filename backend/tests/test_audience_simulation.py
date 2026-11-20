import importlib.util
from pathlib import Path
import copy
import pytest

spec = importlib.util.spec_from_file_location('audience_engine', Path(__file__).parents[1] / 'app/audience/engine.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def config():
    return dict(population=1000, seed=42, groups=copy.deepcopy(engine.DEFAULT_GROUPS), screens=[dict(id='A', visibility=1, obstruction=0, viewing_distance=10, physical_height=2, slot_seconds=10)])


def test_reproducible_and_conserved():
    p = config()
    r = engine.simulate(p)
    assert r == engine.simulate(p)
    t = r['screens'][0]['totals']
    assert sum(t.get(k, 0) for k in ('ignored', 'glanced', 'watched', 'interested')) == 1000
    assert t.get('interested', 0) == 0
    assert sum(g['counts'].get('encounters', 0) for g in r['screens'][0]['groups']) == 1000


def test_obstruction_prevents_notice():
    p = config(); p['screens'][0]['obstruction'] = 1
    assert engine.simulate(p)['screens'][0]['totals']['ignored'] == 1000


def test_group_dwell_drives_different_reactions():
    p = config()
    for g in p['groups']: g['attention'] = 1
    groups = {g['group_id']: g['counts'] for g in engine.simulate(p)['screens'][0]['groups']}
    assert groups['commuter'].get('full_view', 0) == 0
    assert groups['waiting']['full_view'] == groups['waiting']['encounters']


@pytest.mark.parametrize('key,value', [('population', 1.5), ('population', float('nan')), ('seed', -1), ('groups', []), ('screens', []), ('groups', [None])])
def test_invalid_inputs(key, value):
    p = config(); p[key] = value
    with pytest.raises(ValueError): engine.simulate(p)


def test_duplicate_screens_and_zero_shares():
    p = config(); p['screens'] *= 2
    with pytest.raises(ValueError): engine.simulate(p)
    p = config()
    for g in p['groups']: g['share'] = 0
    with pytest.raises(ValueError): engine.simulate(p)


def test_creative_interest_is_conditional():
    p = config(); p['creative_supplied'] = True
    p['groups'] = [dict(id='test', name='test', share=1, mobility='waiting', dwell_seconds=100, attention=1, interest=1)]
    assert engine.simulate(p)['screens'][0]['totals']['interested'] == 1000
