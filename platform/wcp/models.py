"""统一数据模型 —— 选题(Topic)。

对齐 2_数据库/预测选题全景.md 的数据模型。所有抓取结果归一到 Topic。
"""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Topic:
    # 标识
    event_id: str                 # Polymarket event id
    slug: str                     # 用于生成跳转链接的 slug
    title: str

    # 分类
    line: str                     # "长盘" | "单场"
    category: str = ""            # 选题全景里的分类编号/名
    match_id: Optional[str] = None  # 单场盘归一到的场次 id（去重用）

    # 内容
    teams: list = field(default_factory=list)
    bet_type: str = ""            # 1X2 / O/U / 比分 / 让球 / 出线 / 夺冠 ...
    strategy_tags: list = field(default_factory=list)  # 命中策略 [A..N]

    # 行情
    price: Optional[float] = None     # 代表性隐含概率
    outcomes: list = field(default_factory=list)  # [{name, price}] 各选项及其Yes概率
    volume: float = 0.0
    liquidity: float = 0.0

    # 下注方向（P3，由 direction 模块填充）
    direction: Optional[dict] = None  # {label, outcome, price, basis} 或 None

    # 时间/状态
    kickoff: Optional[str] = None     # 单场盘开赛时间(UTC)
    is_new: bool = False              # 近期新上线（先发机会）
    snapshot_ts: str = ""             # 抓取时间(UTC ISO)

    # 可追溯（原则 P0.3）
    event_url: str = ""               # 带邀请码的跳转链接

    def to_row(self) -> dict:
        d = asdict(self)
        # list/dict 字段存为 JSON 文本
        import json
        for k in ("teams", "strategy_tags", "outcomes", "direction"):
            d[k] = json.dumps(d[k], ensure_ascii=False)
        return d
