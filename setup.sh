#!/bin/sh
set -e

python - <<'EOF'
p = "editor/editor.py"
s = open(p).read()

old = """  def set_tool(self, name):
    if self.tool == "ghost" and name != "ghost":
      self.ghost_target = [0.0, float(BODY_R)]
    self.tool = name"""
new = """  def set_tool(self, name):
    # <STRANGE>#233 reset idle on any tool change so the return timer starts fresh from the switch moment
    self.ghost_idle = 0.0
    self.tool = name"""
assert old in s, "set_tool"
s = s.replace(old, new, 1)

open(p, "w").write(s)
EOF

python -c "import ast; ast.parse(open('editor/editor.py').read()); print('syntax ok')"