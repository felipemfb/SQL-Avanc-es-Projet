import time
from pymongo import MongoClient
from typing import List, Dict, Any
from pprint import pprint

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB_NAME = "cineexplorer"

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

def timed(label: str, fn):
    start = time.perf_counter()
    res = fn()
    end = time.perf_counter()
    print(f"{label}: {(end - start) * 1000:.2f} ms")
    return res

def filmsByActor(db, actor_name: str) -> List[Dict[str, Any]]:
    pipeline = [
        {"$match": {"primaryname": {"$regex": f"^{actor_name}$", "$options": "i"}}},

        {"$lookup": {
            "from": "principals",
            "localField": "pid",
            "foreignField": "pid",
            "as": "p"
        }},
        {"$unwind": {"path": "$p", "preserveNullAndEmptyArrays": False}},

        {"$lookup": {
            "from": "movies",
            "localField": "p.mid",
            "foreignField": "mid",
            "as": "m"
        }},
        {"$unwind": {"path": "$m", "preserveNullAndEmptyArrays": True}},

        {"$project": {
            "_id": 0,
            "actor_name": "$primaryname",
            "mid": "$p.mid",
            "title": "$m.primarytitle",
            "year": {"$toInt": {"$ifNull": ["$m.startyear", "0"]}},
            "category": "$p.category",
            "job": "$p.job"
        }},

        {"$sort": {"year": -1, "title": 1}}
    ]
    return list(db.persons.aggregate(pipeline))

def bestFilmsFilter(db, genre: str, start_year: int, end_year: int, top_n: int):
    pipeline = [
        {"$match": {"genre": {"$regex": f"^{genre}$", "$options": "i"}}},

        {"$lookup": {
            "from": "movies",
            "localField": "mid",
            "foreignField": "mid",
            "as": "m"
        }},
        {"$unwind": {"path": "$m", "preserveNullAndEmptyArrays": True}},

        {"$match": {
            "$expr": {
                "$and": [
                    {"$gte": [{"$toInt": {"$ifNull": ["$m.startyear", "0"]}}, start_year]},
                    {"$lte": [{"$toInt": {"$ifNull": ["$m.startyear", "0"]}}, end_year]}
                ]
            }
        }},

        {"$lookup": {
            "from": "ratings",
            "localField": "mid",
            "foreignField": "mid",
            "as": "r"
        }},
        {"$unwind": {"path": "$r", "preserveNullAndEmptyArrays": False}},

        {"$project": {
            "_id": 0,
            "mid": "$mid",
            "title": "$m.primarytitle",
            "year": {"$toInt": {"$ifNull": ["$m.startyear", "0"]}},
            "avgRating": {"$toDouble": {"$ifNull": ["$r.averagerating", "0"]}},
            "numVotes": {"$toInt": {"$ifNull": ["$r.numvotes", "0"]}}
        }},

        {"$sort": {"avgRating": -1, "numVotes": -1}},
        {"$limit": top_n}
    ]
    return list(db.genres.aggregate(pipeline))

def charactersByActor(db):
    pipeline = [
        {"$group": {
            "_id": {"pid": "$pid", "mid": "$mid"},
            "roles": {"$addToSet": "$name"}
        }},

        {"$match": {"$expr": {"$gt": [{"$size": "$roles"}, 1]}}},

        {"$lookup": {
            "from": "persons",
            "localField": "_id.pid",
            "foreignField": "pid",
            "as": "p"
        }},
        {"$unwind": {"path": "$p", "preserveNullAndEmptyArrays": False}},

        {"$lookup": {
            "from": "movies",
            "localField": "_id.mid",
            "foreignField": "mid",
            "as": "m"
        }},
        {"$unwind": {"path": "$m", "preserveNullAndEmptyArrays": True}},

        {"$project": {
            "_id": 0,
            "pid": "$_id.pid",
            "actor_name": "$p.primaryname",
            "mid": "$_id.mid",
            "title": "$m.primarytitle",
            "roles_count": {"$size": "$roles"}
        }},
        {"$sort": {"roles_count": -1, "actor_name": 1}}
    ]
    return list(db.characters.aggregate(pipeline))

