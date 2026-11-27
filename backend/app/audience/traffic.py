"""Synthetic traffic and deterministic opportunity events; not measured impressions."""
import math
import random
from .cohorts import apportioned
from .mobility import journey,RoutePlanner

DEFAULT = dict(pedestrians_per_agent=4, vehicles_per_hour=1200)
VEHICLES = [dict(kind='car',label='轿车',color='#81b5dd',length=22,occupancy=(1,4)),
            dict(kind='taxi',label='出租车',color='#f5cf71',length=22,occupancy=(1,3)),
            dict(kind='bus',label='公交车',color='#86c7a5',length=38,occupancy=(8,30)),
            dict(kind='van',label='厢式车',color='#cab9da',length=28,occupancy=(1,2))]
VARIANTS = [('everyday','日常出行'),('backpack','随身背包'),('shopping','提袋出行'),('phone','查看手机'),('briefcase','携带公文包'),('stroll','轻装散步')]


def validate_traffic(value=None):
    if value is None:value={}
    if not isinstance(value,dict):raise ValueError('车辆与人群展开配置须为对象')
    result={}
    for key,minimum,maximum in [('pedestrians_per_agent',1,10),('vehicles_per_hour',0,3000)]:
        v=value.get(key,DEFAULT[key])
        if type(v) is not int or not minimum<=v<=maximum:raise ValueError(f'{key} 必须为 {minimum}–{maximum} 的整数')
        result[key]=v
    return result


def roadside_screens(existing):
    used={s['id'] for s in existing};result=[]
    for i,(x,y) in enumerate([(340,325),(815,395)],1):
        sid=f'SYNTHETIC-ROAD-{i}'
        while sid in used:sid+='-extra'
        used.add(sid)
        result.append(dict(id=sid,name=f'沿街广告牌 {i}',x=x,y=y,venue='合成道路广告牌',visibility=None,obstruction=0,
                           view_radius=105,creative='城市生活',creative_label='示例广告 · 非实际投放',
                           source='合成演示新增；不属于上传库存或预算推荐'))
    return result


def opportunities(points,screens,default_radius):
    """Once per outing/screen, at closest passage, including stationary segments."""
    result=[]
    for screen in screens:
        best=None
        for a,b in zip(points,points[1:]):
            dx,dy=b['x']-a['x'],b['y']-a['y'];denom=dx*dx+dy*dy
            t=max(0,min(1,((screen['x']-a['x'])*dx+(screen['y']-a['y'])*dy)/denom)) if denom else 0
            x,y=a['x']+t*dx,a['y']+t*dy;distance=math.hypot(x-screen['x'],y-screen['y'])
            if best is None or distance<best['distance']:
                best=dict(screen_id=screen['id'],minute=round(a['minute']+t*(b['minute']-a['minute']),5),distance=distance)
        if best and best['distance']<=screen.get('view_radius',default_radius):
            result.append({**best,'distance':round(best['distance'],3)})
    return result


def vehicles(slot,seed,base_count):
    factor={'quiet':.18,'morning':1.5,'evening':1.6,'night':1.2,'daytime':1.}.get(slot.get('period'),1.)
    count=min(9000,round(base_count*factor*slot.get('activity_factor',1.)))
    rng=random.Random(f'traffic:{seed}:{slot["round"]}');result=[]
    # Common lane speed and staggered arrivals avoid cars overtaking on one lane.
    for direction,lane_count in zip((1,-1),apportioned(count,[1,1]) if count else (0,0)):
        speed=round(rng.uniform(24,36),2);duration=1040*.6/(speed/3.6)/60
        for index in range(lane_count):
            definition=rng.choices(VEHICLES,[48,22,12,18])[0];occupants=rng.randint(*definition['occupancy'])
            start=(index+rng.uniform(.1,.4))*(59.9-duration)/max(1,lane_count)
            y=346 if direction==1 else 374;x0,x1=(-20,1020) if direction==1 else (1020,-20)
            points=[dict(x=x0,y=y,minute=start,activity='驶入街区'),dict(x=x1,y=y,minute=start+duration,activity='驶离街区')]
            result.append(dict(id=f'v-{slot["round"]}-{direction}-{index}',**{k:v for k,v in definition.items() if k!='occupancy'},
                               occupants=occupants,speed_kmh=speed,direction=direction,
                               journey=dict(start_minute=start,end_minute=start+duration,waypoints=points,purpose='沿街车辆通行'),
                               source='情景生成的车辆与载客数；不代表实测交通，也未调用 LLM 判断司机或乘客观看'))
    return result


