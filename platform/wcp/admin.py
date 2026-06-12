"""后台管理：手写内容提交 → 优化 → 发布到网站。

工作流：
  1. POST /admin/posts       提交原始内容（AI 生成原稿）→ 自动基础清洗，存为 draft
  2. GET  /admin/posts       看所有草稿/已发布
  3. PATCH /admin/posts/{id} 写入优化后文本（在对话里让 Claude 改完再贴回来）
  4. POST /admin/posts/{id}/publish  一键发布
  5. GET  /posts             公开接口，前端展示已发布内容
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import db, tone

router = APIRouter(tags=["admin"])


# ── 公开只读接口（前端用） ──────────────────────────────────
@router.get("/posts")
def public_posts(limit: int = 20):
    """已发布的分析文章，供前端展示。"""
    conn = db.connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT id,type,title,content,published_ts FROM posts"
            " WHERE status='published' ORDER BY published_ts DESC LIMIT ?",
            (limit,)).fetchall()]
        return {"count": len(rows), "posts": rows}
    finally:
        conn.close()


# ── 后台管理接口 ────────────────────────────────────────────
class PostIn(BaseModel):
    type: str = "分析"       # 分析 / 赛前 / 赛后 / 策略
    title: str = ""
    raw_content: str         # 用户提交的原始文本
    content: str = ""        # 可选：直接提交已优化版本


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    status: str | None = None   # draft / published


@router.post("/admin/posts")
def create_post(p: PostIn):
    """新建草稿。content 留空时用 raw_content 的基础清洗版（去 AI 套话）。"""
    content = p.content.strip() if p.content.strip() else tone.clean(p.raw_content)
    ts = datetime.now(timezone.utc).isoformat()
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO posts(type,title,raw_content,content,status,created_ts)"
            " VALUES(?,?,?,?,?,?)",
            (p.type, p.title.strip(), p.raw_content, content, "draft", ts))
        conn.commit()
        return {"ok": True, "id": cur.lastrowid, "preview": content[:120] + ("…" if len(content) > 120 else "")}
    finally:
        conn.close()


@router.get("/admin/posts")
def list_posts(status: str | None = None):
    """列出草稿/已发布。status=draft 或 published，不传则全部。"""
    conn = db.connect()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM posts WHERE status=? ORDER BY created_ts DESC", (status,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM posts ORDER BY created_ts DESC").fetchall()
        return {"count": len(rows), "posts": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.patch("/admin/posts/{post_id}")
def update_post(post_id: int, u: PostUpdate):
    """更新草稿——优化后的文本在对话里改完，在这里写入 content 字段。"""
    conn = db.connect()
    try:
        if not conn.execute("SELECT id FROM posts WHERE id=?", (post_id,)).fetchone():
            raise HTTPException(404, "文章不存在")
        sets, vals = [], []
        if u.title is not None:
            sets.append("title=?"); vals.append(u.title)
        if u.content is not None:
            sets.append("content=?"); vals.append(u.content)
        if u.status is not None:
            sets.append("status=?"); vals.append(u.status)
            if u.status == "published":
                sets.append("published_ts=?")
                vals.append(datetime.now(timezone.utc).isoformat())
        if not sets:
            return {"ok": True, "changed": 0}
        vals.append(post_id)
        conn.execute(f"UPDATE posts SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
        return {"ok": True, "id": post_id}
    finally:
        conn.close()


@router.post("/admin/posts/{post_id}/publish")
def publish_post(post_id: int):
    """将草稿标记为已发布。"""
    conn = db.connect()
    try:
        if not conn.execute("SELECT id FROM posts WHERE id=?", (post_id,)).fetchone():
            raise HTTPException(404, "文章不存在")
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE posts SET status='published',published_ts=? WHERE id=?", (ts, post_id))
        conn.commit()
        return {"ok": True, "id": post_id, "published_ts": ts}
    finally:
        conn.close()


@router.delete("/admin/posts/{post_id}")
def delete_post(post_id: int):
    conn = db.connect()
    try:
        conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
