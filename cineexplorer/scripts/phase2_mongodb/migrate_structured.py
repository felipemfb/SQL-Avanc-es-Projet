from __future__ import annotations
import time
import argparse
from pymongo import MongoClient, errors
from typing import List, Dict, Any, Tuple
from pprint import pprint
import sys

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB_NAME = "cineexplorer"

def now_ms() -> float:
    return time.perf_counter() * 1000.0

def timed(label: str, fn):
    t0 = now_ms()
    res = fn()
    t1 = now_ms()
    print(f"{label}: {t1 - t0:.2f} ms")
    return res


client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
try:
    client.admin.command("ping")
except Exception as e:
    print("ERROR: cannot connect to MongoDB server:", e)
    sys.exit(1)
db = client[MONGO_DB_NAME]

def ensure_indexes():
    print("Ensuring indexes (may take a few seconds)...")
    idxs = {
        "genres": [("mid", 1)],
        "ratings": [("mid", 1)],
        "directors": [("mid", 1), ("pid", 1)],
        "principals": [("mid", 1), ("pid", 1), ("category", 1)],
        "characters": [("mid", 1), ("pid", 1)],
        "writers": [("mid", 1), ("pid", 1)],
        "titles": [("mid", 1)],
        "movies": [("mid", 1)],
        "persons": [("pid", 1)]
    }
    for coll, keys in idxs.items():
        try:
            name = db[coll].create_index(keys)
            print(f"  index ensured: {coll} -> {name}")
        except Exception as e:
            print(f"  warning: could not create index on {coll}: {e}")
    try:
        db.movies_complete.create_index([("_id", 1)], unique=True)
    except Exception:
        pass

