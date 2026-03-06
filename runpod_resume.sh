#!/bin/bash
# runpod_resume.sh - Run this script whenever your Spot Instance restarts!
# Usage: bash /workspace/duchess/runpod_resume.sh

set -e

echo "=== Resuming Duchess RL Loop on RunPod ==="

# 1. System Dependencies
echo "[1/4] Installing system dependencies..."
apt-get update
apt-get install -y postgresql postgresql-contrib libpq-dev git cmake g++ tmux sudo python3-venv

# 2. Start PostgreSQL and Restore Database
echo "[2/4] Starting PostgreSQL and Restoring Database..."
service postgresql start

# Create the user and an empty database
su - postgres -c "psql -c \"CREATE USER root WITH SUPERUSER;\"" || true
su - postgres -c "createdb duchess_db" || true

# Restore the most recent backup if it exists
if [ -f "/workspace/duchess_db_backup.sql" ]; then
    echo "Found existing database backup! Restoring..."
    # Drop the empty db and recreate it so the restore applies cleanly
    su - postgres -c "dropdb duchess_db"
    su - postgres -c "createdb duchess_db"
    pg_restore -U root -d duchess_db -1 /workspace/duchess_db_backup.sql || psql -U root -d duchess_db -f /workspace/duchess_db_backup.sql
    echo "Database restored successfully!"
else
    echo "No database backup found. Starting fresh."
fi

# 3. Setup Python and Compile Engine
echo "[3/4] Setting up Python env and recompiling the C++ Engine..."
cd /workspace/duchess

git submodule update --init --recursive

if [ ! -d "py-duchess" ]; then
    python3 -m venv py-duchess
fi
source py-duchess/bin/activate
pip install -r requirements.txt

# Initialize Database Schema if creating a fresh database
alembic upgrade head

cd engine
rm -rf build
mkdir build && cd build
cmake .. -DPython3_EXECUTABLE="/workspace/duchess/py-duchess/bin/python"
make -j$(nproc)
cd ../..

# 4. Start the Backup Daemon
echo "[4/4] Starting continuous database backup daemon..."
cat << 'EOF' > /workspace/backup_db.sh
#!/bin/bash
while true; do
    pg_dump -U root duchess_db > /workspace/duchess_tmp.sql && mv /workspace/duchess_tmp.sql /workspace/duchess_db_backup.sql
    sleep 600
done
EOF
chmod +x /workspace/backup_db.sh
nohup /workspace/backup_db.sh > /workspace/backup.log 2>&1 &

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "Your database is restored and the engine is compiled."
echo "To resume your training loop, run these exact commands:"
echo ""
echo "    cd /workspace/duchess"
echo "    tmux new -s training"
echo "    source py-duchess/bin/activate"
LATEST_WEIGHTS=$(ls -v /workspace/duchess/nnue/duchess_iter_*.bin 2>/dev/null | tail -n 1)
if [ -z "$LATEST_WEIGHTS" ]; then
    START_ITER=1
    START_NNUE="nnue/duchess.bin"
else
    # Extract the number from duchess_iter_X.bin
    LAST_NUM=$(echo "$LATEST_WEIGHTS" | grep -o -E '[0-9]+' | tail -n 1)
    START_ITER=$((LAST_NUM + 1))
    START_NNUE="nnue/duchess_iter_${LAST_NUM}.bin"
fi

echo "    python nnue/rl_loop.py \\"
echo "        --iterations 35 \\"
echo "        --games-per-iter 5000 \\"
echo "        --threads \$(nproc) \\"
echo "        --epochs-per-iter 20 \\"
echo "        --start-iter $START_ITER \\"
echo "        --start-nnue $START_NNUE \\"
echo "        --book /workspace/duchess/assets/gm2001.bin \\"
echo "        --syzygy /workspace/Syzygy \\"
echo "        --gauntlet-engine /workspace/Queen405x64/queen \\"
echo "        --gauntlet-games 20"
echo "========================================="
