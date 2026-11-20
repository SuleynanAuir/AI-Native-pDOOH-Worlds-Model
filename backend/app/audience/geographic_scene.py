"""Project returned OSM geometry; never place a generic street grid over real coordinates."""
import math
from .geolocation import distance_m

WALKABLE={'residential','living_street','service','pedestrian','footway','path','steps','tertiary','secondary','primary','unclassified','road','cycleway'}
DRIVABLE={'residential','living_street','service','tertiary','secondary','primary','unclassified','road','motorway','trunk','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link'}


def geographic_network(context):
    lat,lon=context['coordinate']['lat'],context['coordinate']['lon'];radius=context['evidence']['radius_m'];scale=250/radius
    def project(g):return dict(x=round(500+(g['lon']-lon)*111195*math.cos(math.radians(lat))*scale,3),y=round(295-(g['lat']-lat)*111195*scale,3))
    def inside(p):return 35<=p['x']<=965 and 35<=p['y']<=555
    nodes={};edges={};features=[];vehicle_paths=[]
    for feature in context['evidence']['features']:
        points=[project(p) for p in feature['geometry']];tags=feature['tags'];highway=tags.get('highway')
        if any(inside(p) for p in points):features.append(dict(id=feature['id'],tags=tags,points=points,url=feature['url']))
        can_walk=highway in WALKABLE and tags.get('foot') not in ('no','private') and tags.get('access') not in ('private','no') and (highway!='cycleway' or tags.get('foot') in ('yes','designated','permissive'))
        road=[]
        for i,(a,b) in enumerate(zip(points,points[1:])):
            if not inside(a) or not inside(b):
                if len(road)>1:vehicle_paths.append(dict(id=f'{feature["id"]}-{i}',points=road,tags=tags))
                road=[];continue
            if a==b:continue
            if can_walk:
                refs=feature.get('nodes',[])
                aid=f'osm-node-{refs[i]}' if len(refs)==len(points) else f'{feature["id"]}-{i}'
                bid=f'osm-node-{refs[i+1]}' if len(refs)==len(points) else f'{feature["id"]}-{i+1}'
                nodes[aid]=dict(id=aid,**a);nodes[bid]=dict(id=bid,**b)
                edges[tuple(sorted((aid,bid)))]=dict(a=aid,b=bid,kind='sidewalk' if highway in ('footway','pedestrian','path','steps') else 'road_proxy',source_id=feature['id'])
            if highway in DRIVABLE and tags.get('motor_vehicle')!='no' and tags.get('access') not in ('private','no'):
                if not road:road=[a]
                road.append(b)
        if len(road)>1:vehicle_paths.append(dict(id=feature['id'],points=road,tags=tags))
    if len(nodes)<4:raise ValueError('返回地图缺少可连通的人行或代用道路节点，不能生成该地点的行程')
    links={k:set() for k in nodes}
    for a,b in edges:links[a].add(b);links[b].add(a)
    components=[];unvisited=set(nodes)
    while unvisited:
        stack=[min(unvisited)];component=set()
        while stack:
            node=stack.pop()
            if node in component:continue
            component.add(node);stack.extend(links[node]-component)
        unvisited-=component;components.append(component)
    nearby=[c for c in components if min(math.hypot(nodes[n]['x']-500,nodes[n]['y']-295)/scale for n in c)<150]
    connected=max(nearby or components,key=lambda c:(len(c),sorted(c)))
    if len(connected)<4:raise ValueError('屏幕附近路网组件不足以生成出行；需补充道路数据')
    nodes={k:nodes[k] for k in sorted(connected)};edges=[e for e in edges.values() if e['a'] in nodes and e['b'] in nodes]
    available=list(nodes.values())
    boundary=[]
    for score in (lambda n:n['x']+n['y'],lambda n:-n['x']+n['y'],lambda n:n['x']-n['y'],lambda n:-n['x']-n['y']):
        boundary.append(min((n for n in available if n not in boundary),key=score))
    places=[dict(id=k,node=n['id'],label=label,kind='boundary') for k,n,label in zip(('west','east','southwest','southeast'),boundary,('西北范围边界','东北范围边界','西南范围边界','东南范围边界'))]
    categories={'home':lambda t:t.get('building') in ('residential','apartments','house'),
                'office':lambda t:t.get('building') in ('office','commercial') or t.get('amenity') in ('townhall','courthouse','public_building'),
                'park':lambda t:t.get('leisure')=='park', 'shops':lambda t:bool(t.get('shop')),
                'cafe':lambda t:t.get('amenity') in ('cafe','restaurant','fast_food'),
                'services':lambda t:t.get('amenity') in ('library','pharmacy','community_centre','post_office','bank'),
                'transit':lambda t:t.get('public_transport') or t.get('highway')=='bus_stop'}
    def nearest(point):return min(available,key=lambda n:math.hypot(n['x']-point['x'],n['y']-point['y']))['id']
    for i,(key,predicate) in enumerate(categories.items()):
        feature=next((f for f in features if predicate(f['tags']) and any(inside(p) for p in f['points'])),None)
        if feature:
            point=next(p for p in feature['points'] if inside(p));name=feature['tags'].get('name') or next((feature['tags'][k] for k in ('amenity','shop','leisure','building','public_transport','highway') if k in feature['tags']),'地图设施')
            places.append(dict(id=key,node=nearest(point),label=name,kind='place',source_id=feature['id'],entrance_basis='最近网络节点代用入口，非实测门口'))
        else:places.append(dict(id=key,node=available[i%len(available)]['id'],label=f'{key} 活动点（地图未确认，仅任务假设）',kind='assumption'))
    places.append(dict(id='venue',node=nearest(dict(x=500,y=295)),label='所选 Frame 附近',kind='place',source_id='selected-frame'))
    frame=context['frame'];screen=dict(id=frame['screen_id'],name=frame['address'] or frame['screen_id'],venue=frame['venue'],x=500,y=295,visibility=None,obstruction=0,view_radius=40*scale,
                                      coordinate=context['coordinate'],source='FilteredFrames.GEOM 实际屏幕坐标；方向、高度、视线与广告内容仍未知')
    network=dict(nodes=list(nodes.values()),edges=edges,places=places,meters_per_unit=1/scale,view_radius=40*scale,geographic=True,features=features,vehicle_paths=vehicle_paths,
                 projection=dict(center=context['coordinate'],pixels_per_meter=scale),map_url=context['map_url'],attribution=context['evidence']['attribution'],
                 source=context['evidence'].get('geometry_basis','OSM 返回道路与建筑几何；部分道路中心线代用人行路线，非实测人行道/入口'),
                 assumptions='只使用选定连通组件；断开的道路不强接。出场人数、任务、步速和停留仍为合成情景；缺失场所标记为假设。车辆不模拟信号灯/避碰。')
    return network,[screen]
