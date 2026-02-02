import time
from datetime import datetime, UTC
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, PyMongoError

REPLICA_URI = "mongodb://localhost:27017/?replicaSet=rs0"
DB_NAME = "failover_test"
COLLECTION = "events"

def connect():
    return MongoClient(REPLICA_URI, serverSelectionTimeoutMS=3000)


def get_rs_status(client):
    return client.admin.command("replSetGetStatus")


def summarize_rs(status):
    return {m["name"]: m["stateStr"] for m in status["members"]}


def print_summary(summary):
    for node, state in summary.items():
        print(f"{node:20} -> {state}")


def get_primary(summary):
    for node, state in summary.items():
        if state == "PRIMARY":
            return node
    return None

print("Test 1: Initial State Check")

client = connect()
status = get_rs_status(client)
summary = summarize_rs(status)

print_summary(summary)

primary_before = get_primary(summary)
print(f"\nDetected PRIMARY: {primary_before}")

print("Test 2: Write & Replication")

db = client[DB_NAME]
col = db[COLLECTION]

doc = {
    "event": "initial_write",
    "timestamp": datetime.now(UTC).isoformat()
}

res = col.insert_one(doc)
print(f"Inserted document id = {res.inserted_id}")

time.sleep(2)

print("Documents visible from replica set:")
for d in col.find():
    print(d)


print("Test 3: Primary Failure")

print(f"Prepare to stop the PRIMARY node: {primary_before}")

print("Waiting for PRIMARY to go down...")
election_start = None

while True:
    try:
        status = get_rs_status(connect())
        summary = summarize_rs(status)

        if get_primary(summary) != primary_before:
            election_start = time.time()
            break

    except (ServerSelectionTimeoutError, PyMongoError):
        election_start = time.time()
        break

    time.sleep(1)

print("Test 4: New Primary Election")

new_primary = None
timeout = 30
start_wait = time.time()

while True:
    if time.time() - start_wait > timeout:
        print("Timeout waiting for new PRIMARY")
        break

    try:
        client = connect()
        status = get_rs_status(client)
        summary = summarize_rs(status)
        print_summary(summary)

        new_primary = get_primary(summary)

        if new_primary and new_primary != primary_before:
            break

    except Exception:
        print("Replica set not yet stable (no PRIMARY)")

    time.sleep(2)

election_end = time.time()

print(f"Old PRIMARY : {primary_before}")
print(f"New PRIMARY : {new_primary}")
print(f"Election time: {election_end - election_start:.2f} seconds")


print("Test 5: Read Availability")

try:
    count = col.count_documents({})
    print(f"Documents accessible after failover: {count}")
except PyMongoError as e:
    print("Read failed:", e)

print("Test 6: Node Reconnection and Resync")
print(f"Prepare to restart the stopped node: {primary_before}")

for _ in range(10):
    try:
        client = connect()
        status = get_rs_status(client)
        summary = summarize_rs(status)
        print_summary(summary)

        if primary_before in summary:
            print("Rejoined replica set")

    except Exception as e:
        print("Node not yet reachable or still recovering")

    time.sleep(3)


print("Test 7: Double Failure")
print("Stop two nodes now (including PRIMARY)")

no_primary_detected = False

for _ in range(10):
    try:
        status = get_rs_status(connect())
        summary = summarize_rs(status)
        print_summary(summary)

        if get_primary(summary) is None:
            print("No PRIMARY available")
            no_primary_detected = True
            break

    except PyMongoError:
        print("Replica set unreachable")
        no_primary_detected = True

    time.sleep(3)

if no_primary_detected:
    print("\nResult: Double failure correctly caused loss of quorum.")
else:
    print("\nResult: Quorum still present (unexpected in double failure).")