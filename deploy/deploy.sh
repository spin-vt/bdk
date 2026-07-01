#!/bin/sh
# Deploy BDK on this host by pulling the CI-built images for a commit and
# restarting — nothing is built on the host. Images are built and pushed to
# ghcr by .github/workflows/docker_push.yml on every green main build, tagged
# by commit SHA.
#
#   ./deploy.sh web  <git-sha>
#   ./deploy.sh data <git-sha>
#
# Rollback = the same command with a previous sha. The checkout is pinned to
# that sha too (so the compose files / nginx.conf match the images) and must
# be clean — production is never hand-edited.
set -eu

ROLE=${1:?usage: deploy.sh <web|data> <git-sha>}
SHA=${2:?usage: deploy.sh <web|data> <git-sha>}
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(dirname "$DIR")

[ -f "$DIR/$ROLE/.env" ] || { echo "missing $DIR/$ROLE/.env (copy from env.example)"; exit 1; }

cd "$REPO"
if [ -n "$(git status --porcelain)" ]; then
  echo "checkout is dirty — production is never hand-edited. Aborting."
  git status --short
  exit 1
fi
git fetch --all --quiet
git checkout --quiet "$SHA"
TAG=$(git rev-parse HEAD)
export TAG
echo "deploying $ROLE at $(git rev-parse --short HEAD) (image tag $TAG)"

cd "$DIR/$ROLE"
docker compose --env-file .env pull
docker compose --env-file .env up -d
docker compose --env-file .env ps
