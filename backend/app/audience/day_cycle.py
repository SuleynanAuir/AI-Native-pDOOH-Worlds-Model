"""Editable 24-hour scenarios, explicitly synthetic rather than traffic data."""
from copy import deepcopy
from datetime import date, timedelta
import math
import random

PERIODS = {'morning': {'start': 7, 'end': 10}, 'evening': {'start': 17, 'end': 19}, 'night': {'start': 19, 'end': 23}}
LABELS = {'morning': '上班高峰', 'evening': '下班高峰', 'night': '夜间消费', 'daytime': '日间活动', 'quiet': '深夜 / 清晨'}
HOLIDAYS = [
    dict(id='ordinary', name='普通工作日', description='常规通勤、日常采购和夜间休闲情景', commute_factor=1., leisure_factor=1.),
    dict(id='christmas', name='圣诞节', description='合成节日情景：礼品采购、家庭聚会、节庆出游；不假定每个人庆祝', commute_factor=.65, leisure_factor=1.5),
    dict(id='new_year', name='元旦 / 跨年', description='合成节日情景：聚会、夜间活动与休闲消费', commute_factor=.6, leisure_factor=1.6),
    dict(id='spring_festival', name='春节', description='合成节日情景：家庭团聚、走访与节日采购；地区差异需校正', commute_factor=.4, leisure_factor=1.35),
    dict(id='national_day', name='国庆假期', description='合成节日情景：出游、家庭活动和商圈消费', commute_factor=.5, leisure_factor=1.5),
    dict(id='black_friday', name='黑色星期五', description='合成购物活动情景：消费者可能比较价格或采购，不保证实际购买', commute_factor=.95, leisure_factor=1.7),
    dict(id='custom', name='自定义节日 / 活动', description='用户自定义的当地节日或活动假设', commute_factor=1., leisure_factor=1.2),
]
DEFAULT = dict(days=1, start_date='', periods=PERIODS, holiday={**HOLIDAYS[0], 'start_hour': 0, 'end_hour': 24})
BASE_ACTIVITY = {'morning': .72, 'evening': .8, 'night': .62, 'daytime': .35, 'quiet': .05}


def window_hours(start, end):
    return set(range(start, end)) if end > start else set(range(start, 24)) | set(range(end))


def validate_window(value, label):
    if not isinstance(value, dict): raise ValueError(f'{label}需要起止小时')
    start, end = value.get('start'), value.get('end')
    if type(start) is not int or type(end) is not int or not 0 <= start <= 23 or not 1 <= end <= 24 or start == end:
        raise ValueError(f'{label}起点为 0–23、终点为 1–24，且不能相同')
    return dict(start=start, end=end)


def validate_day_cycle(value):
    if not isinstance(value, dict): raise ValueError('需要有效的全天模拟配置')
    result = deepcopy(DEFAULT)
    days = value.get('days', 1)
    if type(days) is not int or not 1 <= days <= 3: raise ValueError('模拟天数必须为 1–3 的整数')
    result['days'] = days
    start = value.get('start_date', '')
    if not isinstance(start, str): raise ValueError('日期须为 YYYY-MM-DD 或留空')
    if start:
        try:
            parsed = date.fromisoformat(start)
            if parsed.isoformat() != start: raise ValueError()
            parsed + timedelta(days=days-1)
        except (ValueError, OverflowError): raise ValueError('日期须为有效的 YYYY-MM-DD')
    result['start_date'] = start
    periods = value.get('periods', PERIODS)
    if not isinstance(periods, dict) or set(periods) != set(PERIODS): raise ValueError('请配置上班、下班和夜间三个时段')
    occupied = set()
    for key in PERIODS:
        result['periods'][key] = validate_window(periods[key], LABELS[key])
        hours = window_hours(**result['periods'][key])
        if hours & occupied: raise ValueError('高峰与夜间时段不能重叠')
        occupied |= hours
    holiday = value.get('holiday', {})
    if not isinstance(holiday, dict): raise ValueError('节日配置必须为对象')
    preset = next((p for p in HOLIDAYS if p['id'] == holiday.get('id', 'ordinary')), None)
    if preset is None: raise ValueError('不支持的节日，请选择自定义活动')
    result['holiday'] = {**preset, **{k: holiday[k] for k in ('name', 'description', 'commute_factor', 'leisure_factor') if k in holiday}}
    for field in ('name', 'description'):
        text = result['holiday'][field]
        if not isinstance(text, str) or not text.strip() or len(text) > (100 if field == 'name' else 1000): raise ValueError('请填写有效的节日名称和情景说明')
    for field in ('commute_factor', 'leisure_factor'):
        v = result['holiday'][field]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not .1 <= v <= 3: raise ValueError('节日活动系数必须在 0.1–3 之间')
    window = validate_window(dict(start=holiday.get('start_hour', 0), end=holiday.get('end_hour', 24)), '节日有效时段')
    result['holiday'].update(start_hour=window['start'], end_hour=window['end'])
    return result


