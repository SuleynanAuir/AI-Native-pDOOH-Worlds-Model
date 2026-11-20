import math
import pytest
from app.audience.world import scene
from app.audience.mobility import neighborhood,journey,validate_mobility,with_viewing_stop,movement_summary
from app.audience.cohorts import summarize


@pytest.fixture(scope='module')
def world():return scene(day_cycle={},total_population=30000)


def test_all_hourly_journeys_follow_connected_walkways_and_leave(world):
    network=world['neighborhood'];nodes={n['id']:n for n in network['nodes']}
    edges={frozenset((e['a'],e['b'])) for e in network['edges']}
    covered=set();departures=set();modes=set();unexposed=0
    for slot,trips in zip(world['schedule'],world['mobility_rounds']):
        assert {int(k) for k in trips}==set(slot['present_agent_ids'])
        for trip in trips.values():
            points=trip['waypoints'];covered.update(p['id'] for p in points)
            assert 0<=trip['start_minute']<trip['end_minute']<60
            assert points[0]['minute']==trip['start_minute'] and points[-1]['minute']==trip['end_minute']
            assert trip['departure_mode'] in ('walking','transit')
            departures.add(trip['destination_id']);modes.add(trip['mode'])
            for a,b in zip(points,points[1:]):
                assert b['minute']>=a['minute']
                if a['id']==b['id']:continue
                assert frozenset((a['id'],b['id'])) in edges
                dist=math.hypot(b['x']-a['x'],b['y']-a['y'])*network['meters_per_unit']
                actual=dist/(b['minute']-a['minute'])/60
                assert abs(actual-trip['speed_mps'])<.002
            if trip['encounter'] is None:unexposed+=1
            else:
                encounter=trip['encounter'];screen=next(s for s in world['screens'] if s['id']==encounter['screen_id'])
                assert math.hypot(encounter['x']-screen['x'],encounter['y']-screen['y'])<=network['view_radius']
                assert trip['start_minute']<=encounter['minute']<=trip['end_minute']
    assert covered==set(nodes), 'Surrounding streets must be visited, not only screen zones'
    assert departures=={'west','east','southwest','southeast','transit'}
    assert modes=={'walking','walk_transit'}
    assert unexposed>0


def test_ordinary_passers_walk_even_when_transit_probability_is_high(world):
    profile={**world['agents'][0],'local_context':{'visit_purpose':'普通路人路过社区，不候车'}}
    trip=journey(profile,dict(round=1,period='morning'),42,world['neighborhood'],dict(walking_share=0,explore_share=0),world['screens'])
    assert trip['mode']=='walking' and trip['departure_mode']=='walking'
    assert trip['stops']==[] and trip['purpose']=='普通行人穿行'
    changed={**profile,'represented_population':99999,'audience_profile':{**profile['audience_profile'],'purchasing_power':'不同收入','economic_context':'不同阶层'}}
    assert trip==journey(changed,dict(round=1,period='morning'),42,world['neighborhood'],dict(walking_share=0,explore_share=0),world['screens'])


def test_walking_setting_and_seed_apply_to_whole_day(world):
    all_walk=scene(day_cycle={},mobility=dict(walking_share=1,explore_share=0))
    assert all(j['mode']=='walking' and not j['exploring'] for r in all_walk['mobility_rounds'] for j in r.values())
    assert world==scene(day_cycle={},total_population=30000)
    assert world['mobility_rounds']!=scene(day_cycle={},seed=43)['mobility_rounds']


@pytest.mark.parametrize('value',[[],{'walking_share':-1},{'walking_share':1.1},{'explore_share':True},{'explore_share':float('nan')}])
def test_bad_mobility_rejected(value):
    with pytest.raises(ValueError):validate_mobility(value)


def test_viewing_pause_preserves_route_and_elapsed_time(world):
    trip=next(j for r in world['mobility_rounds'] for j in r.values() if j['encounter'])
    paused=with_viewing_stop(trip,dict(reaction='watch',dwell_seconds=20))
    viewing=[p for p in paused['waypoints'] if p['id']=='viewing']
    assert len(viewing)==2
    assert viewing[0]['x']==viewing[1]['x']==trip['encounter']['x']
    assert viewing[1]['minute']-viewing[0]['minute']==pytest.approx(20/60)
    assert paused['end_minute']==pytest.approx(trip['end_minute']+20/60)
    assert paused['end_minute']<60
    assert all(a['minute']<=b['minute'] for a,b in zip(paused['waypoints'],paused['waypoints'][1:]))
    assert 'viewing_stop_seconds' not in trip


def test_unexposed_is_neither_away_nor_ignoring_ad(world):
    a,b=world['agents'][:2]
    agents=[{**a,'reaction':'unexposed','dwell_seconds':None,'screen_id':None},
            {**b,'reaction':'watch','dwell_seconds':8,'screen_id':world['screens'][0]['id']}]
    summary=summarize(agents)
    assert summary['weighted_counts']['passing']==0
    assert summary['active_population']==sum(a['represented_population'] for a in agents)
    assert summary['noticed_population']==b['represented_population']
    assert summary['weighted_mean_dwell_seconds']==8
    trips=world['mobility_rounds'][8]
    expanded=[{**a,'journey':trips.get(str(a['id']))} for a in world['agents']]
    movement=movement_summary(expanded)
    assert movement['walking_departures']+movement['transit_departures']==world['schedule'][8]['scheduled_population']
