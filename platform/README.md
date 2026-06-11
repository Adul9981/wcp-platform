# WCP · 世界杯预测平台（代码）

> 知识库在上级目录（1_想法库 … 7_优化库）。本目录是平台代码。
> 受 [平台建设原则](../5_工具建设库/平台建设原则.md) 约束。

## 当前进度：M1 数据管道 ✅ + M2 三榜引擎 ✅

```
platform/
├── requirements.txt        # requests, fastapi, uvicorn
├── data/wcp.db             # SQLite（运行后生成）
└── wcp/
    ├── config.py           # 配置 + 邀请码 + build_event_url()（单一真相来源）
    ├── client.py           # Polymarket 只读客户端（UA/翻页/超时/退避重试）
    ├── models.py           # Topic 统一数据模型
    ├── normalize.py        # 归一/去重(348→75场次)/策略打标(A..N)
    ├── db.py               # SQLite：topics / snapshots / seen_events
    ├── pipeline.py         # M1 编排：抓取→归一→标新→落库
    ├── scoring.py          # M2 三榜可解释评分
    ├── boards.py           # M2 三榜生成（多样性控制，不以流动性过滤）
    └── api.py              # M2 FastAPI：/health /boards /topics /matches
```

## 运行
```bash
pip install -r requirements.txt
python -m wcp.pipeline          # 1. 跑数据管道
python -m wcp.boards            # 2. 命令行预览三榜
uvicorn wcp.api:app --reload    # 3. 启动 API (http://127.0.0.1:8000/boards)
```

## 重要设计铁律
- **低流动性绝不作为剔除理由**：新上线低关注盘是先发机会(策略N)的正常状态。
- **不臆造公平价值**：未接外部赔率前，三榜按可观测信号排序并诚实声明。

## 数据源（已核查稳定）
- 长盘：Gamma API `tag_id=102350`（149选题）
- 单场：`series_id=11433`（348 event → 75 独立场次）

## 设计要点
- **读写分离**（原则P1）：本管道仅只读，无私钥、不下单。
- **失败显性**（原则P0.4）：重试耗尽抛错，不用旧值假装新值。
- **可追溯**（原则P0.3）：每条 topic 存原始 slug + 带邀请码 event_url。
- **diff/先发**：`seen_events` 表标记首次出现，`snapshots` 存历史价用于趋势。

## 下一步：M2 三榜引擎
公平价值估算 → 机会评分 → 三榜（最值得关注/最被忽视/最大盈亏比）→ FastAPI 暴露。
