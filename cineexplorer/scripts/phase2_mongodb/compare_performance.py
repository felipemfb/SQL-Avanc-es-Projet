import random
import argparse
from pymongo import MongoClient
from time import perf_counter
from typing import List

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB_NAME = "cineexplorer"

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[MONGO_DB_NAME]


def time_fetch_movies_complete(mid: str) -> float:
    t0 = perf_counter()
    _ = db.movies_complete.find_one({"_id": mid}, {"_id":0})
    t1 = perf_counter()
    return (t1 - t0) * 1000.0

def pretty_bytes(n: int) -> str:
    for unit in ("B","KB","MB","GB","TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"

def time_assemble_multi(mid: str) -> float:
    t0 = perf_counter()
    movie = db.movies.find_one({"mid": mid}, {"_id":0})
    if movie:
        _ = list(db.genres.find({"mid": mid}, {"genre":1}))
        _ = db.ratings.find_one({"mid": mid}, {"_id":0})
        for d in db.directors.find({"mid": mid}, {"pid":1}):
            _ = db.persons.find_one({"pid": d["pid"]}, {"primaryname":1})
        for pr in db.principals.find({"mid": mid, "category": {"$in": ["actor", "actress"]}}, {"pid":1, "ordering":1}):
            _ = db.persons.find_one({"pid": pr["pid"]}, {"primaryname":1})
            _ = list(db.characters.find({"mid": mid, "pid": pr["pid"]}, {"name":1}))
        _ = list(db.titles.find({"mid": mid}, {"region":1, "title":1}))
    t1 = perf_counter()
    return (t1 - t0) * 1000.0


def get_storage_stats():
    cols_flat = ["movies","genres","ratings","directors","principals","characters","writers","titles","persons"]
    stats = {}
    total_flat = 0
    for c in cols_flat:
        s = db.command("collstats", c)
        stats[c] = s.get("storageSize", 0)
        total_flat += stats[c]
    stats["movies_complete"] = db.command("collstats", "movies_complete").get("storageSize", 0)
    stats["total_flat"] = total_flat
    return stats


def run_compare(sample_mids: List[str], trials: int = 1):
    res = []
    for mid in sample_mids:
        mc_times = [time_fetch_movies_complete(mid) for _ in range(trials)]
        multi_times = [time_assemble_multi(mid) for _ in range(trials)]
        res.append((mid, sum(mc_times)/len(mc_times), sum(multi_times)/len(multi_times)))
    return res


def parse_args_compare():
    p = argparse.ArgumentParser(description="Compare movies_complete vs flat retrieval times")
    p.add_argument("--sample-size", type=int, default=50, help="Number of movies to sample for timing")
    p.add_argument("--trials", type=int, default=1, help="Number of trials per movie to average")
    p.add_argument("--random", action="store_true", help="Sample random mids instead of first N")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args_compare()
    total = db.movies.count_documents({})
    print(f"Total movies in DB: {total}")
    cursor = db.movies.find({}, {"mid":1, "_id":0}).sort("mid",1)
    mids = [d["mid"] for d in cursor.limit(args.sample_size)] if not args.random else [d["mid"] for d in db.movies.aggregate([{"$sample": {"size": args.sample_size}}, {"$project": {"mid":1, "_id":0}}])]

    print(f"Timing retrieval for {len(mids)} movies (trials={args.trials})...")
    results = run_compare(mids, trials=args.trials)
    avg_mc = sum(r[1] for r in results)/len(results)
    avg_multi = sum(r[2] for r in results)/len(results)
    print(f"Average movies_complete fetch time: {avg_mc:.2f} ms")
    print(f"Average assemble (N queries) time: {avg_multi:.2f} ms")

    print("\nPer-movie sample results (mid, mc_ms, multi_ms):")
    for mid, mc_ms, multi_ms in results:
        print(mid, f"{mc_ms:.2f} ms", f"{multi_ms:.2f} ms")

    stats = get_storage_stats()
    print("\nStorage sizes:")
    for k,v in stats.items():
        print(k, pretty_bytes(v))

    print("\nDone.")