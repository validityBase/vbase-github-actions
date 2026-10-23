#!/usr/bin/env bash
set -euo pipefail

heads=$(gh api --method GET --paginate "repos/$GITHUB_REPOSITORY/pulls" \
  -f state=open -f base="$DEFAULT_BRANCH" -f per_page=100 \
  --jq '.[] | [.head.repo.full_name, .head.ref] | @tsv')
while IFS=$'\t' read -r repository branch; do
  if [[ "$repository" == "$GITHUB_REPOSITORY" && "$branch" == "$RELEASE_PREFIX"* ]]; then
    echo 'An open Release PR already exists.'
    exit 1
  fi
done <<< "$heads"
