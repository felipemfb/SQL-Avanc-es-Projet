import argparse
import csv
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_ORDER = [ "movies", "persons", "genres", "titles", "ratings", "directors", "writers", "principals", "characters", "knownformovies", "professions"]

def find_csv_dir(provided: str) -> Path:
    p = Path(provided)
    if p.exists():
        return p
    alt = Path.cwd() / "cineexplorer" / "data" / "csv"
    if alt.exists():
        print(f"[INFO] CSV dir '{provided}' not found. Using '{alt}'.")
        return alt
    return p

def sanitize_colname(raw: str) -> str:
    if raw is None:
        return "col"
    s = str(raw).strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    s = re.sub(r"[\"'(),]", "", s)
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-z_]", "_", s)
    if re.match(r"^\d", s):
        s = "_" + s
    if s == "":
        s = "col"
    return s.lower()

def unique_column_names(cols: List[str]) -> List[str]:
    out = []
    seen = {}
    for c in cols:
        base = c
        if base in seen:
            seen[base] += 1
            c = f"{base}_{seen[base]}"
        else:
            seen[base] = 0
        out.append(c)
    return out

def prepare_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=OFF;")
        cur.execute("PRAGMA temp_store=MEMORY;")
        cur.execute("PRAGMA foreign_keys=ON;")
        conn.commit()
    except Exception:
        pass

def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;", (table,))
    return cur.fetchone() is not None

def create_table(conn: sqlite3.Connection, table: str, cols: List[str]):
    if not cols:
        return
    if table_exists(conn, table):
        existing = [r[1] for r in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]
        for c in cols:
            if c not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{c}" TEXT;')
        conn.commit()
        return
    cols_sql = ", ".join([f'"{c}" TEXT' for c in cols])
    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({cols_sql});')
    conn.commit()
    print(f"[INFO] Created table {table} with columns: {cols}")

def get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return [r[1] for r in rows]

def normalize_value(v: str):
    if v is None:
        return None
    s = v.strip()
    if s == "" or s.lower() in ("\\n", "\\n", "\\n", "\\n", "\\n", "\\n", "\\n", "\\n", "\\n", "\\n", "\\n", "\\n", "\\N", "null", "none"):
        return None
    return s

