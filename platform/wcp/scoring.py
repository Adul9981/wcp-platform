"""三榜评分 —— 全部可解释（原则 P2.1：不做黑箱）。

诚实声明（原则 P0.1 / P2.2）：
当前未接入外部博彩赔率，**不计算"公平价值/edge"，也不臆造**。
三榜基于可观测信号排序：策略匹配、流动性、成交量、隐含概率(盈亏比)、是否新上线。
跨市场公平价值是 M2+ 的后续输入（见待办库），接入后再补 edge 维度。
"""
import math


def _norm_log(x, hi):
    """对数归一到 0..1。hi 为参考上界。"""
    if not x or x <= 0:
        return 0.0
    return min(1.0, math.log10(1 + x) / math.log10(1 + hi))


def payoff_ratio(price):
    """盈亏比 ≈ 1/隐含概率（赢1注的毛回报倍数）。"""
    if not price or price <= 0:
        return None
    return round(1.0 / price, 2)


def score_attention(t):
    """🎯 最值得关注：策略匹配 × 流动性(可成交) × 成交活跃。"""
    strat = min(1.0, len(t["strategy_tags"]) / 4.0)
    liq = _norm_log(t["liquidity"], 1_000_000)
    vol = _norm_log(t["volume"], 10_000_000)
    score = 0.40 * strat + 0.35 * liq + 0.25 * vol
    reason = f"命中{len(t['strategy_tags'])}条策略{t['strategy_tags']}；" \
             f"流动性{t['liquidity']:.0f}；成交{t['volume']:.0f}"
    return round(score, 4), reason


def score_overlooked(t):
    """💎 最被忽视·低关注：有策略逻辑 + 低关注度/新上线（低流动属正常，不剔除）。

    原则：**低流动性不作为剔除理由**。
    新上线/低成交是正常状态，不设流动性门槛。
    门槛仅：必须有策略逻辑（无逻辑的冷门=噪声）+ 有有效报价。
    防刷屏靠 boards 层按场次去重，不靠流动性过滤。
    """
    if not t["strategy_tags"] or t["price"] is None:
        return 0.0, ""
    low_attention = 1.0 - _norm_log(t["volume"], 10_000_000)
    strat = min(1.0, len(t["strategy_tags"]) / 4.0)
    new_bonus = 1.0 if t["is_new"] else 0.0
    interest, ikind = _interest(t)   # 有趣度：顶出H2H/大洲/球员等深挖盘
    score = 0.35 * low_attention + 0.15 * strat + 0.10 * new_bonus + 0.40 * interest
    tag = "新上线" if t["is_new"] else "低关注"
    extra = f"·{ikind}" if ikind else ""
    reason = f"{tag}{extra}+策略{t['strategy_tags']}；成交仅{t['volume']:.0f}（低流动属正常，不剔除）"
    return round(score, 4), reason


# 深挖出的"被忽视但有趣"盘类型 → 高有趣度
_INTERESTING = {
    "球员H2H": "H2H对决", "夺冠": "", "大洲夺冠": "大洲盘", "球员参赛": "球员市场",
}
_INTERESTING_CAT = {
    "12大洲夺冠": "大洲盘", "10大洲其他": "大洲盘", "08花边政治": "花边盘",
    "13球员参赛": "球员市场", "07球员表现": "球员盘", "03个人奖项": "个人奖项",
    "02射手榜": "射手榜", "09赛事纪录": "纪录盘", "06小组排名": "小组排名", "11小组头名": "小组头名",
}
# 重复刷屏的单场衍生盘 → 低有趣度(不该霸占被忽视榜)
_BORING_BET = {"首开记录", "比分", "角球", "BTTS", "半场", "其他衍生"}


def _interest(t):
    cat = t.get("category") or ""
    bet = t.get("bet_type") or ""
    if bet in _INTERESTING:
        return 1.0, _INTERESTING[bet]
    if cat in _INTERESTING_CAT:
        return 1.0, _INTERESTING_CAT[cat]
    if bet in _BORING_BET:
        return 0.15, ""
    return 0.5, ""


def score_payoff(t):
    """📈 最大盈亏比：低隐含概率(高赔率) + 有逻辑支撑 + 最低可成交流动性。"""
    p = t["price"]
    if not p or p <= 0:
        return 0.0, ""
    # 门槛：过滤接近必然(>0.5)与尘埃盘(<0.02)；需有策略支撑
    if p > 0.5 or p < 0.02 or not t["strategy_tags"]:
        return 0.0, ""
    pr = payoff_ratio(p)
    # 盈亏比贡献（对数压缩，避免极端尘埃盘霸榜）+ 流动性可成交性
    pr_score = min(1.0, math.log10(pr) / math.log10(50))  # 50x 封顶
    liq = _norm_log(t["liquidity"], 1_000_000)
    score = 0.70 * pr_score + 0.30 * liq
    reason = f"盈亏比≈{pr}x（隐含{p*100:.1f}%）+ 逻辑{t['strategy_tags']}；流动性{t['liquidity']:.0f}"
    return round(score, 4), reason