def filmsTogether(db, actor_name: str):
    actor = db.persons.find_one({"primaryname": {"$regex": f"^{actor_name}$", "$options": "i"}}, {"pid": 1})
    if not actor:
        return []

    pipeline = [
        {"$match": {"pid": actor["pid"]}},
        {"$lookup": {
            "from": "directors",
            "localField": "mid",
            "foreignField": "mid",
            "as": "d"
        }},
        {"$unwind": {"path": "$d", "preserveNullAndEmptyArrays": False}},
        {"$lookup": {
            "from": "persons",
            "localField": "d.pid",
            "foreignField": "pid",
            "as": "p"
        }},
        {"$unwind": {"path": "$p", "preserveNullAndEmptyArrays": False}},
        {"$group": {
            "_id": "$p.pid",
            "director_name": {"$first": "$p.primaryname"},
            "films_together": {"$sum": 1}
        }},
        {"$sort": {"films_together": -1, "director_name": 1}}
    ]
    return list(db.principals.aggregate(pipeline))

def bestMoviesMetrics(db, min_rating: float = 7.0, min_count: int = 50):
    pipeline = [
        {"$lookup": {
            "from": "ratings",
            "localField": "mid",
            "foreignField": "mid",
            "as": "r"
        }},
        {"$unwind": {"path": "$r", "preserveNullAndEmptyArrays": False}},
        {"$group": {
            "_id": "$genre",
            "avg_rating": {"$avg": {"$toDouble": {"$ifNull": ["$r.averagerating", "0"]}}},
            "count": {"$sum": 1}
        }},
        {"$match": {"avg_rating": {"$gt": min_rating}, "count": {"$gt": min_count}}},
        {"$sort": {"avg_rating": -1}}
    ]
    return list(db.genres.aggregate(pipeline))

def bestByDecade(db, actor_name: str):
    actor = db.persons.find_one({"primaryname": {"$regex": f"^{actor_name}$", "$options": "i"}}, {"pid": 1})
    if not actor:
        return []

    pipeline = [
        {"$match": {"pid": actor["pid"]}},
        {"$lookup": {
            "from": "movies",
            "localField": "mid",
            "foreignField": "mid",
            "as": "m"
        }},
        {"$unwind": {"path": "$m", "preserveNullAndEmptyArrays": False}},
        {"$match": {"$expr": {"$ne": [{"$ifNull": ["$m.startyear", None]}, None]}}},
        {"$lookup": {
            "from": "ratings",
            "localField": "mid",
            "foreignField": "mid",
            "as": "r"
        }},
        {"$unwind": {"path": "$r", "preserveNullAndEmptyArrays": False}},
        {"$project": {
            "decade": {
                "$multiply": [
                    {"$floor": {"$divide": [{"$toInt": {"$ifNull": ["$m.startyear", "0"]}}, 10]}}, 10
                ]
            },
            "rating": {"$toDouble": {"$ifNull": ["$r.averagerating", "0"]}}
        }},
        {"$group": {"_id": "$decade", "count": {"$sum": 1}, "avg_rating": {"$avg": "$rating"}}},
        {"$sort": {"_id": -1}}
    ]
    return list(db.principals.aggregate(pipeline))

def moviesPodium(db, top_k: int):
    pipeline = [
        {"$lookup": {"from": "ratings", "localField": "mid", "foreignField": "mid", "as": "r"}},
        {"$unwind": {"path": "$r", "preserveNullAndEmptyArrays": False}},

        {"$lookup": {"from": "movies", "localField": "mid", "foreignField": "mid", "as": "m"}},
        {"$unwind": {"path": "$m", "preserveNullAndEmptyArrays": False}},

        {"$project": {
            "genre": 1,
            "mid": 1,
            "title": "$m.primarytitle",
            "avgRating": {"$toDouble": {"$ifNull": ["$r.averagerating", "0"]}},
            "numVotes": {"$toInt": {"$ifNull": ["$r.numvotes", "0"]}}
        }},

        {"$group": {
            "_id": "$genre",
            "movies": {
                "$topN": {
                    "output": {
                        "mid": "$mid",
                        "title": "$title",
                        "avgRating": "$avgRating",
                        "numVotes": "$numVotes"
                    },
                    "sortBy": {"avgRating": -1, "numVotes": -1},
                    "n": top_k
                }
            }
        }},
        {"$project": {"_id": 0, "genre": "$_id", "movies": "$movies"}}
    ]
    return list(db.genres.aggregate(pipeline, allowDiskUse=True))

