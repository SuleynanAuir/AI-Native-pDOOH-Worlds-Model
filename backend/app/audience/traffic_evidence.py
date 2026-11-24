"""Road-boundary geometry and geographically scoped public traffic references."""
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from .geolocation import map_evidence
from .geographic_scene import DRIVABLE


def road_key(name):
    value=name.lower().replace('street','st').replace('avenue','ave').replace('boulevard','blvd')
    value=re.sub(r'\b0+(\d+)',r'\1',value)
    return re.sub(r'[^a-z0-9]','',value)


def boundary_roads(area, features):
    point=area['coordinate'];radius=area['radius_m'];roads={};seen=set()
    def xy(g):return ((g['lon']-point['lon'])*111195*math.cos(math.radians(point['lat'])),(g['lat']-point['lat'])*111195)
    for f in features:
        tags=f.get('tags',{});kind=tags.get('highway')
        if kind not in DRIVABLE or tags.get('access') in ('no','private') or tags.get('motor_vehicle') in ('no','private') or tags.get('motorcar')=='no':continue
        name=tags.get('name') or ('未命名道路 '+f['id']);key=road_key(name)
        road=roads.setdefault(key,{'id':'road-'+key,'name':name,'classes':set(),'incoming_portals':0,'oneway_unknown':False,'lanes':set(),'source_ids':set()})
        road['classes'].add(kind);road['source_ids'].add(f['id'])
        if tags.get('lanes'):road['lanes'].add(tags['lanes'])
        oneway=str(tags.get('oneway','')).lower();road['oneway_unknown'] |= oneway not in ('yes','true','1','-1','no','false','0')
        points=[xy(g) for g in f.get('geometry',[])]
        for a,b in zip(points,points[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];aa=dx*dx+dy*dy
            if aa<.01:continue
            bb=2*(a[0]*dx+a[1]*dy);cc=a[0]**2+a[1]**2-radius**2;disc=bb*bb-4*aa*cc
            if disc<=1e-8:continue
            for t in ((-bb-math.sqrt(disc))/(2*aa),(-bb+math.sqrt(disc))/(2*aa)):
                if not -1e-8<=t<=1+1e-8:continue
                px,py=a[0]+t*dx,a[1]+t*dy
                inward=(px*dx+py*dy)<0
                if oneway in ('yes','true','1') and not inward:continue
                if oneway=='-1' and inward:continue
                marker=(key,round(px/3),round(py/3),tags.get('layer'),tags.get('bridge'),tags.get('tunnel'))
                if marker in seen:continue
                seen.add(marker);road['incoming_portals']+=1
    result=[]
    for road in roads.values():
        if not road['incoming_portals']:continue
        for k in ('classes','lanes','source_ids'):road[k]=sorted(road[k])
        road['source_feature_count']=len(road['source_ids']);road['source_ids']=road['source_ids'][:3]
        result.append(road)
    return sorted(result,key=lambda x:x['id'])


def ground_region(area, config):
    if not config.get('LOCATION_LOOKUP_ENABLED'):raise ValueError('需要启用地图查询，以核实区域道路入口后估算车流')
    root=Path(config['UPLOAD_FOLDER'])/'geolocations'/'map-cache'
    # A larger map window keeps the 400m counting boundary inside the geometry.
    evidence=map_evidence(area['coordinate'],600,config,root)
    roads=boundary_roads(area,evidence['features'])
    if not roads:raise ValueError('地图未提供足够的区域入口道路，不能凭地址编造区域总车流')
    references=[];point=area['coordinate'];city=evidence.get('reverse',{}).get('address',{}).get('city','')
    in_sf=city.casefold()=='san francisco' and 37.70<=point['lat']<=37.84 and -122.53<=point['lon']<=-122.35
    if in_sf:
        data=json.loads((Path(__file__).parent/'data'/'sfcta_2025_counts.json').read_text())
        names={road_key(r['name']) for r in roads}
        for row in data['counts']:
            primary=re.split(' between ',row['location'],flags=re.I)[0]
            if road_key(primary) in names:
                references.append({**row,'road_name':primary,'source_url':data['source_url'],'match':'same_named_corridor_not_verified_same_segment','limitation':'历史同名道路断面参考，不代表当前区域边界实测，不能直接相加为区域流量'})
    for road in roads:
        road['reference_ids']=[r['id'] for r in references if road_key(r['road_name'])==road_key(road['name'])]
    return {'roads':roads,'references':references,'map_source':evidence.get('reverse_source'),'map_queried_at':evidence.get('queried_at'),'attribution':evidence.get('attribution'),'resolved_city':city,
            'count_definition':'400m circular boundary inbound vehicle crossings per hour, summed across distinct inbound portals; not internal road-segment counts',
            'limitations':['地图入口数不是实测容量；未知单向按可能双向保留，可能高估入口。','官方断面计数为2025年方向性工作日日流量，仅用作量级参考；不同路段、方向、年份不可直接代替区域进入车流。','未统计完全在区域内部发起且不穿过边界的行程；区域之间不可相加为去重车辆。',*evidence.get('limitations',[])]}
