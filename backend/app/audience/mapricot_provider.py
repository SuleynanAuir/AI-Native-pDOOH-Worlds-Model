"""Mapricot only: server-side SDK, bounded map downloads, source-preserving adapters."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
import uuid
from urllib.parse import urlparse, urlencode
from .geolocation import distance_m

BASE = 'https://api.mapricot.com'
TTL = 7 * 86400


def enabled(config):
    if not config.get('LOCATION_LOOKUP_ENABLED') or config.get('LOCATION_PROVIDER') != 'mapricot':
        raise ValueError('Mapricot 查询未启用；不会改用其他地图服务')
    if not config.get('MAPRICOT_API_KEY'):raise ValueError('请在服务端配置 MAPRICOT_API_KEY')


def cached(cache, signature, fetch):
    path=Path(cache)/(hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and time.time()-path.stat().st_mtime<TTL:return json.loads(path.read_text())
    result=fetch()
    temp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False));temp.replace(path)
    return result


def lookup(point, radius, config, cache):
    enabled(config)
    def fetch():
        from mapricot import Mapricot
        import os, certifi
        # python.org macOS builds may lack a system CA bundle. Keep TLS verification enabled.
        os.environ.setdefault('SSL_CERT_FILE',certifi.where())
        client=Mapricot(config['MAPRICOT_API_KEY'],timeout=35,max_retries=1)
        try:
            reverse=client.geocoding.reverse(point['lat'],point['lon'],limit=1,lang='en')
            nearby=client.places.nearby(point['lat'],point['lon'],radius=radius,limit=20,lang='en')
        except Exception as exc:
            code=getattr(exc,'status',getattr(exc,'status_code',None))
            raise ValueError('Mapricot 查询失败'+(f'（HTTP {code}）' if code else '，请检查网络与密钥权限')) from None
        for value in (reverse,nearby):
            if not isinstance(value,dict) or not isinstance(value.get('results'),list):raise ValueError('Mapricot 返回格式无效')
        candidates=[p for p in reverse['results'] if valid_place(p)]
        if not candidates:raise ValueError('Mapricot 未返回可用地址；保留坐标，不猜测城市')
        address=candidates[0]
        # An administrative result is useful context, but never an exact address.
        exact=address.get('type') in ('address','street')
        offset=distance_m(point['lat'],point['lon'],address['lat'],address['lon'])
        if exact and offset>max(radius,500):raise ValueError('Mapricot 返回地址离屏幕过远，需人工核对')
        pois=[]
        for p in nearby['results']:
            if not valid_place(p):continue
            dist=distance_m(point['lat'],point['lon'],p['lat'],p['lon'])
            if dist>radius+2:continue
            pois.append({k:p[k] for k in ('id','name','label','type','lat','lon','address','categories','source') if k in p}|{'distance_m':round(dist,1)})
        return dict(address=address,pois=sorted(pois,key=lambda p:(p['distance_m'],p['id'])),radius_m=radius,
                    queried_at=datetime.now(timezone.utc).isoformat(),address_granularity=address.get('type'),address_distance_m=round(offset,1),
                    attribution=reverse.get('attribution',[])+nearby.get('attribution',[]),
                    coverage='最近最多 20 个返回设施；不是区域完整清单，数量不能用作客流或行业占比。')
    return cached(cache,['mapricot-sdk-v1',point['lat'],point['lon'],radius],fetch)


def valid_place(p):
    return (isinstance(p,dict) and isinstance(p.get('id'),str) and type(p.get('lat')) in (int,float)
            and type(p.get('lon')) in (int,float) and -90<=p['lat']<=90 and -180<=p['lon']<=180)


def tile_bytes(path,config,authenticated=False):
    """Only caller-built paths on the provider's fixed host; never an arbitrary URL proxy."""
    import requests
    enabled(config)
    if not path.startswith('/tiles/v1/') or '..' in path or '?' in path:raise ValueError('地图路径无效')
    try:
        with requests.get(BASE+path,params={'key':config['MAPRICOT_API_KEY']} if authenticated else None,
                          timeout=(10,35),allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise ValueError(f'Mapricot 地图返回 HTTP {response.status_code}，请确认 tiles 权限')
            content=bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content)>12_000_000:raise ValueError('地图响应超过大小限制')
            return bytes(content)
    except requests.RequestException:raise ValueError('Mapricot 地图连接失败') from None


