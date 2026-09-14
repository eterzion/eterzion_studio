#!/usr/bin/env bash
set -Eeuo pipefail

target_sha="${1:?production commit SHA is required}"
repo_dir="${ETERZION_LICENSING_DEPLOY_DIR:-/opt/eterzion-studio-licensing}"
deployed_file="${repo_dir}/.deployed-sha"
container_name="eterzion-studio-licensing"

cd "$repo_dir"

previous_sha=''
if [[ -f "$deployed_file" ]]; then
  previous_sha="$(<"$deployed_file")"
fi

wait_until_healthy() {
  local attempt status
  for attempt in $(seq 1 18); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container_name" 2>/dev/null || true)"
    if [[ "$status" == 'healthy' ]]; then
      echo "Licensing service is healthy after ${attempt} attempt(s)."
      return 0
    fi
    if [[ "$status" == 'unhealthy' ]]; then
      docker logs --tail 100 "$container_name" >&2 || true
      return 1
    fi
    sleep 5
  done
  docker logs --tail 100 "$container_name" >&2 || true
  return 1
}

start_release() {
  local release_sha="$1"
  git checkout --quiet --detach "$release_sha"
  test -s .licensing-image.env
  test -s .env
  docker network inspect eterzion_proxy >/dev/null
  docker compose --env-file .licensing-image.env pull licensing
  docker compose --env-file .licensing-image.env up -d --remove-orphans licensing
  wait_until_healthy
}

if ! start_release "$target_sha"; then
  echo "Deployment failed for ${target_sha}." >&2
  if [[ -n "$previous_sha" ]] && git cat-file -e "${previous_sha}^{commit}" 2>/dev/null; then
    echo "Rolling back to ${previous_sha}." >&2
    start_release "$previous_sha"
  else
    echo 'No previous validated release is available for rollback.' >&2
  fi
  exit 1
fi

printf '%s\n' "$target_sha" > "$deployed_file"
echo "Deploy complete: ${target_sha}"
