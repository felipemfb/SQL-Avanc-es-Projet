import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / 'data' / 'imdb.db'

def get_connection():
    """Return SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_movie_count():
    """Return number of movies in SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    # fallback if table doesn't exist
    try:
        cursor.execute("SELECT COUNT(*) AS count FROM movies")
        result = cursor.fetchone()
        count = result['count']
    except sqlite3.OperationalError:
        count = 0
    conn.close()
    return count
