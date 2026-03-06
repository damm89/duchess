#!/bin/bash
# runpod_resume.sh - Run this script whenever your Spot Instance restarts!
# Usage: bash /workspace/duchess/runpod_resume.sh

set -e

echo "=== Resuming Duchess RL Loop on RunPod ==="

# 1. System Dependencies
echo "[1/5] Installing system dependencies..."
apt-get update -qq
apt-get install -y postgresql postgresql-contrib libpq-dev git git-lfs cmake g++ tmux sudo python3-venv stockfish

# 2. Start PostgreSQL and Restore Database
echo "[2/5] Starting PostgreSQL and restoring database..."
service postgresql start

su - postgres -c "psql -c \"CREATE USER root WITH SUPERUSER;\"" || true
su - postgres -c "createdb duchess_db" || true

if [ -f "/workspace/duchess_db_backup.sql" ]; then
    echo "Found existing database backup — restoring..."
    su - postgres -c "dropdb duchess_db"
    su - postgres -c "createdb duchess_db"
    pg_restore -U root -d duchess_db -1 /workspace/duchess_db_backup.sql || psql -U root -d duchess_db -f /workspace/duchess_db_backup.sql
    echo "Database restored."
else
    echo "No backup found — starting fresh."
fi

# 3. Setup Python, pull latest code, compile engine
echo "[3/5] Setting up Python env and compiling engine..."
cd /workspace/duchess

git config --global user.name "Duchess RunPod"
git config --global user.email "runpod@duchess.test"
git config --global credential.helper store
git lfs install
git pull origin main
git submodule update --init --recursive

if [ ! -d "py-duchess" ]; then
    python3 -m venv py-duchess
fi
source py-duchess/bin/activate
pip install -r requirements.txt -q

alembic upgrade head

cd engine
rm -rf build
mkdir build && cd build
cmake .. -DPython3_EXECUTABLE="/workspace/duchess/py-duchess/bin/python" -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
cd ../..

# 4. Start the database backup daemon
echo "[4/5] Starting database backup daemon..."
cat << 'EOF' > /workspace/backup_db.sh
#!/bin/bash
while true; do
    pg_dump -U root duchess_db > /workspace/duchess_tmp.sql && mv /workspace/duchess_tmp.sql /workspace/duchess_db_backup.sql
    sleep 600
done
EOF
chmod +x /workspace/backup_db.sh
nohup /workspace/backup_db.sh > /workspace/backup.log 2>&1 &

# 5. Launch the training loop in a tmux session
echo "[5/5] Launching training loop..."

# Kill any existing training session
tmux kill-session -t training 2>/dev/null || true

tmux new-session -d -s training -x 220 -y 50

tmux send-keys -t training "source /workspace/duchess/py-duchess/bin/activate" Enter
tmux send-keys -t training "cd /workspace/duchess" Enter
tmux send-keys -t training "python nnue/rl_loop.py \
    --iterations 35 \
    --games-per-iter 5000 \
    --threads \$(nproc) \
    --selfplay-depth 6 \
    --epochs-per-iter 30 \
    --book /workspace/duchess/assets/gm2001.bin \
    --syzygy /workspace/Syzygy \
    --gauntlet-engine /workspace/Queen405x64/queen \
    --gauntlet-games 20 \
    --gauntlet-threads 4 \
    --gauntlet-depth 6 \
    --stockfish /usr/games/stockfish \
    --distill-pgn /workspace/lichess_elite.pgn \
    --distill-download \
    --distill-games 50000 \
    --distill-workers \$(nproc)" Enter

echo ""
echo "========================================="
echo "✅ Setup complete — training is running!"
echo ""
echo "  Watch:  tmux attach -t training"
echo "  Detach: Ctrl+B then D"
echo "========================================="
