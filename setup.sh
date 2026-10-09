#!/bin/sh
set -e

git add -A
git status --short
git commit -m "sound: complete sfx bank for all events, add footstep system"