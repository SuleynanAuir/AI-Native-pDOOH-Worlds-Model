"""Seeded synthetic encounters, not measured audiences or conversion forecasts."""
import math
import random
from collections import Counter


DEFAULT_GROUPS = [
    dict(id='commuter', name='通勤路人', share=0.4, mobility='walking', dwell_seconds=4, attention=0.35, interest=0.3),
    dict(id='shopper', name='购物消费者', share=0.3, mobility='walking', dwell_seconds=15, attention=0.65, interest=0.6),
    dict(id='waiting', name='候车观众', share=0.2, mobility='waiting', dwell_seconds=40, attention=0.7, interest=0.4),
    dict(id='passenger', name='乘车经过者', share=0.1, mobility='vehicle', dwell_seconds=2, attention=0.25, interest=0.2),
]


def number(value, name, low, high):
    if isinstance(value, bool):
        raise ValueError(f'{name} 必须是数字')
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{name} 必须是数字') from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} 必须在 {low} 与 {high} 之间')
    return value


def simulate(payload):
    if not isinstance(payload, dict):
        raise ValueError('请求必须是对象')
    screens, groups = payload.get('screens'), payload.get('groups')
    if not isinstance(screens, list) or not 1 <= len(screens) <= 100:
        raise ValueError('请提供 1–100 块屏幕')
    if not isinstance(groups, list) or not 1 <= len(groups) <= 30:
        raise ValueError('请提供 1–30 个代表性群体')
    count = number(payload.get('population', 1000), 'population', 1, 10000)
    seed = number(payload.get('seed', 42), 'seed', 0, 2147483647)
    if not count.is_integer() or not seed.is_integer():
        raise ValueError('population 和 seed 必须是整数')
    count, seed = int(count), int(seed)
    if count * len(screens) > 200000:
        raise ValueError('总相遇次数不能超过 200000')
    normalized = []
    ids = set()
    for g in groups:
        if not isinstance(g, dict) or not isinstance(g.get('id'), str) or not g['id'].strip() or g['id'] in ids:
            raise ValueError('群体 id 必须是唯一非空字符串')
        ids.add(g['id'])
        if g.get('mobility') not in ('walking', 'waiting', 'vehicle'):
            raise ValueError('mobility 必须是 walking、waiting 或 vehicle')
        normalized.append({**g, **{k: number(g.get(k), k, 0, high) for k, high in [('share', 1), ('attention', 1), ('interest', 1), ('dwell_seconds', 600)]}})
    if sum(g['share'] for g in normalized) <= 0:
        raise ValueError('群体占比总和必须大于零')
    cleaned, ids = [], set()
    for s in screens:
        if not isinstance(s, dict):
            raise ValueError('每块屏幕必须是对象')
        sid = s.get('VIOOH_ID', s.get('id'))
        if not isinstance(sid, str) or not sid.strip() or sid in ids:
            raise ValueError('屏幕 id 必须是唯一非空字符串')
        ids.add(sid)
        cleaned.append({**s, 'id': sid, **{k: number(s.get(k), k, low, high) for k, low, high in [('visibility', 0, 1), ('obstruction', 0, 1), ('viewing_distance', 0.1, 1000), ('physical_height', 0.01, 100), ('slot_seconds', 0.1, 600)]}})
    rng = random.Random(seed)
    agents = rng.choices(normalized, weights=[g['share'] for g in normalized], k=count)
    results, examples = [], []
    for s in cleaned:
        totals, per_group = Counter(), {g['id']: Counter() for g in normalized}
        # Angular size proxy; 0.05 rad is an explicit heuristic, not calibration.
        legibility = min(1, s['physical_height'] / s['viewing_distance'] / 0.05)
        for aid, g in enumerate(agents):
            dwell = g['dwell_seconds'] * rng.uniform(0.6, 1.4)
            p_notice = s['visibility'] * (1 - s['obstruction']) * legibility * g['attention']
            noticed = rng.random() < p_notice
            watched = noticed and dwell >= s['slot_seconds']
            interested = watched and payload.get('creative_supplied') is True and rng.random() < g['interest']
            reaction = 'interested' if interested else 'watched' if watched else 'glanced' if noticed else 'ignored'
            for tally in (totals, per_group[g['id']]):
                tally['encounters'] += 1
                tally[reaction] += 1
                tally['noticed'] += int(noticed)
                tally['full_view'] += int(watched)
            if len(examples) < 200:
                examples.append(dict(agent_id=aid, group_id=g['id'], screen_id=s['id'], reaction=reaction, opportunity_seconds=round(dwell, 2), notice_probability=round(p_notice, 4), reason=f"{g['mobility']}；可见性 {s['visibility']}；遮挡 {s['obstruction']}；观看机会 {dwell:.1f}s / 展示 {s['slot_seconds']}s"))
        results.append(dict(screen_id=s['id'], totals=dict(totals), notice_rate=totals['noticed']/count, full_view_rate=totals['full_view']/count, groups=[dict(group_id=g['id'], name=g.get('name', g['id']), counts=dict(per_group[g['id']])) for g in normalized]))
    return dict(engine='audience-encounters-v1', seed=seed, population=count, screens=results, examples=examples, assumptions=[
        '所有结果均为未校准的合成情景，不是真实客流、广告效果或购买预测。',
        '每位合成路人与每块屏幕相遇一次；各屏幕曝光不可相加为去重触达。',
        '群体比例与行为参数由用户配置；未从全国社会学结论自动推断个人。',
        '可见性、遮挡与物理尺寸需人工结合现场照片填写；像素尺寸不能替代物理尺寸。',
        '完整观看仅表示观看机会覆盖展示时长，不代表理解或记忆。',
        '未提供创意时不模拟兴趣；提供时兴趣也只是用户设定的条件概率。',
    ], inputs=dict(screens=cleaned, groups=normalized, creative_supplied=payload.get('creative_supplied') is True, evidence=payload.get('evidence', '未提供资料，参数为情景假设')))
