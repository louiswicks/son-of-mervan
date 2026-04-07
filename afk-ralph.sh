#!/bin/bash
set -e

if [ -z "$GITHUB_TOKEN" ]; then
  echo "Error: GITHUB_TOKEN environment variable is not set."
  echo "Run: export GITHUB_TOKEN=your_token"
  exit 1
fi

# Ensure the token is embedded in the remote URL for every push
git remote set-url origin "https://louiswicks:${GITHUB_TOKEN}@github.com/louiswicks/son-of-mervan.git"

iteration=1

while true; do
  echo "=== Iteration $iteration ==="

  result=$(claude --permission-mode bypassPermissions -p "@PRD.md @progress.txt \
  You are an autonomous software engineer working on the Son of Mervan budgeting app. \
  \
  Your loop: \
  1. Read PRD.md and progress.txt to understand what has been done and what remains. \
  2. If there are incomplete tasks in the PRD, pick the highest-priority one and implement it fully. \
     Run tests and linting. Commit and push. Update PRD.md to mark the task DONE. Append a summary to progress.txt. \
  3. If ALL tasks in the PRD are complete, generate new tasks that would make this application \
     better for users and more production ready. Add them as a new Phase to PRD.md with full \
     acceptance criteria, then immediately begin implementing the first new task. \
     Never output COMPLETE — always find more valuable work to do. \
  \
  Rules: \
  - ONLY WORK ON A SINGLE TASK PER ITERATION. \
  - Always commit and push before finishing. \
  - Keep PRD.md and progress.txt up to date. \
  - If a task requires a decision, make a reasonable engineering judgement and proceed.")

  echo "$result"
  echo "=== Iteration $iteration complete ==="
  iteration=$((iteration + 1))
done
