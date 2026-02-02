import sqlite3
from pathlib import Path
import argparse
from collections import defaultdict
import time
from typing import List, Tuple, Optional, Callable, Any

def printRows(cols, rows, limit=20):
    if not rows:
        print("(no results)")
        return
    hdr = " | ".join(cols)
    print(hdr)
    print("-" * max(len(hdr), 20))
    for r in rows[:limit]:
        print(" | ".join(str(x) if x is not None else "NULL" for x in r))

def _connect(db_path: str) -> sqlite3.Connection:
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    conn = sqlite3.connect(str(p), timeout=30)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=OFF;")
        cur.execute("PRAGMA temp_store=MEMORY;")
        conn.commit()
    except Exception:
        pass
    return conn

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_q1_persons_primaryName ON persons(primaryName);",
    "CREATE INDEX IF NOT EXISTS idx_q1_principals_pid_mid ON principals(pid, mid);",
    "CREATE INDEX IF NOT EXISTS idx_q2_genres_genre_mid ON genres(genre, mid);",
    "CREATE INDEX IF NOT EXISTS idx_q2_movies_startYear_mid ON movies(startYear, mid);",
    "CREATE INDEX IF NOT EXISTS idx_q2_ratings_mid ON ratings(mid);",
    "CREATE INDEX IF NOT EXISTS idx_q3_characters_pid_mid ON characters(pid, mid);",
    "CREATE INDEX IF NOT EXISTS idx_q4_directors_pid_mid ON directors(pid, mid);",
    "CREATE INDEX IF NOT EXISTS idx_q5_genres_mid ON genres(mid);",
    "CREATE INDEX IF NOT EXISTS idx_q5_ratings_mid ON ratings(mid);",
    "CREATE INDEX IF NOT EXISTS idx_q6_principals_pid_mid ON principals(pid, mid);",
    "CREATE INDEX IF NOT EXISTS idx_q7_genres_mid ON genres(mid);",
    "CREATE INDEX IF NOT EXISTS idx_q8_principals_pid ON principals(pid);",
    "CREATE INDEX IF NOT EXISTS idx_q8_movies_mid ON movies(mid);",
    "CREATE INDEX IF NOT EXISTS idx_q8_ratings_mid ON ratings(mid);",
    "CREATE INDEX IF NOT EXISTS idx_q9_genres_genre_mid ON genres(genre, mid);",
    "CREATE INDEX IF NOT EXISTS idx_q9_principals_mid ON principals(mid);",
]

def _index_name_from_create(stmt: str) -> Optional[str]:
    parts = stmt.strip().split()
    try:
        if parts[0].upper() == "CREATE" and parts[1].upper() == "INDEX":
            if len(parts) > 2 and parts[2].upper() == "IF":
                return parts[5]
            return parts[2]
    except Exception:
        pass
    return None

def create_indexes(conn: sqlite3.Connection):
    c = conn.cursor()
    for s in INDEX_STATEMENTS:
        try:
            c.execute(s)
        except Exception:
            pass
    conn.commit()

def drop_indexes(conn: sqlite3.Connection):
    c = conn.cursor()
    for s in INDEX_STATEMENTS:
        name = _index_name_from_create(s)
        if not name:
            continue
        try:
            c.execute(f"DROP INDEX IF EXISTS {name};")
        except Exception:
            try:
                c.execute(f'DROP INDEX IF EXISTS "{name}";')
            except Exception:
                pass
    conn.commit()

def filmsByActor(conn: sqlite3.Connection, name: str, use_indexes: bool = False) -> list:
    sql = """
    WITH target AS (
      SELECT pid, primaryName FROM persons WHERE lower(primaryName) = lower(?)
    )
    SELECT t.primaryName AS actor_name, p.mid, m.primaryTitle, m.startYear, p.category, p.job
    FROM target t
    JOIN principals p ON p.pid = t.pid
    LEFT JOIN movies m ON m.mid = p.mid
    ORDER BY (m.startYear IS NULL), m.startYear DESC, m.primaryTitle
    """
    cur = conn.execute(sql, (name,))
    rows = cur.fetchall()
    printRows(["actor_name","mid","title","year","category","job"], rows, 10)
    return rows