def map_document(kind,config):
    if kind not in ('style','tilejson'):raise ValueError('地图文档类型无效')
    path='/tiles/v1/styles/dark.json' if kind=='style' else '/tiles/v1/planet.json'
    value=json.loads(tile_bytes(path,config,True))
    # Styles contain the server key in a TileJSON URL. Rewrite before returning ANY data.
    def clean(v):
        if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
        if isinstance(v,list):return [clean(x) for x in v]
        if isinstance(v,str) and v.startswith(BASE+'/tiles/v1/planet.json'):return '/api/world/mapricot/tilejson'
        if isinstance(v,str):return v.replace(config['MAPRICOT_API_KEY'],'')
        return v
    return clean(value)


def tile_xy(lat,lon,z=15):
    lat=max(-85.0511287,min(85.0511287,lat));n=2**z
    return (lon+180)/360*n,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n


def local_geometry(point,radius,config,cache):
    """Decode just the selected viewport, not a bulk regional tile export."""
    import mapbox_vector_tile
    from shapely.geometry import LineString, box
    from shapely.ops import unary_union
    lat,lon=point['lat'],point['lon'];z=15;n=2**z
    if abs(lat)>80:raise ValueError('当前局部投影不支持极区，请使用区域地图查看')
    dy=radius/111195;dx=dy/math.cos(math.radians(lat))
    west,north=tile_xy(lat+dy,lon-dx);east,south=tile_xy(lat-dy,lon+dx)
    tiles=[(x,y) for x in range(math.floor(west),math.floor(east)+1) for y in range(math.floor(north),math.floor(south)+1)]
    if len(tiles)>12:raise ValueError('局部地图瓦片过多，请缩小半径')
    clip=box(lon-dx,lat-dy,lon+dx,lat+dy);features=[];roads=defaultdict(list);seen=set()
    def converted(coords,x,y,extent):
        return [( (x+px/extent)/n*360-180, math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+1-py/extent)/n))))) for px,py in coords]
    for x,y in tiles:
        def fetch():return mapbox_vector_tile.decode(tile_bytes(f'/tiles/v1/planet/{z}/{x}/{y}.mvt',config))
        tile=cached(cache,['mapricot-mvt-v1',z,x,y],fetch)
        for layer in ('roads','buildings','landuse','pois'):
            content=tile.get(layer,{});extent=content.get('extent',4096)
            for f in content.get('features',[]):
                p=f.get('properties',{});g=f['geometry'];typ=g['type'];raw=g['coordinates']
                parts=[raw] if typ in ('LineString','Point') else raw if typ in ('MultiLineString','Polygon') else [r for poly in raw for r in poly] if typ=='MultiPolygon' else []
                if typ=='Point':parts=[[raw]]
                for part in parts:
                    coords=converted(part,x,y,extent)
                    if not coords or not any(lon-dx<=a<=lon+dx and lat-dy<=b<=lat+dy for a,b in coords):continue
                    digest=hashlib.sha256(json.dumps([layer,coords,p],sort_keys=True).encode()).hexdigest()[:18]
                    if digest in seen:continue
                    seen.add(digest);fid='mapricot-tile-'+digest
                    tags={'name':str(p['name'])[:200]} if p.get('name') else {}
                    if layer=='roads' and typ in ('LineString','MultiLineString') and len(coords)>1:
                        kind=p.get('kind_detail') or {'minor_road':'residential','major_road':'primary','path':'path','highway':'motorway'}.get(p.get('kind'))
                        if not kind:continue
                        tags.update(highway=kind)
                        for k in ('access','oneway'):
                            if p.get(k) is not None:tags[k]=str(p[k])
                        level=(bool(p.get('is_bridge')),bool(p.get('is_tunnel')),p.get('layer',0))
                        if level[0]:tags['bridge']='yes'
                        if level[1]:tags['tunnel']='yes'
                        line=LineString(coords).intersection(clip)
                        if not line.is_empty and line.geom_type in ('LineString','MultiLineString'):roads[level].append((line,tags,fid))
                        continue
                    if layer=='buildings':tags['building']=str(p.get('kind_detail') or 'yes')
                    elif layer=='landuse':tags['landuse']=str(p.get('kind') or 'unknown')
                    elif layer=='pois':
                        category=str(p.get('kind_detail') or p.get('kind') or 'unknown');tags['map_category']=category
                        if category in ('cafe','restaurant','fast_food','library','pharmacy','community_centre','post_office','bank','townhall','courthouse'):tags['amenity']=category
                        elif category in ('supermarket','convenience','clothes','mall'):tags['shop']=category
                        elif category in ('bus_stop','station','tram_stop'):tags['public_transport']='platform'
                        elif category=='park':tags['leisure']='park'
                    features.append(feature(fid,tags,coords,point))
    # Cartographic lines do not retain OSM node IDs. Node only equal-level intersections.
    # This is a geometry-derived network, explicitly not a verified pedestrian routing graph.
    for level,group in roads.items():
        merged=unary_union([r[0] for r in group]);lines=list(merged.geoms) if hasattr(merged,'geoms') else [merged]
        for i,line in enumerate(lines):
            if line.geom_type!='LineString' or line.length<1e-8:continue
            mid=line.interpolate(.5,normalized=True);original=min(group,key=lambda r:r[0].distance(mid))
            coords=list(line.coords);fid=original[2]+'-'+str(i)
            f=feature(fid,original[1],coords,point)
            # Keep grade-separated intersections disconnected.
            f['nodes']=['tile-'+hashlib.sha256(f'{level}:{a:.7f},{b:.7f}'.encode()).hexdigest()[:20] for a,b in coords]
            features.append(f)
    features.sort(key=lambda f:f['distance_m'])
    if not any(f['tags'].get('highway') for f in features):raise ValueError('Mapricot 局部瓦片没有可用道路；仅提供区域地图，不生成虚构路网')
    return features


