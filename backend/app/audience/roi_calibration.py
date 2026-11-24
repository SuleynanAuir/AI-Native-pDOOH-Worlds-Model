"""Screen-specific incremental order rates from supplied test/control observations."""
import math
import re
from decimal import Decimal, ROUND_CEILING
from .engine import number


def validate_rows(value):
    if not isinstance(value,dict) or len(value)>10000:raise ValueError('逐屏校准数据必须为屏幕ID映射')
    out={}
    for sid,raw in value.items():
        if not isinstance(raw,dict):raise ValueError('逐屏历史数据须为对象')
        row={k:number(raw.get(k),k,lo,hi) for k,lo,hi in [
            ('test_exposures',1,1e12),('control_exposures',1,1e12),('test_orders',0,1e10),('control_orders',0,1e10),
            ('order_value',.01,1e9),('margin',0,1)]}
        if not isinstance(raw.get('currency'),str) or not re.fullmatch('[A-Z]{3}',raw['currency']):raise ValueError('逐屏校准必须提供三字母币种')
        row['currency']=raw['currency']
        row['extra_cost']=number(raw.get('extra_cost',0),'逐屏额外执行成本',0,1e12)
        row['extra_cost']=float(Decimal(str(row['extra_cost'])).quantize(Decimal('.01'),rounding=ROUND_CEILING))
        for key in ('source','period'):
            if not isinstance(raw.get(key),str) or not raw[key].strip():raise ValueError('历史校准必须注明来源及对齐的观测周期')
            row[key]=raw[key][:1000]
        # The measurement unit is an order, not a unique converted person.
        if row['test_orders']>row['test_exposures'] or row['control_orders']>row['control_exposures']:raise ValueError('订单数不能大于同口径曝光数，请检查单位')
        out[str(sid)]=row
    return out


def assumptions(roi,screen_id):
    row=roi.get('calibration',{}).get(screen_id)
    if not row:
        return dict(rates=roi['overrides'].get(screen_id,roi['rates']),order_value=roi['order_value'],margin=roi['margin'],
            incrementality=roi['incrementality'],extra_cost=0,calibrated=False,
            source=roi['source'],rate_source='逐屏情景假设' if screen_id in roi['overrides'] else '统一情景假设')
    a,b=row['test_exposures'],row['control_exposures']
    lift=(row['test_orders']/a-row['control_orders']/b)*1000
    # Approximate Poisson sensitivity band, with +1 stabilizer for zero observations.
    spread=1.96*math.sqrt((row['test_orders']+1)/a**2+(row['control_orders']+1)/b**2)*1000
    return dict(rates=dict(low=max(-1000,lift-spread),base=lift,high=min(1000,lift+spread)),order_value=row['order_value'],margin=row['margin'],incrementality=1,
        extra_cost=row['extra_cost'],calibrated=True,source=row['source'],period=row['period'],rate_source='逐屏投放/对照差值',
        method='千次增量订单=1000×(投放组订单/曝光−对照组订单/曝光)；已算增量，不再乘归因比例。低/高为近似泊松敏感区间（+1稳定项），不是因果保证。组间可比性、跨屏重复及样本独立性仍需验证。')