def bestFilmsFilter(conn: sqlite3.Connection, genre: str, startYear: int, endYear: int, N: int = 10, use_indexes: bool = False) -> list:
    sql = """
    SELECT m.mid, m.primaryTitle, m.startYear, r.averageRating, r.numVotes
    FROM genres g
    JOIN movies m ON m.mid = g.mid
    JOIN ratings r ON r.mid = m.mid
    WHERE lower(g.genre) = lower(?)
      AND m.startYear BETWEEN ? AND ?
    ORDER BY r.averageRating DESC, r.numVotes DESC
    LIMIT ?
    """
    cur = conn.execute(sql, (genre, startYear, endYear, N))
    rows = cur.fetchall()
    printRows(["mid","title","year","avgRating","numVotes"], rows, min(10, N))
    return rows

def charactersByActor(conn: sqlite3.Connection, use_indexes: bool = False) -> list:
    sql = """
    SELECT c.pid, p.primaryName, c.mid, m.primaryTitle, COUNT(DISTINCT c.name) AS roles_count
    FROM characters c
    JOIN persons p ON p.pid = c.pid
    LEFT JOIN movies m ON m.mid = c.mid
    GROUP BY c.pid, c.mid
    HAVING COUNT(DISTINCT c.name) > 1
    ORDER BY roles_count DESC, p.primaryName
    """
    cur = conn.execute(sql)
    rows = cur.fetchall()
    printRows(["pid","actor_name","mid","title","roles_count"], rows, 10)
    return rows

def filmsTogether(conn: sqlite3.Connection, actor_name: str, use_indexes: bool = False) -> list:
    sql = """
    SELECT d.pid AS director_pid, p.primaryName AS director_name, COUNT(*) AS films_together
    FROM directors d
    JOIN persons p ON p.pid = d.pid
    WHERE d.mid IN (
      SELECT pr.mid FROM principals pr
      WHERE pr.pid IN (SELECT pid FROM persons WHERE lower(primaryName) = lower(?))
    )
    GROUP BY d.pid
    ORDER BY films_together DESC, p.primaryName
    """
    cur = conn.execute(sql, (actor_name,))
    rows = cur.fetchall()
    printRows(["director_pid","director_name","films_together"], rows, 10)
    return rows

def bestMoviesMetrics(conn: sqlite3.Connection, min_rating: float = 7.0, min_count: int = 50, use_indexes: bool = False) -> list:
    sql = """
    SELECT g.genre, AVG(r.averageRating) AS avg_rating, COUNT(*) AS cnt
    FROM genres g
    JOIN ratings r ON r.mid = g.mid
    GROUP BY g.genre
    HAVING avg_rating > ? AND cnt > ?
    ORDER BY avg_rating DESC
    """
    cur = conn.execute(sql, (min_rating, min_count))
    rows = cur.fetchall()
    printRows(["genre","avg_rating","count"], rows, 10)
    return rows

def bestByDecade(conn: sqlite3.Connection, actor_name: str, limit_decades: Optional[int] = None, use_indexes: bool = False) -> list:
    sql = """
    WITH actor AS (
      SELECT pid FROM persons WHERE lower(primaryName) = lower(?)
    ), actor_movies AS (
      SELECT m.mid, m.startYear, r.averageRating
      FROM principals pr
      JOIN movies m ON m.mid = pr.mid
      LEFT JOIN ratings r ON r.mid = m.mid
      WHERE pr.pid IN (SELECT pid FROM actor)
        AND m.startYear IS NOT NULL
    ), decade AS (
      SELECT (CAST(startYear/10 AS INTEGER) * 10) AS decade, COUNT(*) AS cnt, AVG(averageRating) AS avg_rating
      FROM actor_movies
      GROUP BY decade
      ORDER BY decade DESC
    )
    SELECT decade, cnt, avg_rating FROM decade
    """
    params = (actor_name,)
    if limit_decades is not None:
        sql = sql + "\nLIMIT ?"
        params = (actor_name, limit_decades)
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    printRows(["decade","count","avg_rating"], rows, 10)
    return rows

