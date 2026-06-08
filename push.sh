#!/bin/bash
# Auto git push script for HowToServePeopleLangChainAgent
# Usage: ./push.sh "commit message"

cd "$(dirname "$0")"

# Check if commit message provided
if [ -z "$1" ]; then
    MSG="auto: $(date '+%Y-%m-%d %H:%M:%S') - 更新代码"
else
    MSG="$1"
fi

# Check if there are changes
if git diff --quiet && git diff --cached --quiet; then
    echo "✓ 没有需要提交的更改"
    exit 0
fi

# Add all changes
git add -A

# Commit
git commit -m "$MSG"

# Push
git push origin master

echo "✓ 已推送到 GitHub"
