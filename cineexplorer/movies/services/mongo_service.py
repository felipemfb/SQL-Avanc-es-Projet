from pymongo import MongoClient

def get_mongo_client():
    """Connect to MongoDB replica set."""
    try:
        client = MongoClient(
            ["localhost:27017", "localhost:27018", "localhost:27019"],
            replicaSet="rs0",
            serverSelectionTimeoutMS=5000
        )
        client.admin.command("ping")
        return client
    except Exception as e:
        print("MongoDB connection failed:", e)
        return None

def get_movie_count_mongo():
    """Return number of movies in MongoDB."""
    client = get_mongo_client()
    if client is None:
        return 0
    db = client["cineexplorer"]
    collection = db["movies"]
    return collection.count_documents({})
