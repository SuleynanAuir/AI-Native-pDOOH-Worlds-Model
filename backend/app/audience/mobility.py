"""Reproducible neighborhood journeys. This is a synthetic network, not a GIS/traffic model."""
import heapq
import math
import random

DEFAULT = dict(walking_share=.75, explore_share=.4)
X, Y = [30, 190, 370, 550, 730, 900, 970], [180, 300, 420, 550]


def validate_mobility(value=None):
    if value is None: value = {}
    if not isinstance(value, dict): raise ValueError('出行配置须为对象')
    result = dict(DEFAULT)
    for key in DEFAULT:
        v = value.get(key, DEFAULT[key])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1:
            raise ValueError('步行与探索比例须为 0–1 的数字')
        result[key] = v
    return result


def neighborhood(locality=None):
    nodes = [dict(id=f'{i}-{j}', x=x, y=y) for j, y in enumerate(Y) for i, x in enumerate(X)]
    edges = []
    for j in range(4):
        for i in range(7):
            if i < 6: edges.append(dict(a=f'{i}-{j}', b=f'{i+1}-{j}', kind='sidewalk'))
            if j < 3 and (j != 1 or i in (1, 3, 5)):
                edges.append(dict(a=f'{i}-{j}', b=f'{i}-{j+1}', kind='crossing' if j == 1 else 'sidewalk'))
    venue = (locality or {}).get('venue_type', 'station')
    venue_label = {'station':'车站 / 接驳入口','airport':'航站楼公共入口','supermarket':'商超入口','mall':'商场入口','office':'办公场所入口','street':'沿街服务入口'}.get(venue, '目标场所入口')
    places = [dict(id=k, node=n, label=label, kind=kind) for k,n,label,kind in [
        ('west','0-0','西侧社区出口','boundary'), ('east','6-0','东侧街区出口','boundary'),
        ('southwest','0-3','南侧步行出口','boundary'), ('southeast','6-3','东南步行出口','boundary'),
        ('home','1-0','住宅与社区','place'), ('office','2-0','办公街区','place'),
        ('park','5-0','公园 / 散步','place'), ('shops','4-1','沿街商店','place'),
        ('cafe','5-2','餐饮与休息','place'), ('services','2-3','社区生活服务','place'),
        ('venue','1-2',venue_label,'place'), ('transit','3-2','公共交通接续点','transit')]]
    return dict(nodes=nodes, edges=edges, places=places, meters_per_unit=.6, view_radius=65,
                source='合成街区步行网络；道路、建筑、比例尺与交通点均为情景假设，未匹配真实地图',
                assumptions='步速 0.8–1.6 m/s；人行横道等候 4–20 秒；办事/休息 1–6 分钟；步行比例是出行情景抽样概率，不是当地统计。代表点不是密度粒子，未建模人群避碰。')


def shortest_path(network, start, end, rng):
    nodes = {n['id']: n for n in network['nodes']}
    links = {k: [] for k in nodes}
    # Stable randomized edge costs allow alternate legal routes, never through buildings.
    for e in network['edges']:
        a,b=e['a'],e['b']; length=math.hypot(nodes[a]['x']-nodes[b]['x'],nodes[a]['y']-nodes[b]['y'])
        cost=length*rng.uniform(.85,1.3)+(25 if e['kind']=='crossing' else 0)
        links[a].append((b,cost));links[b].append((a,cost))
    queue=[(0,start,[start])];seen=set()
    while queue:
        cost,node,path=heapq.heappop(queue)
        if node==end:return path
        if node in seen:continue
        seen.add(node)
        for nxt,weight in links[node]:
            if nxt not in seen:heapq.heappush(queue,(cost+weight,nxt,path+[nxt]))
    raise ValueError('步行网络不连通')