def import_csv(conn: sqlite3.Connection, csv_path: Path, table: str, batch_size: int, verbose: bool) -> Dict[str,int]:
    stats = {"read":0, "inserted":0, "skipped_invalid":0, "skipped_error":0}
    if not csv_path.exists():
        print(f"[WARN] CSV not found: {csv_path} -> skipping {table}")
        return stats

    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        try:
            header_raw = next(reader)
        except StopIteration:
            print(f"[WARN] Empty CSV: {csv_path} -> skipping {table}")
            return stats

    sanitized = [sanitize_colname(h) for h in header_raw]
    sanitized = unique_column_names(sanitized)
    if verbose:
        print(f"[DEBUG] {csv_path.name} header_raw={header_raw} -> sanitized={sanitized}")

    create_table(conn, table, sanitized)
    table_cols = get_table_columns(conn, table)
    if not table_cols:
        print(f"[WARN] Table {table} has no columns; skipping")
        return stats

    sanitized_set = set(sanitized)
    insert_cols = [c for c in table_cols if c in sanitized_set]
    if not insert_cols:
        print(f"[WARN] No matching columns between CSV and table {table}; skipping")
        return stats

    header_index_map = {}
    for idx, h in enumerate(sanitized):
        header_index_map[h] = idx

    indices = [header_index_map[c] for c in insert_cols]

    placeholders = ",".join(["?"] * len(insert_cols))
    col_list_sql = ",".join([f'"{c}"' for c in insert_cols])
    cur = conn.cursor()

    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader, None)
        batch = []
        for rn, row in enumerate(reader, start=1):
            stats['read'] += 1
            try:
                vals = []
                for i in indices:
                    v = row[i] if i < len(row) else None
                    vals.append(normalize_value(v))
                batch.append(tuple(vals))
            except Exception:
                stats['skipped_invalid'] += 1
                if verbose:
                    print(f"[DEBUG] invalid row {csv_path.name}#{rn}: {row}")
                continue

            if len(batch) >= batch_size:
                try:
                    cur.executemany(f'INSERT INTO "{table}" ({col_list_sql}) VALUES ({placeholders})', batch)
                    conn.commit()
                    stats['inserted'] += len(batch)
                    if verbose:
                        print(f"[INFO] inserted batch {table}: {len(batch)} rows")
                except sqlite3.IntegrityError:
                    conn.rollback()
                    ins = 0
                    for b in batch:
                        try:
                            cur.execute(f'INSERT INTO "{table}" ({col_list_sql}) VALUES ({placeholders})', b)
                            ins += 1
                        except Exception:
                            stats['skipped_error'] += 1
                    conn.commit()
                    stats['inserted'] += ins
                    if verbose:
                        print(f"[WARN] batch integrity fallback {table}: inserted {ins}, skipped {len(batch)-ins}")
                except Exception as e:
                    conn.rollback()
                    stats['skipped_error'] += len(batch)
                    print(f"[WARN] batch insert error {table}: {e}")
                batch = []

        if batch:
            try:
                cur.executemany(f'INSERT INTO "{table}" ({col_list_sql}) VALUES ({placeholders})', batch)
                conn.commit()
                stats['inserted'] += len(batch)
                if verbose:
                    print(f"[INFO] inserted final batch {table}: {len(batch)} rows")
            except sqlite3.IntegrityError:
                conn.rollback()
                ins = 0
                for b in batch:
                    try:
                        cur.execute(f'INSERT INTO "{table}" ({col_list_sql}) VALUES ({placeholders})', b)
                        ins += 1
                    except Exception:
                        stats['skipped_error'] += 1
                conn.commit()
                stats['inserted'] += ins
            except Exception as e:
                conn.rollback()
                stats['skipped_error'] += len(batch)
                print(f"[WARN] final batch error {table}: {e}")

    print(f"[INFO] {table}: read={stats['read']} inserted={stats['inserted']} skipped_invalid={stats['skipped_invalid']} skipped_error={stats['skipped_error']}")
    return stats

def parse_args():
    p = argparse.ArgumentParser(description="Import IMDB CSVs into SQLite (essential)")
    p.add_argument("--db", default="cineexplorer/data/imdb.db")
    p.add_argument("--csv-dir", default="cineexplorer/data/csv")
    p.add_argument("--batch-size", type=int, default=2000)
    p.add_argument("--order", nargs="*", default=DEFAULT_ORDER)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()

def main():
    args = parse_args()
    csv_dir = find_csv_dir(args.csv_dir)
    if not csv_dir.exists():
        print(f"[ERROR] csv-dir not found: {csv_dir}")
        sys.exit(1)
    db_path = Path(args.db)
    os.makedirs(db_path.parent, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        prepare_db(conn)
        if args.dry_run:
            conn.execute("BEGIN")
            print("[INFO] dry-run: changes will be rolled back")

        overall = {"read":0, "inserted":0, "skipped_invalid":0, "skipped_error":0}
        t0 = time.time()
        for table in args.order:
            csv_file = csv_dir / f"{table}.csv"
            s = import_csv(conn, csv_file, table, args.batch_size, args.verbose)
            for k in overall:
                overall[k] += s.get(k, 0)

        if args.dry_run:
            conn.rollback()
            print("[INFO] dry-run rollback executed")
        else:
            conn.commit()

        elapsed = time.time() - t0
        print(f"[INFO] TOTAL elapsed={elapsed:.1f}s read={overall['read']} inserted={overall['inserted']} skipped_invalid={overall['skipped_invalid']} skipped_error={overall['skipped_error']}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
