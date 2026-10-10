#!/bin/sh
set -e

cat > levels/test2.json <<'EOF'
{
  "pegs": [],
  "platforms": [],
  "items": [
    {"x": -400, "y": 120, "type": "cube"},
    {"x": -300, "y": 120, "type": "cube"},
    {"x": -200, "y": 120, "type": "cube"},
    {"x": -100, "y": 120, "type": "cube"},
    {"x":    0, "y": 120, "type": "cube"},
    {"x":  100, "y": 120, "type": "cube"},
    {"x":  200, "y": 120, "type": "cube"},
    {"x":  300, "y": 120, "type": "cube"},
    {"x":  400, "y": 120, "type": "cube"},
    {"x":  500, "y": 120, "type": "cube"}
  ]
}
EOF

git add -A
git commit -m "levels: test2 without platform, cubes fall to floor"