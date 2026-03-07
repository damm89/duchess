#!/bin/bash
# runpod_resume.sh - Run this script whenever your Spot Instance restarts!
# Usage: bash /workspace/duchess/runpod_resume.sh

set -e

# Parse flags
AUTO_STOP=0
for arg in "$@"; do
    [ "$arg" = "--auto-stop" ] && AUTO_STOP=1
done

# Write stop_pod.sh — only wired up if --auto-stop is passed
cat << 'STOPEOF' > /tmp/stop_pod.sh
#!/bin/bash
echo ""
echo "!!! FATAL ERROR — requesting pod stop to avoid idle billing !!!"
if [ -n "${RUNPOD_POD_ID:-}" ] && [ -n "${RUNPOD_API_KEY:-}" ]; then
    curl -s -X POST "https://api.runpod.io/graphql" \
        -H "content-type: application/json" \
        -H "Authorization: Bearer $RUNPOD_API_KEY" \
        -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$RUNPOD_POD_ID\\\"}) { id } }\"}" > /dev/null
    echo "Pod stop requested."
else
    echo "Set RUNPOD_API_KEY in your pod's environment variables to enable auto-stop."
fi
STOPEOF
chmod +x /tmp/stop_pod.sh

if [ "$AUTO_STOP" = "1" ]; then
    trap /tmp/stop_pod.sh ERR
    echo "[auto-stop ON] Pod will stop on fatal error."
fi

echo "=== Resuming Duchess RL Loop on RunPod ==="

# 1. System Dependencies
echo "[1/5] Installing system dependencies..."
apt-get update -qq
apt-get install -y postgresql postgresql-contrib libpq-dev git git-lfs cmake g++ tmux sudo python3-venv

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
if [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "https://damm89:${GITHUB_TOKEN}@github.com" > ~/.git-credentials
    echo "  [✓] GitHub credentials configured via GITHUB_TOKEN env var"
elif [ -f "/workspace/.github_token" ]; then
    TOKEN=$(cat /workspace/.github_token)
    echo "https://damm89:${TOKEN}@github.com" > ~/.git-credentials
    echo "  [✓] GitHub credentials configured via /workspace/.github_token"
else
    echo ""
    read -rsp "  Enter GitHub Personal Access Token (will be saved to /workspace/.github_token): " TOKEN
    echo ""
    echo "${TOKEN}" > /workspace/.github_token
    echo "https://damm89:${TOKEN}@github.com" > ~/.git-credentials
    echo "  [✓] GitHub credentials saved."
fi
git lfs install
git pull origin main
git submodule update --init --recursive

if [ ! -d "py-duchess" ]; then
    python3 -m venv py-duchess
fi
source py-duchess/bin/activate
pip install -r requirements.txt -q

if [ ! -f ".env" ]; then
    echo "DATABASE_URL=postgresql:///duchess_db" > .env
    echo "  [✓] Created .env with DATABASE_URL"
fi
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

# Pre-flight checks — warn about missing optional paths, build flags dynamically
EXTRA_FLAGS=""

if [ -f "/workspace/Queen405x64/queen" ]; then
    EXTRA_FLAGS="$EXTRA_FLAGS --gauntlet-engine /workspace/Queen405x64/queen --gauntlet-games 20 --gauntlet-threads 4 --gauntlet-depth 6"
    echo "  [✓] Gauntlet engine: /workspace/Queen405x64/queen"
else
    echo "  [!] Queen engine not found at /workspace/Queen405x64/queen — gauntlet disabled."
fi

if [ -d "/workspace/Syzygy" ]; then
    EXTRA_FLAGS="$EXTRA_FLAGS --syzygy /workspace/Syzygy"
    echo "  [✓] Syzygy tablebases: /workspace/Syzygy"
else
    echo "  [!] Syzygy dir not found at /workspace/Syzygy — endgame tablebases disabled."
fi

if [ -f "/workspace/duchess/assets/gm2001.bin" ]; then
    EXTRA_FLAGS="$EXTRA_FLAGS --book /workspace/duchess/assets/gm2001.bin"
    echo "  [✓] Opening book: /workspace/duchess/assets/gm2001.bin"
else
    echo "  [!] Opening book not found at /workspace/duchess/assets/gm2001.bin — opening diversity disabled."
fi

# Lichess eval distillation — always enabled (no engine needed, skipped if dataset already exists)
EXTRA_FLAGS="$EXTRA_FLAGS --distill-evals-download --distill-positions 500000"
echo "  [✓] Lichess eval distillation enabled (500k positions)"

# Kill any existing training session
tmux kill-session -t training 2>/dev/null || true

tmux new-session -d -s training -x 220 -y 50

tmux send-keys -t training "source /workspace/duchess/py-duchess/bin/activate" Enter
tmux send-keys -t training "cd /workspace/duchess" Enter
TRAIN_CMD="python nnue/rl_loop.py \
    --iterations 50 \
    --games-per-iter 10000 \
    --threads \$(nproc) \
    --selfplay-depth 3 \
    --epochs-per-iter 30 \
    $EXTRA_FLAGS"
if [ "$AUTO_STOP" = "1" ]; then
    TRAIN_CMD="$TRAIN_CMD || /tmp/stop_pod.sh"
fi
tmux send-keys -t training "$TRAIN_CMD" Enter

echo ""
echo "========================================="
echo "✅ Setup complete — training is running!"
echo ""
echo "  Watch:  tmux attach -t training"
echo "  Detach: Ctrl+B then D"
echo "========================================="
