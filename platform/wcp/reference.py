"""参考数据：策略说明（用户要求#4）+ 世界杯赛程进度（用户要求#3）。

策略定义同步自 3_策略分析库/核心策略清单.md 与 1_想法库/核心机会框架.md。
赛程为 2026 美加墨世界杯官方阶段时间。
"""
from datetime import date, datetime

# ---- 策略说明（卡片 tooltip + 策略页用）----
STRATEGIES = {
    "A": {
        "name": "强打弱·大分", "timing": "赛前",
        "desc": "S/A强队打C/D鱼腩，实力差≥2档，且强队有进攻动力（未锁定出线或有净胜球需求）。押大分 Over 2.5/3.5，或强队让球 -1.5。鱼腩摆大巴的场次谨慎——看赔率里的进球期望。",
    },
    "B": {
        "name": "强队确定性", "timing": "赛前",
        "desc": "押强队做「应该发生的事」——法国进R16、葡萄牙出线这类地板事件。赔率1.05–1.3x，打的是确定性不是回报，适合不想赌的场次。",
    },
    "C": {
        "name": "摇摆末轮生死战", "timing": "赛前/赛中",
        "desc": "小组末轮，依赖真实积分动态触发。双方都需要赢→押大分；平局双方都能出→押平/小分；一方有出线压力另一方无所谓→押有动力那队。Polymarket 赛中全程开盘，半场结束后可按场上实际情况补仓或锁利。",
    },
    "D": {
        "name": "比赛中观测", "timing": "赛中",
        "desc": "Polymarket 比赛全程开盘，随时可以买卖。半场结束后，根据实际数据（控球率、射门/射正数、半场比分）再入场，比赛前买信息更充分。典型场景：半场0-0但主队控球65%射门10+，此时押「全场大分」或「主队胜」赔率还在，值得进。",
    },
    "F": {
        "name": "准确比分博高赔", "timing": "赛前/赛中",
        "desc": "S级打D级，小仓博具体比分：3-0约8-12x，4-0约15-20x，5-0约30-50x。赛中赔率会随比分移动，1-0领先时押2-0赔率比赛前低但命中率更高，可以赛前+赛中分批。",
    },
    "G": {
        "name": "东道主效应", "timing": "赛前",
        "desc": "美/加/墨在本土城市主场，加成约等于额外0.3–0.5球优势。重点场次：美国vs弱队、墨西哥vs B级对手。主场爆冷也发生过——不是必赢，是赔率里的主场价值被低估。",
    },
    "I": {
        "name": "保守踢法小分", "timing": "赛前/赛中",
        "desc": "一队锁定头名轮换、一队已出局无动力，或双方接受平局。押全场小分 Under 2.5、平局、下半场小分。建议开场15分钟确认比赛节奏后再买，Polymarket 赛中随时可入。",
    },
}

# ---- 2026 世界杯赛程阶段（官方）----
STAGES = [
    {"key": "group", "name": "小组赛", "start": "2026-06-11", "end": "2026-06-27",
     "desc": "12组每组4队，共72场。每组前2名 + 成绩最好的8个第三名晋级，共32队出线。"},
    {"key": "r32", "name": "32强淘汰赛", "start": "2026-06-28", "end": "2026-07-03",
     "desc": "单场淘汰，48队扩军后新增的一轮。"},
    {"key": "r16", "name": "16强", "start": "2026-07-04", "end": "2026-07-07", "desc": "八分之一决赛。"},
    {"key": "qf", "name": "8强", "start": "2026-07-09", "end": "2026-07-11", "desc": "四分之一决赛。"},
    {"key": "sf", "name": "4强", "start": "2026-07-14", "end": "2026-07-15", "desc": "半决赛。"},
    {"key": "third", "name": "三四名决赛", "start": "2026-07-18", "end": "2026-07-18", "desc": "季军争夺战。"},
    {"key": "final", "name": "决赛", "start": "2026-07-19", "end": "2026-07-19",
     "desc": "纽约/新泽西 MetLife 球场。"},
]


def progress(today: str | None = None):
    """返回各阶段状态：已结束/进行中/未开始 + 整体进度。"""
    d = date.fromisoformat(today) if today else date.today()
    out = []
    for s in STAGES:
        st, en = date.fromisoformat(s["start"]), date.fromisoformat(s["end"])
        if d > en:
            status = "已结束"
        elif d < st:
            status = "未开始"
        else:
            status = "进行中"
        out.append({**s, "status": status})
    # 整体进度（按时间轴）
    total_start = date.fromisoformat(STAGES[0]["start"])
    total_end = date.fromisoformat(STAGES[-1]["end"])
    span = (total_end - total_start).days or 1
    elapsed = max(0, min(span, (d - total_start).days))
    return {
        "today": d.isoformat(),
        "overall_percent": round(100 * elapsed / span),
        "current_stage": next((s["name"] for s in out if s["status"] == "进行中"),
                              "未开赛" if d < total_start else "已闭幕"),
        "stages": out,
    }
