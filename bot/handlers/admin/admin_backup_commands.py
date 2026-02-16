from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from bot.shared_auth import is_admin
from db.session import DATABASE_PATH


PM2_OUT_LOG_PATH = os.getenv("PM2_OUT_LOG_PATH", "/home/botuser/.pm2/logs/medbot-out.log")
MAX_DIRECT_LOG_SEND_BYTES = 45 * 1024 * 1024  # keep margin below Telegram document limit


def _create_sqlite_snapshot(source_db_path: str) -> str:
    """
    Create a consistent SQLite snapshot using backup API.
    Returns a temporary file path.
    """
    fd, snapshot_path = tempfile.mkstemp(prefix="medical_backup_", suffix=".db")
    os.close(fd)

    src_conn = sqlite3.connect(f"file:{source_db_path}?mode=ro", uri=True, timeout=30)
    try:
        dst_conn = sqlite3.connect(snapshot_path, timeout=30)
        try:
            src_conn.backup(dst_conn)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    return snapshot_path


def _build_logs_tail_file(log_path: str, lines: int = 8000) -> str:
    """
    Build a temporary tail file from a large log to avoid sending oversized documents.
    """
    fd, tail_path = tempfile.mkstemp(prefix="medbot_logs_tail_", suffix=".log")
    os.close(fd)

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.readlines()

    selected = content[-lines:] if len(content) > lines else content
    with open(tail_path, "w", encoding="utf-8") as out:
        out.writelines(selected)

    return tail_path


async def backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /backup - send current SQLite backup snapshot."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_admin(user.id):
        return

    db_path = os.getenv("DATABASE_PATH", DATABASE_PATH)
    if not os.path.exists(db_path):
        await message.reply_text("❌ Database not found")
        return

    await message.reply_text("📦 Sending backup...")

    snapshot_path = None
    try:
        snapshot_path = await asyncio.to_thread(_create_sqlite_snapshot, db_path)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        with open(snapshot_path, "rb") as f:
            await message.reply_document(
                document=f,
                filename=f"medical_backup_{ts}.db",
            )
    except Exception as e:
        await message.reply_text(f"❌ Backup failed: {str(e)[:250]}")
    finally:
        if snapshot_path and os.path.exists(snapshot_path):
            try:
                os.remove(snapshot_path)
            except Exception:
                pass


async def send_pm2_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /logs - send pm2 output log file (or tail if too large)."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_admin(user.id):
        return

    log_path = PM2_OUT_LOG_PATH
    if not os.path.exists(log_path):
        await message.reply_text(f"❌ Log file not found:\n{log_path}")
        return

    await message.reply_text("📄 Sending logs...")

    temp_tail = None
    try:
        send_path = log_path
        send_name = os.path.basename(log_path)
        size_bytes = os.path.getsize(log_path)

        # If file is too large, send a tail snapshot to avoid Telegram size failure.
        if size_bytes > MAX_DIRECT_LOG_SEND_BYTES:
            temp_tail = await asyncio.to_thread(_build_logs_tail_file, log_path)
            send_path = temp_tail
            send_name = f"{os.path.splitext(os.path.basename(log_path))[0]}_tail.log"

        with open(send_path, "rb") as f:
            await message.reply_document(document=f, filename=send_name)

        if temp_tail:
            await message.reply_text("ℹ️ Original log was large, sent latest tail only.")
    except Exception as e:
        await message.reply_text(f"❌ Logs send failed: {str(e)[:250]}")
    finally:
        if temp_tail and os.path.exists(temp_tail):
            try:
                os.remove(temp_tail)
            except Exception:
                pass


def register(app):
    """Register admin utility commands."""
    app.add_handler(CommandHandler("backup", backup_db))
    app.add_handler(CommandHandler("logs", send_pm2_logs))