def moviesPodium(conn: sqlite3.Connection, top_k: int = 3, use_indexes: bool = False) -> list:
    sql = f"""
    SELECT genre, mid, title, averageRating, numVotes, rn FROM (
      SELECT g.genre, m.mid, m.primaryTitle AS title, r.averageRating, r.numVotes,
             ROW_NUMBER() OVER (PARTITION BY g.genre ORDER BY r.averageRating DESC, r.numVotes DESC) AS rn
      FROM genres g
      JOIN movies m ON m.mid = g.mid
      JOIN ratings r ON r.mid = m.mid
    ) WHERE rn <= ?
    ORDER BY genre, rn;
    """
    cur = conn.execute(sql, (top_k,))
    rows = cur.fetchall()
    printRows(["genre","mid","title","avgRating","numVotes","rank"], rows, 10)
    return rows

def famousByMovie(conn: sqlite3.Connection, votes_threshold: int = 200000, fallback_top_n: int = 10, use_indexes: bool = False) -> list:
    cur = conn.cursor()
    q = """
    SELECT pr.pid, p.primaryName, m.mid, m.primaryTitle, m.startYear, COALESCE(r.numVotes, 0) as numVotes
    FROM principals pr
    JOIN persons p ON p.pid = pr.pid
    JOIN movies m ON m.mid = pr.mid
    LEFT JOIN ratings r ON r.mid = m.mid
    WHERE m.startYear IS NOT NULL
    ORDER BY pr.pid, m.startYear, m.mid
    """
    cur.execute(q)
    rows = cur.fetchall()
    people = defaultdict(lambda: {"name": None, "films": []})
    for pid, name, mid, title, startYear, numVotes in rows:
        people[pid]["name"] = name
        try:
            sy = int(startYear)
        except:
            continue
        try:
            nv = int(numVotes)
        except:
            nv = 0
        people[pid]["films"].append((mid, title, sy, nv))
    strict_results = []
    for pid, info in people.items():
        films = info["films"]
        if not films or len(films) < 2:
            continue
        films.sort(key=lambda x: (x[2], x[0]))
        for mid, title, byear, bnum in films:
            before_votes = [nv for (_m, _t, y, nv) in films if y < byear]
            after_votes  = [nv for (_m, _t, y, nv) in films if y >= byear]
            cnt_before = len(before_votes)
            cnt_after = len(after_votes)
            if cnt_before == 0 or cnt_after == 0:
                continue
            avg_before = sum(before_votes) / cnt_before if cnt_before else 0.0
            avg_after  = sum(after_votes) / cnt_after if cnt_after else 0.0
            if avg_before < votes_threshold and avg_after > votes_threshold:
                strict_results.append((pid, info["name"], mid, title, byear, cnt_before, cnt_after, round(avg_before,2), round(avg_after,2)))
                break
    if strict_results:
        strict_results.sort(key=lambda x: x[8], reverse=True)
        printRows(["pid","name","breakout_mid","breakout_title","breakout_year","cnt_before","cnt_after","avg_before_votes","avg_after_votes"], strict_results, 10)
        return strict_results
    candidates = []
    for pid, info in people.items():
        films = info["films"]
        before_votes = [nv for (_m, _t, y, nv) in films if nv < votes_threshold]
        after_films  = [(_m, _t, y, nv) for (_m, _t, y, nv) in films if nv >= votes_threshold]
        cnt_before = len(before_votes)
        cnt_after = len(after_films)
        if cnt_before == 0 or cnt_after == 0:
            continue
        avg_before = sum(before_votes) / cnt_before
        avg_after  = sum(nv for (_m,_t,y,nv) in after_films) / cnt_after
        ratio = (avg_after / avg_before) if avg_before > 0 else None
        delta = avg_after - avg_before
        best_after = max(after_films, key=lambda x: x[3])
        best_after_mid, best_after_title, _, best_after_votes = best_after
        candidates.append((pid, info["name"], cnt_before, cnt_after, round(avg_before,2), round(avg_after,2), round(ratio,3) if ratio is not None else None, round(delta,2), best_after_mid, best_after_title, best_after_votes))
    if candidates:
        def cand_key(x):
            ratio = x[6]
            return (-(ratio) if ratio is not None else float('inf'), -x[7], -x[10])
        candidates.sort(key=cand_key)
        printRows(["pid","name","cnt_before","cnt_after","avg_before_votes","avg_after_votes","ratio","delta","best_after_mid","best_after_title","best_after_votes"], candidates[:fallback_top_n], fallback_top_n)
        return candidates[:fallback_top_n]
    return []