def schedule(config):
    result = []
    holiday = config['holiday']
    for day in range(config['days']):
        stamp = (date.fromisoformat(config['start_date']) + timedelta(days=day)).isoformat() if config['start_date'] else f'第 {day+1} 天'
        for hour in range(24):
            period = next((k for k, w in config['periods'].items() if hour in window_hours(**w)), 'daytime' if 6 <= hour < 23 else 'quiet')
            active_holiday = holiday['id'] != 'ordinary' and hour in window_hours(holiday['start_hour'], holiday['end_hour'])
            factor = (holiday['commute_factor'] if period in ('morning', 'evening') else holiday['leisure_factor']) if active_holiday else 1.
            result.append(dict(round=len(result)+1, day=day+1, date=stamp, hour=hour, time=f'{hour:02d}:00',
                               period=period, period_label=LABELS[period], holiday_active=active_holiday,
                               holiday_name=holiday['name'] if active_holiday else '', holiday_description=holiday['description'] if active_holiday else '',
                               activity_factor=factor, base_activity=BASE_ACTIVITY[period],
                               source='用户可修改的时间与节日情景假设；不是客流预测或法定假日日历'))
    return result


def attendance(profile, slot, seed):
    """Sample encounter opportunity, not an LLM reaction; retain absent agents."""
    group = profile['group']
    commuter = group in ('early_career', 'professional', 'young_couple', 'flex_worker', 'student')
    family = group in ('parents', 'caregiver', 'value_family', 'retired')
    relative = 1.2 if slot['period'] in ('morning', 'evening') and commuter else .7 if slot['period'] == 'morning' else .75 if slot['period'] == 'night' and family else 1.
    if profile.get('activity_factors'):
        relative = profile['activity_factors'][slot['period']]
    probability = min(.98, max(0., slot['base_activity'] * slot['activity_factor'] * relative))
    rng = random.Random(f'attendance:{seed}:{profile["id"]}:{slot["day"]}:{slot["hour"]}')
    present = rng.random() < probability
    purpose = {'morning': '上班 / 上学通勤' if commuter else '晨间生活事务', 'evening': '下班返程或顺路采购', 'night': '晚间餐饮、休闲或生活消费', 'daytime': '日间办事、采购或出游', 'quiet': '少量夜间出行或清晨事务'}[slot['period']]
    if profile.get('local_context'):purpose=profile['local_context']['visit_purpose']
    return dict(present=present, activity_probability=round(probability, 4), purpose=purpose, relative_activity_factor=relative, factor_source='local_template_assumption' if profile.get('activity_factors') else 'legacy_scenario_assumption',
                source='时间场景调度抽样，非 LLM 决策；未出场不等于路过未注意',
                assumptions='时段基准 × 节日系数 × 群体活动系数，上限 0.98；权重不改变抽样概率')