class RoutePlanner:
    """Per-network A* route atlas; bounded, reproducible alternatives, no global cache."""
    def __init__(self,network,seed,variants=8):
        self.nodes={n['id']:n for n in network['nodes']}
        self.places={p['id']:p for p in network['places']}
        self.edge_index={}
        self.edges=[]
        for edge in network['edges']:
            a,b=edge['a'],edge['b']
            self.edge_index.setdefault((a,b),edge);self.edge_index.setdefault((b,a),edge)
            self.edges.append((a,b,math.hypot(self.nodes[a]['x']-self.nodes[b]['x'],self.nodes[a]['y']-self.nodes[b]['y']),25 if edge['kind']=='crossing' else 0))
        self.seed=seed;self.variants=variants;self.graphs={};self.paths={};self.searches=0

    def route(self,start,end,rng):
        variant=rng.randrange(self.variants);key=(variant,start,end)
        if key in self.paths:return self.paths[key]
        if variant not in self.graphs:
            weights=random.Random(f'route-atlas:{self.seed}:{variant}')
            links={node:[] for node in self.nodes}
            for a,b,length,penalty in self.edges:
                cost=length*weights.uniform(.85,1.3)+penalty
                links[a].append((b,cost));links[b].append((a,cost))
            self.graphs[variant]=links
        links=self.graphs[variant];target=self.nodes[end]
        def heuristic(node):
            value=self.nodes[node]
            return .85*math.hypot(value['x']-target['x'],value['y']-target['y'])
        queue=[(heuristic(start),0,start)];best={start:0};previous={};self.searches+=1
        while queue:
            _,cost,node=heapq.heappop(queue)
            if cost!=best[node]:continue
            if node==end:
                path=[end]
                while path[-1]!=start:path.append(previous[path[-1]])
                result=tuple(reversed(path));self.paths[key]=result
                return result
            for nxt,weight in links[node]:
                candidate=cost+weight
                if candidate<best.get(nxt,float('inf')):
                    best[nxt]=candidate;previous[nxt]=node
                    heapq.heappush(queue,(candidate+heuristic(nxt),candidate,nxt))
        raise ValueError('步行网络不连通')

def journey(profile, slot, seed, network, options, screens, planner=None):
    """One bounded outing per scheduled hour; no cross-hour teleporting in view.

    Income, nationality and representative weight are deliberately not used.
    Explicit visit purpose guides stops; mobility shares remain scenario inputs.
    """
    rng=random.Random(f'journey:{seed}:{profile["id"]}:{slot["round"]}')
    if planner is not None:
        places=planner.places;nodes=planner.nodes;edge_index=planner.edge_index
    else:
        places={p['id']:p for p in network['places']};nodes={n['id']:n for n in network['nodes']}
        edge_index={}
        for edge in network['edges']:
            edge_index.setdefault((edge['a'],edge['b']),edge)
            edge_index.setdefault((edge['b'],edge['a']),edge)
    boundary=['west','east','southwest','southeast']
    text=profile.get('local_context',{}).get('visit_purpose','')+' '+profile.get('audience_profile',{}).get('mobility','')
    period=slot.get('period','daytime')
    walking = rng.random() < options['walking_share']
    explore = rng.random() < options['explore_share']
    pure_passer = any(word in text for word in ('路过','穿行','散步','非候车'))
    if pure_passer or (network.get('geographic') and not places['transit'].get('source_id')): walking=True
    if any(word in text for word in ('采购','购物','商店')): target='shops'
    elif any(word in text for word in ('散步','艺术','游览')): target='park'
    elif any(word in text for word in ('员工','办公','上班')): target='office'
    elif any(word in text for word in ('接送','候车','换乘','访客')): target='venue'
    else: target=rng.choice(['shops','services','park','office','cafe'])
    if period=='night' and target=='office':target='cafe'
    if network.get('geographic') and places[target].get('kind')=='assumption':target='venue'
    origin=rng.choice(boundary)
    destination=rng.choice([p for p in boundary if p!=origin])
    if not walking:
        # Both boarding and alighting trips occur; all visible segments are on foot.
        if period=='evening' or rng.random()<.45:origin='transit'
        else:destination='transit'
    purpose='普通行人穿行' if pure_passer else '日常事务途中'
    stops=[] if pure_passer else [target]
    if explore:
        options_for_stops=[p for p in ['home','park','shops','services','cafe'] if p!=target and (not network.get('geographic') or places[p].get('kind')!='assumption')]
        extra=rng.sample(options_for_stops,min(2,len(options_for_stops)))
        stops=extra if pure_passer else [target,*extra]
        purpose='周边散步 / 多点浏览' if pure_passer else '办事后顺路浏览'
    elif not walking:purpose='步行接续公共交通'
    # Each outing explicitly ends at a boundary or a transport access, not a screen.
    speed=round(rng.uniform(.8,1.6),2)
    curtailed=False
    while True:
        visits=[origin,*stops,destination];path=[places[origin]['node']];stop_at={}
        for index,place in enumerate(visits[1:]):
            part=planner.route(path[-1],places[place]['node'],rng) if planner else shortest_path(network,path[-1],places[place]['node'],rng)
            path.extend(part[1:])
            if index<len(stops):stop_at[len(path)-1]=(place,rng.uniform(1,6))
        points=[dict(**nodes[path[0]],minute=0.,activity='进入街区' if origin!='transit' else '下车后步行')]
        elapsed=0.;distance=0.;crossings=0
        for i,(prev,nxt) in enumerate(zip(path,path[1:]),1):
            a,b=nodes[prev],nodes[nxt]
            edge=edge_index[(prev,nxt)]
            if edge['kind']=='crossing':
                elapsed+=rng.uniform(4,20)/60;crossings+=1
                points.append(dict(**a,minute=round(elapsed,4),activity='等待人行横道'))
            length=math.hypot(a['x']-b['x'],a['y']-b['y'])*network['meters_per_unit']
            distance+=length;elapsed+=length/speed/60
            points.append(dict(**b,minute=round(elapsed,4),activity='步行穿行' if not explore else '沿街浏览'))
            if i in stop_at:
                place,pause=stop_at[i];elapsed+=pause
                points.append(dict(**b,minute=round(elapsed,4),activity='停留：'+places[place]['label']))
        if elapsed<=55:break
        if not stops:raise ValueError('出行超过小时边界，需调整步行网络')
        stops.pop();curtailed=True
    explore=explore and len(stops)>1
    start=rng.uniform(0, max(0,59-elapsed))
    for point in points:point['minute']=round(point['minute']+start,4)
    points[-1]['activity']='步行离开街区' if destination!='transit' else '进入交通接续点'
    # Closest point along every traversed segment; screen choice follows the route.
    candidates=[]
    for s in screens:
        best=None
        for a,b in zip(points,points[1:]):
            dx,dy=b['x']-a['x'],b['y']-a['y'];square=dx*dx+dy*dy
            t=max(0,min(1,((s['x']-a['x'])*dx+(s['y']-a['y'])*dy)/square)) if square else 0
            x,y=a['x']+dx*t,a['y']+dy*t;dist=math.hypot(x-s['x'],y-s['y'])
            if best is None or dist<best['distance']:
                # Screens assumed two-sided; orientation remains a declared assumption.
                best=dict(screen_id=s['id'],x=x,y=y,distance=round(dist,3),minute=round(a['minute']+(b['minute']-a['minute'])*t,4))
        if best and best['distance']<=network['view_radius']:candidates.append(best)
    candidates.sort(key=lambda c:c['minute'])
    encounter=candidates[0] if candidates else None
    return dict(route_method='cached_route_variants_v1' if planner else 'per_trip_randomized_search',purpose=purpose,mode='walking' if walking else 'walk_transit',
                mode_label='全程步行' if walking else '步行 + 公共交通',origin=places[origin]['label'],destination=places[destination]['label'],
                origin_id=origin,destination_id=destination,departure_mode='walking' if destination!='transit' else 'transit',
                stops=[places[s]['label'] for s in stops],exploring=explore,waypoints=points,
                start_minute=points[0]['minute'],end_minute=points[-1]['minute'],distance_m=round(distance,1),speed_mps=speed,
                crossing_count=crossings,curtailed_optional_stops=curtailed,encounter=encounter,screen_opportunities=candidates,
                source='规则驱动的合成出行；本轮仅首块近邻屏幕调用模型推演反应，其余屏幕机会不外推曝光')


