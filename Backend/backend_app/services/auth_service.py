from __future__ import annotations

from ..db import connection_scope, transaction
from ..errors import AppError
from ..security import generate_access_token, hash_password, verify_password
from ..utils import mask_phone, now_iso, round2


def serialize_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user["nickname"],
        "phone_masked": mask_phone(user.get("phone")),
        "avatar_url": user.get("avatar_url"),
        "balance": round2(float(user["balance"])),
        "status": user["status"],
    }


def _load_user_by_username(conn, username: str) -> dict | None:
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def _create_session(conn, user_id: int) -> str:
    token = generate_access_token()
    conn.execute(
        """
        INSERT INTO user_sessions (user_id, token, status, last_used_at)
        VALUES (?, ?, 'active', ?)
        """,
        (user_id, token, now_iso()),
    )
    return token


def register_user(username: str, password: str, phone: str | None, nickname: str | None) -> dict:
    with transaction() as conn:
        if _load_user_by_username(conn, username):
            raise AppError("USERNAME_ALREADY_EXISTS", "用户名已存在", 409)

        safe_nickname = nickname or username
        user_id = conn.execute_insert(
            """
            INSERT INTO users (
                username, password_hash, phone, nickname, avatar_url, balance, status
            ) VALUES (?, ?, ?, ?, NULL, 0, 'active')
            """,
            (username, hash_password(password), phone, safe_nickname),
        )
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        token = _create_session(conn, user_id)
        return {
            "success": True,
            "user": serialize_user(user),
            "access_token": token,
            "token_type": "bearer",
        }


def login_user(username: str, password: str) -> dict:
    with transaction() as conn:
        user = _load_user_by_username(conn, username)
        if not user:
            raise AppError("USER_NOT_FOUND", "用户名不存在", 404)
        if user["status"] != "active":
            raise AppError("USER_DISABLED", "当前账号不可用", 403)
        if not verify_password(password, user["password_hash"]):
            raise AppError("INVALID_PASSWORD", "密码错误", 401)

        token = _create_session(conn, user["id"])
        return {
            "success": True,
            "user": serialize_user(user),
            "access_token": token,
            "token_type": "bearer",
        }


def get_current_user_by_token(token: str) -> dict:
    with transaction() as conn:
        session = conn.execute(
            """
            SELECT s.id AS session_id, u.*
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.status = 'active'
            """,
            (token,),
        ).fetchone()
        if not session:
            raise AppError("UNAUTHORIZED", "请先登录", 401)
        if session["status"] != "active":
            raise AppError("USER_DISABLED", "当前账号不可用", 403)
        conn.execute(
            "UPDATE user_sessions SET last_used_at = ? WHERE id = ?",
            (now_iso(), session["session_id"]),
        )
        return dict(session)


def logout_user(token: str) -> dict:
    with transaction() as conn:
        session = conn.execute(
            "SELECT id FROM user_sessions WHERE token = ? AND status = 'active'",
            (token,),
        ).fetchone()
        if session:
            conn.execute(
                "UPDATE user_sessions SET status = 'revoked', last_used_at = ? WHERE id = ?",
                (now_iso(), session["id"]),
            )
    return {"success": True}