def top_actors_by_genre(conn: sqlite3.Connection, genre: str = "Drama", limit: Optional[int] = None, use_indexes: bool = False) -> list:
    base_sql = """
    SELECT pr.pid, p.primaryName, COUNT(*) AS appearances, AVG(r.averageRating) AS avgRating
    FROM principals pr
    JOIN movies m ON m.mid = pr.mid
    JOIN genres g ON g.mid = m.mid
    JOIN ratings r ON r.mid = m.mid
    JOIN persons p ON p.pid = pr.pid
    WHERE lower(g.genre) = lower(?)
    GROUP BY pr.pid
    HAVING COUNT(*) >= 2
    ORDER BY avgRating DESC, appearances DESC
    """
    params = [genre]
    if limit is not None:
        base_sql = base_sql + "\nLIMIT ?"
        params.append(limit)
    cur = conn.execute(base_sql, tuple(params))
    rows = cur.fetchall()
    printRows(["pid","name","appearances","avgRating"], rows, 10)
    return rows

inventCode = top_actors_by_genre

def _time_callable_avg(callable_fn: Callable[[], Any], runs: int = 3) -> Optional[float]:
    if runs < 1:
        runs = 1
    try:
        callable_fn()
    except Exception:
        return None
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            callable_fn()
        except Exception:
            return None
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)
    return sum(times) / len(times)

def _print_table(header: List[str], rows: List[List[str]]):
    widths = [len(h) for h in header]
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(str(c)))
    sep = " | "
    line = "-+-".join("-" * w for w in widths)
    print(sep.join(h.ljust(widths[i]) for i, h in enumerate(header)))
    print(line)
    for r in rows:
        print(sep.join(str(c).ljust(widths[i]) for i, c in enumerate(r)))