def feature(fid,tags,coords,point):
    return dict(id=fid,tags=tags,geometry=[dict(lon=a,lat=b) for a,b in coords],nodes=[],
                distance_m=round(min(distance_m(point['lat'],point['lon'],b,a) for a,b in coords),1),url='https://mapricot.com/docs/map-tiles/')


def evidence(point,radius,config,cache):
    value=lookup(point,radius,config,cache);addr=value['address'];a=addr.get('address',{})
    reverse=dict(lat=addr['lat'],lon=addr['lon'],display_name=addr.get('label'),type=addr.get('type'),address=dict(country=a.get('country',''),city=a.get('locality') or a.get('region',''),road=a.get('street',''),state=a.get('region',''),postcode=a.get('postalCode','')))
    features=local_geometry(point,radius,config,Path(cache)/'tiles')
    for poi in value['pois']:
        f=feature(poi['id'],dict(name=poi.get('name',poi['id']),map_category=', '.join(poi.get('categories',[])) or '未分类设施'),[(poi['lon'],poi['lat'])],point)
        f['url']=BASE+'/places/v1/'+poi['id'];features.append(f)
    features.sort(key=lambda f:f['distance_m'])
    attribution=list(dict.fromkeys(a['text'] for a in value['attribution'] if a.get('text')))
    return dict(provider='mapricot',reverse=reverse,features=features,pois=value['pois'],queried_at=value['queried_at'],radius_m=radius,
                reverse_source=BASE+'/geocoding/v1/reverse?'+urlencode(dict(lat=point['lat'],lon=point['lon'],limit=1)),
                overpass_source='',attribution='Mapricot · '+' · '.join(attribution),
                geometry_basis='Mapricot / OSM 地图瓦片几何；按同层交点构建展示行程，不等同于道路导航或实测人行道',
                limitations=[value['coverage'],'瓦片为制图几何，可能简化道路与建筑；交叉连接、入口、通行权限与单行方向可能不完整，不能用于导航。','地图不能证明实时营业、人口结构、文化、收入、客流、遮挡或广告视线；人数与反应仍为情景假设。'])