def build_pipeline_for_mids(mids: List[str]) -> List[Dict[str, Any]]:
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"mid": {"$in": mids}}},
    
        {"$lookup": {"from": "genres", "localField": "mid", "foreignField": "mid", "as": "genres_docs"}},
        {"$addFields": {"genres": {"$map": {"input": "$genres_docs", "as": "g", "in": "$$g.genre"}}}},
        {"$project": {"genres_docs": 0}},

        {"$lookup": {"from": "ratings", "localField": "mid", "foreignField": "mid", "as": "rating_doc"}},
        {"$addFields": {
            "rating": {
                "$cond": [
                    {"$gt": [{"$size": "$rating_doc"}, 0]},
                    {
                        "average": {"$toDouble": {"$ifNull": [{"$arrayElemAt": ["$rating_doc.averagerating", 0]}, "0"]}},
                        "votes": {"$toInt": {"$ifNull": [{"$arrayElemAt": ["$rating_doc.numvotes", 0]}, "0"]}}
                    },
                    None
                ]
            }
        }} ,
        {"$project": {"rating_doc": 0}},

        {"$lookup": {
            "from": "directors",
            "let": {"mid": "$mid"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$mid", "$$mid"]}}},
                {"$lookup": {"from": "persons", "localField": "pid", "foreignField": "pid", "as": "person"}},
                {"$unwind": {"path": "$person", "preserveNullAndEmptyArrays": True}},
                {"$project": {"_id": 0, "person_id": "$pid", "name": "$person.primaryname"}}
            ],
            "as": "directors"
        }},

        {"$lookup": {
            "from": "principals",
            "let": {"mid": "$mid"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [{"$eq": ["$mid", "$$mid"]}, {"$in": ["$category", ["actor", "actress"]]}]}}},
                {"$lookup": {"from": "persons", "localField": "pid", "foreignField": "pid", "as": "person"}},
                {"$unwind": {"path": "$person", "preserveNullAndEmptyArrays": True}},
                {"$lookup": {
                    "from": "characters",
                    "let": {"pmid": "$mid", "ppid": "$pid"},
                    "pipeline": [
                        {"$match": {"$expr": {"$and":[{"$eq":["$mid","$$pmid"]},{"$eq":["$pid","$$ppid"]}]}}},
                        {"$project": {"_id":0, "name":1}}
                    ],
                    "as": "chars"
                }},
                {"$project": {"_id": 0, "person_id": "$pid", "name": "$person.primaryname", "characters": {"$cond": [{"$gt":[{"$size":"$chars"},0]}, {"$map":{"input":"$chars","as":"c","in":"$$c.name"}}, []]}, "ordering": {"$toInt": {"$ifNull": ["$ordering", "0"]}}}},
                {"$sort": {"ordering": 1}}
            ],
            "as": "cast"
        }},

        {"$lookup": {"from": "titles", "let": {"mid": "$mid"}, "pipeline": [
            {"$match": {"$expr": {"$eq": ["$mid", "$$mid"]}}},
            {"$project": {"_id": 0, "region": "$region", "title": "$title"}}
        ], "as": "titles"}},

        {"$lookup": {
            "from": "writers",
            "let": {"mid": "$mid"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$mid", "$$mid"]}}},
                {"$lookup": {"from": "persons", "localField": "pid", "foreignField": "pid", "as": "person"}},
                {"$unwind": {"path": "$person", "preserveNullAndEmptyArrays": True}},
                {"$project": {"_id":0, "person_id":"$pid", "name":"$person.primaryname", "category":{"$ifNull":["$category", None]}}}
            ],
            "as": "writers_from_writers"
        }},
        {"$lookup": {
            "from": "principals",
            "let": {"mid": "$mid"},
            "pipeline": [
                {"$match": {"$expr": {"$and":[{"$eq":["$mid","$$mid"]},{"$in":["$category", ["writer","screenplay","screenwriter","author","writer/producer"]]}]}}},
                {"$lookup": {"from": "persons", "localField": "pid", "foreignField": "pid", "as": "person"}},
                {"$unwind": {"path":"$person","preserveNullAndEmptyArrays": True}},
                {"$project": {"_id":0, "person_id":"$pid", "name":"$person.primaryname", "category":{"$ifNull":["$category", None]}}}
            ],
            "as": "writers_from_principals"
        }},
        {"$addFields": {"writers": {"$cond": [{"$gt":[{"$size":"$writers_from_writers"},0]}, "$writers_from_writers", "$writers_from_principals"]}}},

        {"$project": {
            "mid": 1,
            "title": "$primarytitle",
            "year": {"$toInt": {"$ifNull": ["$startyear", "0"]}},
            "runtime": {"$toInt": {"$ifNull": ["$runtimeminutes", None]}},
            "genres": 1,
            "rating": 1,
            "directors": 1,
            "cast": 1,
            "writers": 1,
            "titles": 1
        }},
        {"$set": {"_id": "$mid"}},
        {"$merge": {"into": "movies_complete", "whenMatched": "replace", "whenNotMatched": "insert"}}
    ]
    return pipeline

def build_movies_complete_in_batches(limit: int = None, batch_size: int = 1000, resume: bool = True, max_retries: int = 1):
    total_available = db.movies.count_documents({})
    total_to_process = total_available if (limit is None) else min(limit, total_available)
    print(f"Total movies available: {total_available}. Will process: {total_to_process} (limit={limit})")
    cursor = db.movies.find({}, {"mid": 1, "_id": 0}).sort("mid", 1)
    if limit:
        cursor = cursor.limit(limit)

    mids_batch: List[str] = []
    processed = 0
    start_all = now_ms()

    try:
        for doc in cursor:
            mids_batch.append(doc["mid"])
            if len(mids_batch) >= batch_size:
                processed += len(mids_batch)
                print(f"[{processed}/{total_to_process}] Batch size {len(mids_batch)} -> preparing...")
                _run_batch(mids_batch, resume, max_retries)
                mids_batch = []
        if mids_batch:
            processed += len(mids_batch)
            print(f"[{processed}/{total_to_process}] Final batch size {len(mids_batch)} -> preparing...")
            _run_batch(mids_batch, resume, max_retries)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except Exception as e:
        print("ERROR during batch processing:", e)
    elapsed_all = now_ms() - start_all
    print(f"All batches processed in {elapsed_all:.2f} ms (total).")