def main_benchmark():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db", default="cineexplorer/data/imdb.db", help="Path to SQLite DB")
    args, _ = parser.parse_known_args()
    db_path = args.db
    if not Path(db_path).exists():
        print(f"DB not found: {db_path}")
        return
    conn = _connect(db_path)

    actor_name = "Tom Hanks"
    print("Actor Name:", actor_name)
    genre = "Drama"
    print("Genre:", genre)
    start_year = 2000
    print("Start year:", start_year)
    end_year = 2025
    print("End year:", end_year)
    N = 10
    print("Top N:", N)
    podium_k = 3
    print("K:", podium_k)
    min_rating = 7.0
    print("Min average rating Q5:", min_rating)
    min_count = 50
    print("Min count Q5:", min_count)
    votes_thresh = 200000
    print("Votes threshold Q8:", votes_thresh)
    fallback_n = 10
    print("Fallback top N Q8:", fallback_n)
    invent_limit = 50
    print("Invent", invent_limit)
    runs = 3
    print("Runs:", runs)

    bench_items = [
        ("Q1 - Filmography", lambda: (lambda: filmsByActor(conn, actor_name, use_indexes=False))),
        ("Q2 - Top N films", lambda: (lambda: bestFilmsFilter(conn, genre, start_year, end_year, N, use_indexes=False))),
        ("Q3 - Multi-role actors", lambda: (lambda: charactersByActor(conn, use_indexes=False))),
        ("Q4 - Collaborations", lambda: (lambda: filmsTogether(conn, actor_name, use_indexes=False))),
        ("Q5 - Popular genres", lambda: (lambda: bestMoviesMetrics(conn, min_rating, min_count, use_indexes=False))),
        ("Q6 - Career by decade", lambda: (lambda: bestByDecade(conn, actor_name, limit_decades=None, use_indexes=False))),
        ("Q7 - Movies podium", lambda: (lambda: moviesPodium(conn, top_k=podium_k, use_indexes=False))),
        ("Q8 - Breakout careers", lambda: (lambda: famousByMovie(conn, votes_threshold=votes_thresh, fallback_top_n=fallback_n, use_indexes=False))),
        ("Q9 - Free query (top actors by genre)", lambda: (lambda: top_actors_by_genre(conn, genre=genre, limit=invent_limit, use_indexes=False))),
    ]

    results_no_idx = []
    for label, builder in bench_items:
        callable_fn = builder()
        ms = _time_callable_avg(callable_fn, runs=runs)
        if ms is None:
            print(f"{label} (no indexes): ERR")
        else:
            print(f"{label} (no indexes): {ms:.2f} ms")
        results_no_idx.append((label, ms))

    create_indexes(conn)

    results_with_idx = []
    for label, _ in bench_items:
        if label == "Q1 - Filmography":
            callable_fn = lambda: filmsByActor(conn, actor_name, use_indexes=True)
        elif label == "Q2 - Top N films":
            callable_fn = lambda: bestFilmsFilter(conn, genre, start_year, end_year, N, use_indexes=True)
        elif label == "Q3 - Multi-role actors":
            callable_fn = lambda: charactersByActor(conn, use_indexes=True)
        elif label == "Q4 - Collaborations":
            callable_fn = lambda: filmsTogether(conn, actor_name, use_indexes=True)
        elif label == "Q5 - Popular genres":
            callable_fn = lambda: bestMoviesMetrics(conn, min_rating, min_count, use_indexes=True)
        elif label == "Q6 - Career by decade":
            callable_fn = lambda: bestByDecade(conn, actor_name, limit_decades=None, use_indexes=True)
        elif label == "Q7 - Movies podium":
            callable_fn = lambda: moviesPodium(conn, top_k=podium_k, use_indexes=True)
        elif label == "Q8 - Breakout careers":
            callable_fn = lambda: famousByMovie(conn, votes_threshold=votes_thresh, fallback_top_n=fallback_n, use_indexes=True)
        elif label == "Q9 - Free query (top actors by genre)":
            callable_fn = lambda: top_actors_by_genre(conn, genre=genre, limit=invent_limit, use_indexes=True)
        else:
            callable_fn = builder()
        ms = _time_callable_avg(callable_fn, runs=runs)
        if ms is None:
            print(f"{label} (with indexes): ERR")
        else:
            print(f"{label} (with indexes): {ms:.2f} ms")
        results_with_idx.append((label, ms))

    rows = []
    for (lbl, before_ms), (_lbl2, after_ms) in zip(results_no_idx, results_with_idx):
        b = "ERR" if before_ms is None else f"{before_ms:.2f}"
        a = "ERR" if after_ms is None else f"{after_ms:.2f}"
        if before_ms and after_ms:
            gain = ((before_ms - after_ms) / before_ms) * 100.0
            g = f"{gain:.1f}%"
        else:
            g = "ERR"
        rows.append([lbl, b, a, g])

    print("\n=== Benchmark table (ms) ===")
    _print_table(["Request", "No index (ms)", "With index (ms)", "Gain (%)"], rows)

    conn.close()

if __name__ == "__main__":
    main_benchmark()
