#!/usr/bin/env bash
set -euo pipefail

SKILLS_REPO="${SKILLS_REPO:-https://github.com/MECO-Robotics/mission-control-skills.git}"
SKILLS_REF="${SKILLS_REF:-}"
TMP_DIR=".tmp-skills-sync"

fail() { echo "Error: $*" >&2; exit 1; }
cleanup() { rm -rf "$TMP_DIR"; }

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "run from a git repository"
[ "$(pwd -P)" = "$(cd "$repo_root" && pwd -P)" ] || fail "run from the repository root"

trap cleanup EXIT
cleanup
git clone --depth 1 "$SKILLS_REPO" "$TMP_DIR"
[ -d "$TMP_DIR/skills" ] || fail "shared repo does not contain a skills/ directory"
if [ -n "$SKILLS_REF" ]; then
  git -C "$TMP_DIR" fetch --depth 1 origin "$SKILLS_REF"
  git -C "$TMP_DIR" checkout --quiet "$SKILLS_REF"
fi

mkdir -p skills
cp -R "$TMP_DIR/skills/." skills/
echo "Synced skills/ from $SKILLS_REPO${SKILLS_REF:+ at $SKILLS_REF}."
