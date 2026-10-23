"""
Query history persistence using SQLite.
"""
import sqlite3, os, json, logging
from datetime import datetime

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'querymind_history.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                sql_query TEXT NOT NULL,
                table_name TEXT NOT NULL,
                row_count INTEGER DEFAULT 0,
                elapsed_ms REAL DEFAULT 0,
                input_mode TEXT DEFAULT 'text',
                status TEXT DEFAULT 'success',
                error TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()
    logger.info("✅ History DB initialized")

def save_query(question: str, sql: str, table_name: str,
               row_count: int = 0, elapsed_ms: float = 0,
               input_mode: str = 'text', status: str = 'success', error: str = None):
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO query_history
                (question, sql_query, table_name, row_count, elapsed_ms, input_mode, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (question, sql, table_name, row_count, elapsed_ms, input_mode, status, error))
            conn.commit()
    except Exception as e:
        logger.error(f"History save error: {e}")

def get_history(limit: int = 50, table_name: str = None) -> list:
    try:
        with get_conn() as conn:
            if table_name:
                rows = conn.execute("""
                    SELECT * FROM query_history WHERE table_name=?
                    ORDER BY created_at DESC LIMIT ?
                """, (table_name, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM query_history
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        return []

def delete_history_item(item_id: int) -> bool:
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM query_history WHERE id=?", (item_id,))
            conn.commit()
            return True
    except:
        return False

def clear_history() -> bool:
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM query_history")
            conn.commit()
            return True
    except:
        return False

def get_stats() -> dict:
    try:
        with get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM query_history").fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM query_history WHERE status='success'").fetchone()[0]
            avg_ms = conn.execute("SELECT AVG(elapsed_ms) FROM query_history WHERE status='success'").fetchone()[0]
            modes = conn.execute("""
                SELECT input_mode, COUNT(*) as cnt FROM query_history GROUP BY input_mode
            """).fetchall()
            return {
                "total": total,
                "success": success,
                "failed": total - success,
                "avg_ms": round(avg_ms or 0, 1),
                "modes": {r['input_mode']: r['cnt'] for r in modes}
            }
    except:
        return {"total": 0, "success": 0, "failed": 0, "avg_ms": 0, "modes": {}}
