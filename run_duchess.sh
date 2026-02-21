#!/bin/bash
set -e

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# pyenv duchess environment
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
pyenv activate duchess

# Include project root + C++ engine module
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/engine/build"

# Only run migrations for email mode (GUI doesn't need DB)
if [ "$1" != "--mode" ] || [ "$2" != "gui" ]; then
    echo "Running database migrations..."
    python -m alembic upgrade head
fi

echo "Starting Duchess..."
exec python -m duchess.main "$@"
