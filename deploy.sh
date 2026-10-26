#!/bin/sh
set -e

# Multi-arch builds are not loaded into the local image store, so a separate
# `docker compose push` would push a stale local tag. Build and push together.
if ! docker compose config | grep -q 'linux/arm64'; then
    echo "docker-compose.yml is missing the multi-arch platforms; not deploying." >&2
    exit 1
fi

unset OPENMOXIE_VERSION
echo "Building and pushing 'latest'"
docker compose build --push

export OPENMOXIE_VERSION=$(cat site/VERSION)
echo "Building and pushing '$OPENMOXIE_VERSION'"
docker compose build --push

for image in openmoxie-server openmoxie-mqtt; do
    for tag in latest "$OPENMOXIE_VERSION"; do
        echo "openmoxie/$image:$tag"
        docker buildx imagetools inspect "openmoxie/$image:$tag" | grep 'Platform:' | grep -v unknown
    done
done
