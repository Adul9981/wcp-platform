"""SQLite 存储层。

- topics: 当前最新选题快照（每次管道运行 upsert）
- snapshots: 历史价格快照（用于 diff / 趋势 / 先发机会检测）
原则 P0.2：所有记录带 snapshot_ts。
"""
import sqlite3
import os

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT DEFAULT '分析',
    title        TEXT,
    raw_content  TEXT,
    content      TEXT NOT NULL,
    status       TEXT DEFAULT 'draft',
    created_ts   TEXT,
    published_ts TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match       TEXT NOT NULL,
    kickoff     TEXT,
    direction   TEXT NOT NULL,
    reasoning   TEXT,
    risk_level  TEXT DEFAULT '中',
    status      TEXT DEFAULT 'active',
    result      TEXT,
    published   INTEGER DEFAULT 1,
    created_ts  TEXT
);

CREATE TABLE IF NOT EXISTS topics (
    event_id      TEXT PRIMARY KEY,
    slug          TEXT,
    title         TEXT,
    line          TEXT,
    category      TEXT,
    match_id      TEXT,
    teams         TEXT,
    bet_type      TEXT,
    strategy_tags TEXT,
    price         REAL,
    outcomes      TEXT,
    direction     TEXT,
    volume        REAL,
    liquidity     REAL,
    kickoff       TEXT,
    is_new        INTEGER,
    snapshot_ts   TEXT,
    event_url     TEXT
);
CREATE INDEX IF NOT EXISTS idx_topics_line ON topics(line);
CREATE INDEX IF NOT EXISTS idx_topics_match ON topics(match_id);

CREATE TABLE IF NOT EXISTS snapshots (
    event_id    TEXT,
    price       REAL,
    volume      REAL,
    liquidity   REAL,
    snapshot_ts TEXT,
    PRIMARY KEY (event_id, snapshot_ts)
);

CREATE TABLE IF NOT EXISTS seen_events (
    event_id   TEXT PRIMARY KEY,
    first_seen TEXT
);

-- 复盘A：平台预测日志（自动快照单场方向，赛后判命中）
CREATE TABLE IF NOT EXISTS prediction_log (
    match_id      TEXT,
    predicted     TEXT,        -- 预测方向 outcome (如 Mexico / Over 2.5)
    label         TEXT,        -- 中文方向
    bet_type      TEXT,
    strategy_tags TEXT,
    price         REAL,        -- 下注时隐含概率
    kickoff       TEXT,
    captured_ts   TEXT,        -- 首次记录时间
    result        TEXT,        -- 命中/未命中/待定
    actual        TEXT,        -- 实际结果描述
    settled_ts    TEXT,
    PRIMARY KEY (match_id, predicted)
);

-- 后台管理：手写/优化后的分析文章（发布到网站）
CREATE TABLE IF NOT EXISTS posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT DEFAULT '分析',   -- 分析/赛前/赛后/策略
    title        TEXT DEFAULT '',
    raw_content  TEXT DEFAULT '',       -- 用户原始输入（AI生成原文）
    content      TEXT NOT NULL,         -- 优化后内容（展示用）
    status       TEXT DEFAULT 'draft',  -- draft / published
    created_ts   TEXT,
    published_ts TEXT
);

-- 复盘B：用户下注日志（手动记录操作）
CREATE TABLE IF NOT EXISTS bet_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT,
    title       TEXT,
    direction   TEXT,        -- 押的方向
    stake       REAL,        -- 投入
    price       REAL,        -- 下注赔率/隐含概率
    status      TEXT DEFAULT 'open',  -- open/won/lost/void
    pnl         REAL,        -- 盈亏(结算后)
    note        TEXT,
    created_ts  TEXT,
    settled_ts  TEXT
);
"""


def connect():
    path = os.path.abspath(config.DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn=None):
    own = conn is None
    conn = conn or connect()
    conn.executescript(SCHEMA)
    conn.commit()
    if own:
        conn.close()
    return conn


def upsert_topics(conn, topics):
    cols = ["event_id", "slug", "title", "line", "category", "match_id", "teams",
            "bet_type", "strategy_tags", "price", "outcomes", "direction", "volume", "liquidity",
            "kickoff", "is_new", "snapshot_ts", "event_url"]
    placeholders = ",".join("?" * len(cols))
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "event_id")
    sql = (f"INSERT INTO topics ({','.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT(event_id) DO UPDATE SET {updates}")
    rows = []
    for t in topics:
        r = t.to_row()
        rows.append([r[c] if c != "is_new" else int(r[c]) for c in cols])
    conn.executemany(sql, rows)
    # 历史快照
    conn.executemany(
        "INSERT OR IGNORE INTO snapshots(event_id,price,volume,liquidity,snapshot_ts) VALUES(?,?,?,?,?)",
        [(t.event_id, t.price, t.volume, t.liquidity, t.snapshot_ts) for t in topics],
    )
    conn.commit()


def mark_new_events(conn, topics, ts):
    """先发机会检测：首次见到的 event_id 标 is_new=True 并登记 first_seen。"""
    cur = conn.execute("SELECT event_id FROM seen_events")
    seen = {row["event_id"] for row in cur.fetchall()}
    new_ids = []
    for t in topics:
        if t.event_id not in seen:
            t.is_new = True
            new_ids.append((t.event_id, ts))
    conn.executemany("INSERT OR IGNORE INTO seen_events(event_id,first_seen) VALUES(?,?)", new_ids)
    conn.commit()
    return [eid for eid, _ in new_ids]
