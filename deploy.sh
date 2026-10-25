#!/bin/sh

echo "Building and pushing 'latest'"
docker compose build
docker compose push
export OPENMOXIE_VERSION=$(cat site/VERSION)
echo "Building and pushing '$OPENMOXIE_VERSION'"
docker compose build
docker compose push
