#!/bin/sh
set -e

cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.venv/
setup.sh
.idea/
.vscode/
EOF

git add -A
git commit -m "cleanup: drop dead code, shared physics_util, const pruning"