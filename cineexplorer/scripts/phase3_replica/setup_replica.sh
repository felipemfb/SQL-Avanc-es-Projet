echo "Stopping existing mongod.exe files..."
taskkill //F //IM mongod.exe

echo "Starting MongoDB instances..."
start "" "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --replSet rs0 --port 27017 --dbpath "" --bind_ip localhost
start "" "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --replSet rs0 --port 27018 --dbpath "" --bind_ip localhost
start "" "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --replSet rs0 --port 27019 --dbpath "" --bind_ip localhost

echo "Waiting 5 seconds for the servers to come up..."
sleep 5

echo "Connecting to MongoDB and starting the replica set..."
"C:\Program Files\mongosh\mongosh.exe" --port 27017 <<EOF
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "localhost:27017" },
    { _id: 1, host: "localhost:27018" },
    { _id: 2, host: "localhost:27019" }
  ]
})
rs.status()
EOF

echo "Replica set started."