def build_traffic(scene,options=None,snapshots=None):
    options=validate_traffic(options if options is not None else scene.get('traffic_options'))
    if 'neighborhood' not in scene:raise ValueError('该旧运行没有步行路网，请重新预览或运行')
    screens=list(scene['screens']) if scene['neighborhood'].get('geographic') else [*scene['screens'],*roadside_screens(scene['screens'])];frames=[];events=[]
    from .traffic_network import route_pool,connected_vehicles
    pool=route_pool(scene['neighborhood'],scene['seed']) if scene['neighborhood'].get('geographic') and options['vehicles_per_hour'] else []
    planner=RoutePlanner(scene['neighborhood'],scene['seed'])
    recorded={s['round']:s for s in (snapshots or []) if s['round']>0}
    for index,trips in enumerate(scene['mobility_rounds']):
        slot=scene.get('schedule',[dict(round=i+1,period='daytime') for i in range(scene['rounds'])])[index]
        actors=[]
        for parent in scene['agents']:
            trip=trips.get(str(parent['id']))
            if not trip:continue
            n=min(options['pedestrians_per_agent'],parent['represented_population'])
            weights=apportioned(parent['represented_population'],[1]*n)
            for variant,weight in enumerate(weights):
                aid=f'p-{parent["id"]}-{variant}'
                profile={**parent,'id':aid}
                if variant==0:
                    profile_trip=next((a['journey'] for a in recorded.get(index+1,{}).get('agents',[]) if a['id']==parent['id'] and a.get('journey')),trip)
                else:profile_trip=journey(profile,slot,scene['seed'],scene['neighborhood'],scene['mobility'],scene['screens'],planner=planner)
                appearance,label=VARIANTS[(parent['id']+variant)%len(VARIANTS)]
                actor=dict(id=aid,parent_agent_id=parent['id'],name=f'{parent["name"]} · 行人 {variant+1}',group=parent['group'],color=parent['color'],represented_population=weight,
                           appearance=appearance,variant_label=label,journey=profile_trip,
                           decision_source='原代表路线' if variant==0 else '同画像群体的规则展开路线；未额外调用 OASIS')
                actors.append(actor)
                for encounter in opportunities(profile_trip['waypoints'],screens,scene['neighborhood']['view_radius']):
                    events.append(dict(**encounter,id=f'{index+1}:{aid}:{encounter["screen_id"]}',round=index+1,actor_id=aid,kind='pedestrian',count=weight,units=1))
        cars=connected_vehicles(slot,scene['seed'],options['vehicles_per_hour'],scene['neighborhood'],pool=pool) if scene['neighborhood'].get('geographic') else vehicles(slot,scene['seed'],options['vehicles_per_hour'])
        for car in cars:
            for encounter in opportunities(car['journey']['waypoints'],screens,scene['neighborhood']['view_radius']):
                events.append(dict(**encounter,id=f'{index+1}:{car["id"]}:{encounter["screen_id"]}',round=index+1,actor_id=car['id'],kind='vehicle',count=car['occupants']*car.get('represented_vehicles',1),units=car.get('represented_vehicles',1)))
        frames.append(dict(round=index+1,pedestrians=actors,vehicles=cars,
                           represented_pedestrians=sum(a['represented_population'] for a in actors)))
    events.sort(key=lambda e:(e['round'],e['minute'],e['id']))
    return dict(schema_version=2,options=options,screens=screens,frames=frames,events=events,
                counter_label='模拟 Impressions · 曝光机会',
                formula='行人分配权重 + 经过车辆的假设载客人数（含驾驶员）；每趟行程、每块广告牌最多一次；跨屏与跨小时不去重。',
                assumptions='进入合成半径仅代表几何曝光机会，不保证视线、注意、广告播放或观看；屏幕假定双面。车辆载客数、速度、车流与新增广告牌均为情景假设，不是库存或实测客流；路口等待为情景假设，未校准信号、车道、避碰与公交上下客。',
                replay_policy='按当前回放时刻重新求累计值；暂停不增加，倒放会减少，每次全天循环从零重播，不重复增加原始事件。',
                actor_policy='展开行人分摊原代表权重，不增加总人口或 OASIS 独立样本；车辆人群单独建模，不能与步行人口合并声称去重覆盖。')


def geographic_vehicles(slot,seed,base_count,network):
    """Backward-compatible entry point; use contiguous, access-aware road routes."""
    from .traffic_network import connected_vehicles
    return connected_vehicles(slot,seed,base_count,network)