def famousByMovie(db, votes_threshold: int = 200000):
    pipeline = [
        {"$lookup": {
            "from": "ratings",
            "localField": "mid",
            "foreignField": "mid",
            "as": "r"
        }},
        {"$unwind": {"path": "$r", "preserveNullAndEmptyArrays": False}},
        {"$match": {"$expr": {"$gte": [{"$toInt": {"$ifNull": ["$r.numvotes", "0"]}}, votes_threshold]}}},

        {"$lookup": {
            "from": "persons",
            "localField": "pid",
            "foreignField": "pid",
            "as": "p"
        }},
        {"$unwind": {"path": "$p", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "pid": "$pid",
            "name": "$p.primaryname",
            "mid": "$mid",
            "numVotes": {"$toInt": {"$ifNull": ["$r.numvotes", "0"]}}
        }}
    ]
    return list(db.principals.aggregate(pipeline))

def top_actors_by_genre(db, genre: str, limit: int):
    pipeline = [
        {"$lookup": {
            "from": "genres",
            "localField": "mid",
            "foreignField": "mid",
            "as": "g"
        }},
        {"$unwind": {"path": "$g", "preserveNullAndEmptyArrays": False}},
        {"$match": {"g.genre": {"$regex": f"^{genre}$", "$options": "i"}}},

        {"$lookup": {
            "from": "ratings",
            "localField": "mid",
            "foreignField": "mid",
            "as": "r"
        }},
        {"$unwind": {"path": "$r", "preserveNullAndEmptyArrays": False}},

        {"$lookup": {
            "from": "persons",
            "localField": "pid",
            "foreignField": "pid",
            "as": "p"
        }},
        {"$unwind": {"path": "$p", "preserveNullAndEmptyArrays": True}},

        {"$group": {
            "_id": "$pid",
            "name": {"$first": "$p.primaryname"},
            "appearances": {"$sum": 1},
            "avgRating": {"$avg": {"$toDouble": {"$ifNull": ["$r.averagerating", "0"]}}}
        }},
        {"$match": {"appearances": {"$gte": 2}}},
        {"$sort": {"avgRating": -1, "appearances": -1}},
        {"$limit": limit}
    ]
    return list(db.principals.aggregate(pipeline))

if __name__ == "__main__":
    actor_name = "Tom Hanks"
    genre = "Drama"
    print(f"Running queries on MongoDB CineExplorer database ({MONGO_DB_NAME})\n")

    print("Q1 - Filmography by actor")
    timed("Q1", lambda: pprint(filmsByActor(db, actor_name)[:5]))
    print("\nQ2 - Top N films by genre")
    timed("Q2", lambda: pprint(bestFilmsFilter(db, genre, 2000, 2025, 10)[:10]))
    print("\nQ3 - Actors with multiple roles")
    timed("Q3", lambda: pprint(charactersByActor(db)[:5]))
    print("\nQ4 - Director collaborations")
    timed("Q4", lambda: pprint(filmsTogether(db, actor_name)[:5]))
    print("\nQ5 - Popular genres")
    timed("Q5", lambda: pprint(bestMoviesMetrics(db)[:10]))
    print("\nQ6 - Career by decade")
    timed("Q6", lambda: pprint(bestByDecade(db, actor_name)))
    print("\nQ7 - Movies podium per genre")
    timed("Q7", lambda: pprint(moviesPodium(db, 3)[:10]))
    print("\nQ8 - Famous by movie")
    timed("Q8", lambda: pprint(famousByMovie(db)[:5]))
    print("\nQ9 - Top actors by genre")
    timed("Q9", lambda: pprint(top_actors_by_genre(db, genre, 50)[:10]))
    print("\nAll queries executed.")