def _run_batch(mids_batch: List[str], resume: bool, max_retries: int):
    to_process = mids_batch
    if resume:
        existing = list(db.movies_complete.find({"_id": {"$in": mids_batch}}, {"_id": 1}))
        existing_ids = {d["_id"] for d in existing}
        to_process = [m for m in mids_batch if m not in existing_ids]
        if not to_process:
            print("  all mids in batch already exist in movies_complete -> skipping")
            return
        print(f"  {len(mids_batch) - len(to_process)} already present, {len(to_process)} to process")

    pipeline = build_pipeline_for_mids(to_process)
    attempt = 0
    while attempt <= max_retries:
        attempt += 1
        try:
            t0 = now_ms()
            result_cursor = db.movies.aggregate(pipeline, allowDiskUse=True)
            try:
                for _ in result_cursor:
                    pass
            except errors.PyMongoError:
                pass
            t1 = now_ms()
            print(f"  Batch aggregation finished in {(t1 - t0):.2f} ms")
            return
        except errors.PyMongoError as e:
            print(f"  Batch aggregation error on attempt {attempt}: {e}")
            if attempt > max_retries:
                print("  max retries exceeded, attempting per-mid fallback for this batch...")
                _process_each_mid_individually(to_process)
                return
            else:
                print("  retrying batch once after short pause...")
                time.sleep(0.5)


def _process_each_mid_individually(mids: List[str]):
    print("  Starting per-mid fallback (slow).")
    for i, mid in enumerate(mids, start=1):
        print(f"    [{i}/{len(mids)}] Processing mid={mid} ...", end="", flush=True)
        single_pipeline = build_pipeline_for_mids([mid])
        try:
            t0 = now_ms()
            cursor = db.movies.aggregate(single_pipeline, allowDiskUse=True)
            try:
                for _ in cursor:
                    pass
            except errors.PyMongoError:
                pass
            t1 = now_ms()
            print(f" done in {(t1 - t0):.2f} ms")
        except Exception as e:
            print(f" ERROR: {e}")

def get_coll_stats(names: List[str]):
    stats = {}
    for n in names:
        try:
            s = db.command("collstats", n)
            stats[n] = {
                "count": s.get("count", 0),
                "storageSize": s.get("storageSize", 0),
                "size": s.get("size", 0)
            }
        except Exception as e:
            stats[n] = {"error": str(e)}
    return stats


