#!/bin/bash
# Duchess Chess — Ubuntu Setup Script
# Run this on your Ubuntu desktop after cloning the repo.
# Usage: bash setup_ubuntu.sh

set -e

echo "=== Duchess Ubuntu Setup ==="

# 1. System dependencies
echo "[1/7] Installing system packages..."
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake g++ \
    python3 python3-pip python3-venv \
    postgresql postgresql-contrib libpq-dev \
    git git-lfs

# 2. PostgreSQL database
echo "[2/7] Setting up PostgreSQL database..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'duchess_db'" | grep -q 1 || \
    sudo -u postgres createdb duchess_db
# Grant access to current user
sudo -u postgres psql -c "CREATE USER $USER WITH SUPERUSER;" 2>/dev/null || true

# 3. Python virtual environment
echo "[3/7] Creating Python virtualenv 'py-duchess' and installing dependencies..."
python3 -m venv py-duchess
source py-duchess/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Environment file
echo "[4/7] Creating .env file..."
if [ ! -f .env ]; then
    echo "DATABASE_URL=postgresql://localhost/duchess_db" > .env
    echo "Created .env"
else
    echo ".env already exists, skipping"
fi

# 5. Database migrations
echo "[5/7] Running database migrations..."
python -m alembic upgrade head

# 6. Build Duchess engine
echo "[6/7] Building Duchess engine..."
mkdir -p engine/build
cd engine/build
cmake ..
make -j$(nproc)
echo "Running tests..."
ctest --output-on-failure
cd ../..

# 7. Build Queen engine (if source is present)
echo "[7/7] Building Queen engine..."
if [ -d "$HOME/Queen405x64" ]; then
    cd "$HOME/Queen405x64"
    make clean 2>/dev/null || true
    make CXX=g++
    echo "Queen built at: $HOME/Queen405x64/queen"
    cd -
else
    echo "Queen source not found at ~/Queen405x64 — skipping."
    echo "Copy it from your Mac: scp -r user@mac:~/Desktop/Queen405x64 ~/"
fi

# Initialize Git LFS
git lfs install

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Always activate the venv before running:"
echo "  source py-duchess/bin/activate"
echo ""
echo "To start the RL training loop:"
echo "  source py-duchess/bin/activate"
echo "  python nnue/rl_loop.py \\"
echo "    --iterations 35 \\"
echo "    --games-per-iter 5000 \\"
echo "    --threads $(nproc) \\"
echo "    --epochs-per-iter 20 \\"
echo "    --book assets/gm2001.bin \\"
echo "    --gauntlet-engine ~/Queen405x64/queen \\"
echo "    --gauntlet-games 20"
echo ""
echo "Optional: copy Syzygy tablebases and add --syzygy /path/to/syzygy"
