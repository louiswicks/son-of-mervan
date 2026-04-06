#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
  echo "Error: GITHUB_TOKEN environment variable is not set."
  echo "Run: export GITHUB_TOKEN=your_token"
  exit 1
fi

# Ensure the token is embedded in the remote URL for every push
git remote set-url origin "https://louiswicks:${GITHUB_TOKEN}@github.com/louiswicks/son-of-mervan.git"

for ((i=1; i<=$1; i++)); do
  result=$(claude --permission-mode bypassPermissions -p "@PRD.md @progress.txt \
  1. Find the highest-priority task and implement it. \
  2. Run your tests and type checks. \
  3. Update the PRD with what was done. \
  4. Append your progress to progress.txt. \
  5. Commit your changes. \
  ONLY WORK ON A SINGLE TASK. \
  If the PRD is complete, output <promise>COMPLETE</promise>.")

  echo "$result"

  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo "PRD complete after $i iterations."
    exit 0
  fi
done
