"""Mesoscopic vehicle routes on connected map geometry, never measured flow."""
import math
import random
from itertools import accumulate
from collections import defaultdict


def route_pool(network, seed, policies=()):
    graph=defaultdict(list); seen=set();scale=network['meters_per_unit']
    for path in network.get('vehicle_paths',[]):
        tags=path.get('tags',{})
        if tags.get('access') in ('no','private') or tags.get('motor_vehicle') in ('no','private') or tags.get('motorcar')=='no':continue
        allowed={'car','taxi','bus','van'}
        if tags.get('highway')=='busway' or tags.get('access')=='bus':allowed={'bus'}
        for policy in policies:
            if tags.get('name','').casefold()==policy['road'].casefold():allowed &= set(policy['allowed'])
        if not allowed:continue
        level=(str(tags.get('layer','0')),str(tags.get('bridge','no')),str(tags.get('tunnel','no')))
        def key(p):return (round(p['x'],3),round(p['y'],3),*level)
        oneway=tags.get('oneway')
        for a,b in zip(path['points'],path['points'][1:]):
            length=math.hypot(b['x']-a['x'],b['y']-a['y'])*scale
            if length<.2:continue
            directions=[]
            if oneway!='-1':directions.append((a,b))
            if oneway not in ('yes','true','1'):directions.append((b,a))
            for start,end in directions:
                ka,kb=key(start),key(end)
                if (ka,kb) in seen:continue
                seen.add((ka,kb));graph[ka].append(dict(end=kb,length=length,allowed=allowed,name=tags.get('name','地图道路'),highway=tags.get('highway','road')))
    if not graph:return []
    rng=random.Random(f'route-pool:{seed}');nodes=sorted(graph)
    # Prefer outer nodes for arrivals; only connect coordinates actually shared
    # at the same mapped level. Never join separated overpasses or nearby roads.
    outer=sorted(nodes,key=lambda p:math.hypot(p[0]-500,p[1]-295),reverse=True)[:max(1,len(nodes)//3)]
    result=[]
    for _ in range(180):
        start=rng.choice(outer);current=start;visited={current};points=[dict(x=start[0],y=start[1])];length=0.;allowed={'car','taxi','bus','van'};names=[];junctions=[];goal=rng.uniform(650,1200)
        for step in range(700):
            choices=[e for e in graph[current] if e['end'] not in visited and allowed & e['allowed']]
            if not choices:break
            weights=[2 if e['highway'] in ('primary','secondary','tertiary') else 1 for e in choices]
            e=rng.choices(choices,weights)[0];previous=current;current=e['end'];visited.add(current);length+=e['length'];allowed &= e['allowed'];names.append(e['name']);points.append(dict(x=current[0],y=current[1]))
            if sum(edge['end']!=previous for edge in graph[current])>1:junctions.append(len(points)-1)
            if length>=goal:break
        if length>=60:
            reduced,saved_junctions=simplify_route(points,junctions)
            result.append(dict(points=reduced,junctions=saved_junctions,length=length,allowed=sorted(allowed),roads=list(dict.fromkeys(names))))
    # Dedupe repeated paths without discarding disconnected legitimate corridors.
    unique={tuple((p['x'],p['y']) for p in r['points']):r for r in result}
    return sorted(unique.values(),key=lambda r:r['length'],reverse=True)[:100]


def simplify_route(points,junctions):
    # Remove near-collinear map tessellation vertices, retaining intersections.
    # A vertex is not a traffic light; do not invent a stop every N vertices.
    kept=[points[0]];kept_junctions=[];junctions=set(junctions)
    for i in range(1,len(points)-1):
        a,b,c=kept[-1],points[i],points[i+1]
        length=math.hypot(c['x']-a['x'],c['y']-a['y'])
        distance=abs((c['y']-a['y'])*b['x']-(c['x']-a['x'])*b['y']+c['x']*a['y']-c['y']*a['x'])/max(length,.001)
        if i in junctions or distance>.15:
            kept.append(b)
            if i in junctions:kept_junctions.append(len(kept)-1)
    kept.append(points[-1]);return kept,kept_junctions


def connected_vehicles(slot,seed,base_count,network,policies=(),pool=None,absolute_count=False,max_samples=3000):
    from .traffic import VEHICLES
    pool=route_pool(network,seed,policies) if pool is None else pool
    if not pool or base_count==0:return []
    factor={'quiet':.18,'morning':1.5,'evening':1.6,'night':1.2,'daytime':1.}.get(slot.get('period'),1.)
    target=max(0,round(base_count if absolute_count else base_count*factor*slot.get('activity_factor',1.)))
    if type(max_samples) is not int or not 1<=max_samples<=3000:raise ValueError("车辆样本上限须为1–3000")
    count=min(max_samples,target)
    # Each path is a stratified traffic sample; integer weights preserve volume.
    weight,remainder=divmod(target,max(1,count))
    rng=random.Random(f'connected-vehicles:{seed}:{slot["round"]}');result=[]
    peak=slot.get('period') in ('morning','evening')
    cumulative=list(accumulate(r["length"] for r in pool))
    for i in range(count):
        route=rng.choices(pool,cum_weights=cumulative)[0];defs=[v for v in VEHICLES if v['kind'] in route['allowed']]
        if not defs:continue
        definition=rng.choices(defs,[{'car':66,'taxi':18,'bus':5,'van':11}[v['kind']] for v in defs])[0]
        # Lower peak speeds model urban congestion; signal wait is an explicit
        # scenario assumption, not an inferred measured signal phase.
        speed=rng.uniform(14,23) if peak else rng.uniform(23,35)
        elapsed=0.;points=[dict(**route['points'][0],minute=0.,activity='驶入连通道路')]
        for j,(a,b) in enumerate(zip(route['points'],route['points'][1:])):
            elapsed+=math.hypot(b['x']-a['x'],b['y']-a['y'])*network['meters_per_unit']/(speed/3.6)/60
            points.append(dict(**b,minute=elapsed))
            if j+1 in route.get('junctions',[]) and rng.random()<.5:
                elapsed+=rng.uniform(.1,.45) if peak else rng.uniform(.03,.15)
                points.append(dict(**b,minute=elapsed,activity='路口等候（假设）'))
        if elapsed>=59:continue
        start=(i+rng.random())/max(1,count)*(60-elapsed-.01)
        for point in points:point['minute']=round(point['minute']+start,5)
        points[-1]['activity']='驶出当前行程范围'
        # Keep positions on supplied road geometry. Lanes/turn restrictions need
        # further map/traffic data; no claim of collision-free microscopic physics.
        result.append(dict(id=f'v-{slot["round"]}-{i}',represented_vehicles=weight+(i<remainder),**{k:v for k,v in definition.items() if k!='occupancy'},occupants=rng.randint(*definition['occupancy']),speed_kmh=round(speed,2),direction=1,
            journey=dict(start_minute=points[0]['minute'],end_minute=points[-1]['minute'],waypoints=points,purpose=' → '.join(route['roads'][:4]),distance_m=round(route['length'])),
            source='OSM / Mapricot 地图连通道路 + 合成到达/速度/路口等待；不是实测车流，未校准车道与避碰'))
    return result
