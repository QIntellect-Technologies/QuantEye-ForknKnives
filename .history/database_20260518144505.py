import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from logger_config import get_logger
from config import DB_PATH, ATTENDANCE_LOG_RETENTION_DAYS

logger = get_logger(__name__)


def init_db():
    """Initialize SQLite database with proper schema and indexes."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                email TEXT,
                phone TEXT,
                department TEXT,
                enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1,
                notes TEXT
            )
        ''')

        # Embeddings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                embedding BLOB NOT NULL,
                source_video TEXT,
                quality_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Attendance logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                detected_name TEXT,
                confidence REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT,
                frame_quality TEXT,
                location TEXT,
                device_id TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_name ON users(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_embeddings_user ON embeddings(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_user ON attendance(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_source ON attendance(source)')

        conn.commit()
        conn.close()
        logger.info(f"✓ Database initialized at {DB_PATH}")
        return True
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        return False


def add_user(name: str, email: str = None, phone: str = None, department: str = None) -> Optional[int]:
    """Add a new user with validation."""
    try:
        if not name or len(name.strip()) == 0:
            logger.warning("Attempted to add user with empty name")
            return None
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO users (name, email, phone, department) VALUES (?, ?, ?, ?)',
            (name.strip(), email, phone, department)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"✓ User '{name}' created (ID: {user_id})")
        return user_id
    except sqlite3.IntegrityError:
        logger.warning(f"User '{name}' already exists")
        return None
    except Exception as e:
        logger.error(f"Failed to add user: {e}")
        return None


def get_user_by_name(name: str) -> Optional[Dict]:
    """Retrieve user by name."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, email FROM users WHERE name = ?', (name,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {'id': row[0], 'name': row[1], 'email': row[2]}
    return None


def get_all_users() -> List[Dict]:
    """Get all active users."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, email, created_at FROM users WHERE active = 1')
    rows = cursor.fetchall()
    conn.close()
    
    return [{'id': r[0], 'name': r[1], 'email': r[2], 'created_at': r[3]} for r in rows]


def store_embedding(user_id: int, embedding: List[float], source_video: str = None):
    """Store face embedding for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    embedding_blob = json.dumps(embedding).encode()
    
    cursor.execute(
        'INSERT INTO embeddings (user_id, embedding, source_video) VALUES (?, ?, ?)',
        (user_id, embedding_blob, source_video)
    )
    conn.commit()
    conn.close()


def get_embeddings_for_user(user_id: int) -> List[Dict]:
    """Retrieve all embeddings for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, embedding, source_video, created_at FROM embeddings WHERE user_id = ?',
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    embeddings = []
    for row in rows:
        embedding = json.loads(row[1].decode())
        embeddings.append({
            'id': row[0],
            'embedding': embedding,
            'source_video': row[2],
            'created_at': row[3]
        })
    return embeddings


def log_attendance(user_id: int, detected_name: str, confidence: float, source: str = 'camera'):
    """Log attendance detection."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO attendance (user_id, detected_name, confidence, source) VALUES (?, ?, ?, ?)',
        (user_id, detected_name, confidence, source)
    )
    conn.commit()
    conn.close()


def get_attendance_logs(limit: int = 100) -> List[Dict]:
    """Retrieve recent attendance logs."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, u.name, a.detected_name, a.confidence, a.timestamp, a.source
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'id': r[0],
        'name': r[1],
        'detected_name': r[2],
        'confidence': r[3],
        'timestamp': r[4],
        'source': r[5]
    } for r in rows]


def get_attendance_by_user(user_id: int, days: int = 7) -> List[Dict]:
    """Get attendance logs for a user in the last N days."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, timestamp, confidence, source FROM attendance
            WHERE user_id = ? AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC
        ''', (user_id, days))
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'id': r[0],
            'timestamp': r[1],
            'confidence': r[2],
            'source': r[3]
        } for r in rows]
    except Exception as e:
        logger.error(f"Failed to get attendance logs: {e}")
        return []


def cleanup_old_logs(days: int = ATTENDANCE_LOG_RETENTION_DAYS):
    """Delete attendance logs older than specified days."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM attendance
            WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
        ''', (days,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"✓ Cleaned up {deleted} old attendance records")
        return deleted
    except Exception as e:
        logger.error(f"Failed to cleanup logs: {e}")
        return 0


def get_attendance_statistics() -> Dict:
    """Get comprehensive attendance statistics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Total attendance records
        cursor.execute('SELECT COUNT(*) FROM attendance')
        total_records = cursor.fetchone()[0]
        
        # Today's attendance
        cursor.execute('''
            SELECT COUNT(*) FROM attendance
            WHERE datetime(timestamp) >= datetime('now', 'start of day')
        ''')
        today_count = cursor.fetchone()[0]
        
        # Users with attendance today
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) FROM attendance
            WHERE datetime(timestamp) >= datetime('now', 'start of day')
        ''')
        unique_today = cursor.fetchone()[0]
        
        # Average confidence
        cursor.execute('SELECT AVG(confidence) FROM attendance')
        avg_confidence = cursor.fetchone()[0] or 0
        
        # Most recent attendance
        cursor.execute('''
            SELECT u.name, a.timestamp, a.confidence FROM attendance a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.timestamp DESC LIMIT 10
        ''')
        recent = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_records': total_records,
            'today_count': today_count,
            'unique_users_today': unique_today,
            'avg_confidence': float(avg_confidence),
            'recent_entries': [
                {'name': r[0], 'timestamp': r[1], 'confidence': r[2]}
                for r in recent
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return {}


if __name__ == '__main__':
    init_db()