def retrieve_and_compare_one(mid: str) -> Tuple[Dict[str,Any], Dict[str,Any], float, float]:
    t0 = now_ms()
    doc_mc = db.movies_complete.find_one({"_id": mid}, {"_id":0})
    t1 = now_ms()
    time_mc = t1 - t0

    t0 = now_ms()
    movie = db.movies.find_one({"mid": mid}, {"_id":0})
    assembled = None
    if movie:
        genres = [g.get("genre") for g in db.genres.find({"mid": mid}, {"genre":1})]
        rating_doc = db.ratings.find_one({"mid": mid}, {"_id":0})
        rating = None
        if rating_doc:
            rating = {"average": float(rating_doc.get("averagerating") or 0.0), "votes": int(rating_doc.get("numvotes") or 0)}
        dirs = []
        for d in db.directors.find({"mid": mid}, {"pid":1}):
            p = db.persons.find_one({"pid": d["pid"]}, {"_id":0, "pid":1, "primaryname":1})
            if p:
                dirs.append({"person_id": p["pid"], "name": p.get("primaryname")})
        cast = []
        for pr in db.principals.find({"mid": mid, "category": {"$in": ["actor", "actress"]}}, {"pid":1, "ordering":1}):
            p = db.persons.find_one({"pid": pr["pid"]}, {"_id":0, "pid":1, "primaryname":1})
            chars = [c.get("name") for c in db.characters.find({"mid": mid, "pid": pr["pid"]}, {"name":1})]
            ordering = int(pr.get("ordering") or 0)
            cast.append({"person_id": pr["pid"], "name": p.get("primaryname") if p else None, "characters": chars, "ordering": ordering})
        cast.sort(key=lambda x: x.get("ordering", 0))
        writers = []
        wdocs = list(db.writers.find({"mid": mid}))
        if wdocs:
            for w in wdocs:
                p = db.persons.find_one({"pid": w["pid"]}, {"_id":0, "pid":1, "primaryname":1})
                writers.append({"person_id": w["pid"], "name": p.get("primaryname") if p else None, "category": w.get("category")})
        else:
            for pr in db.principals.find({"mid": mid, "category": {"$in": ["writer", "screenplay", "screenwriter"]}}):
                p = db.persons.find_one({"pid": pr["pid"]}, {"_id":0, "pid":1, "primaryname":1})
                writers.append({"person_id": pr["pid"], "name": p.get("primaryname") if p else None, "category": pr.get("category")})
        titles = list(db.titles.find({"mid": mid}, {"_id":0, "region":1, "title":1}))
        assembled = {
            "mid": movie.get("mid"),
            "title": movie.get("primarytitle"),
            "year": int(movie.get("startyear")) if movie.get("startyear") else None,
            "runtime": int(movie.get("runtimeminutes")) if movie.get("runtimeminutes") else None,
            "genres": genres,
            "rating": rating,
            "directors": dirs,
            "cast": cast,
            "writers": writers,
            "titles": titles
        }
    t1 = now_ms()
    time_multi = t1 - t0
    return doc_mc, assembled, time_mc, time_multi


def pretty_bytes(n: int) -> str:
    for unit in ("B","KB","MB","GB","TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def parse_args():
    p = argparse.ArgumentParser(description="Build movies_complete in batches to avoid large single aggregation")
    p.add_argument("--limit", type=int, default=None, help="Limit number of movies to process (for debugging)")
    p.add_argument("--batch-size", type=int, default=1000, help="Number of mids per aggregation batch (200-1000 recommended)")
    p.add_argument("--no-resume", dest="resume", action="store_false", help="Don't skip existing movies_complete docs")
    p.add_argument("--max-retries", type=int, default=1, help="Number of retries for a failing batch before per-mid fallback")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"Building movies_complete (limit={args.limit}) from DB: {MONGO_DB_NAME}")
    timed("Ensure indexes", ensure_indexes)
    timed("Build movies_complete (batched)", lambda: build_movies_complete_in_batches(limit=args.limit, batch_size=args.batch_size, resume=args.resume, max_retries=args.max_retries))

    cols_flat = ["movies","genres","ratings","directors","principals","characters","writers","titles","persons"]
    cols = cols_flat + ["movies_complete"]
    stats = get_coll_stats(cols)
    print("\nCollection stats (counts + storageSize):")
    for c in cols:
        info = stats.get(c, {})
        if "error" in info:
            print(f"  {c}: ERROR: {info['error']}")
            continue
        print(f"  {c}: count={info['count']}, storageSize={pretty_bytes(info['storageSize'])}, size={pretty_bytes(info.get('size',0))}")

    sample = db.movies.find_one({}, {"mid":1})
    if sample:
        mid = sample["mid"]
        print(f"\nExample mid for timing: {mid}")
        doc_mc, assembled_doc, t_mc, t_multi = retrieve_and_compare_one(mid)
        print(f"Fetch from movies_complete: {t_mc:.2f} ms, found={doc_mc is not None}")
        print(f"Assemble via N queries: {t_multi:.2f} ms, found={assembled_doc is not None}")
        print("\n--- movies_complete preview (short) ---")
        if doc_mc:
            pprint({k: doc_mc.get(k) for k in ("mid","title","year","rating","genres")})
        print("\n--- assembled (N queries) preview (short) ---")
        if assembled_doc:
            pprint({k: assembled_doc.get(k) for k in ("mid","title","year","rating","genres")})
    else:
        print("No movies found to test retrieval timings.")
    print("\nDone.")