def movement_summary(agents):
    active=[a for a in agents if a.get('journey')]
    def count(predicate):return sum(a.get('represented_population',1) for a in active if predicate(a['journey']))
    return dict(scheduled_representatives=len(active),walking_population=count(lambda j:j['mode']=='walking'),
                walking_departures=count(lambda j:j['departure_mode']=='walking'),transit_departures=count(lambda j:j['departure_mode']=='transit'),
                exploring_population=count(lambda j:j['exploring']),unexposed_population=count(lambda j:j['encounter'] is None),
                basis='每小时出行情景的加权人数；不是同时在场人数或跨小时去重人数')


def with_viewing_stop(trip, decision):
    """Insert the recorded viewing pause on the route, preserving walking speed."""
    if decision['reaction'] not in ('watch','interest') or not decision.get('dwell_seconds'):
        return trip
    from copy import deepcopy
    result=deepcopy(trip);encounter=result['encounter'];minute=encounter['minute'];delay=decision['dwell_seconds']/60
    points=result['waypoints'];updated=[];inserted=False
    for point in points:
        if not inserted and point['minute']>=minute:
            updated.extend([dict(id='viewing',x=encounter['x'],y=encounter['y'],minute=minute,activity='到达屏幕附近'),
                            dict(id='viewing',x=encounter['x'],y=encounter['y'],minute=minute+delay,activity='停留观看屏幕')])
            inserted=True
        updated.append({**point,'minute':point['minute']+delay if inserted else point['minute']})
    result.update(waypoints=updated,end_minute=result['end_minute']+delay,viewing_stop_seconds=decision['dwell_seconds'])
    return result
