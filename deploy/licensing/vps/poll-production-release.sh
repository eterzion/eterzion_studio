#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="${ETERZION_LICENSING_DEPLOY_DIR:-/opt/eterzion-studio-licensing}"
deployed_file="${repo_dir}/.deployed-sha"

cd "$repo_dir"
git fetch --quiet origin production
target_sha="$(git rev-parse refs/remotes/origin/production)"

if [[ -f "$deployed_file" ]] && [[ "$(<"$deployed_file")" == "$target_sha" ]]; then
  echo "Production release already deployed: ${target_sha}"
  exit 0
fi

script_file="$(mktemp "${TMPDIR:-/tmp}/eterzion-licensing-deploy.XXXXXX")"
trap 'rm -f "$script_file"' EXIT
git show "${target_sha}:scripts/deploy.sh" > "$script_file"
chmod 0700 "$script_file"

echo "Deploying validated production release: ${target_sha}"
"$script_file" "$target_sha"
