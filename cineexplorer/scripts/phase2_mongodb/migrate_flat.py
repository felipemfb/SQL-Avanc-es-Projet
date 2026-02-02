import os
import sqlite3
from pymongo import MongoClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SQLITE_DB_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "../../data/imdb.db")
)

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB_NAME = "cineexplorer"

def migrate_table(sqlite_conn, mongo_db, table_name: str):
    cursor = sqlite_conn.cursor()

    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]

    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    if not rows:
        print(f"Skipped empty table '{table_name}'")
        return
    
    documents = [
        dict(zip(columns, row))
        for row in rows
    ]

    mongo_db[table_name].insert_many(documents)

    print(f"Migrated table '{table_name}': {len(documents)} documents")


def main():
    print("Connecting to SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)

    print("Connecting to MongoDB...")
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB_NAME]

    tables = [
        "movies",
        "persons",
        "genres",
        "titles",
        "ratings",
        "directors",
        "writers",
        "principals",
        "characters",
        "knownformovies",
        "professions"
    ]


    print("\nStarting migration...\n")
    for table in tables:
        mongo_db[table].drop()
        migrate_table(sqlite_conn, mongo_db, table)

    print("\nMigration completed\n")

    print("Verification of document counts:")
    for table in tables:
        count = mongo_db[table].estimated_document_count()
        print(f"- {table}: {count} documents")

    sqlite_conn.close()
    mongo_client.close()



if __name__ == "__main__":
    main()