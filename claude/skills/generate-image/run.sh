#!/bin/sh
# usage: run.sh <job folder> <imagegen.py command> [args...]
#
# Runs imagegen.py in Docker with the job folder as its working directory, so
# every path in the arguments is relative to that folder. Commands that call
# llama-swap get its address and API key from the cluster with kubectl; the key
# goes to the container through the environment, never on a command line.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
job=$1
shift
mkdir -p "$job"
image="generate-image:$(cksum < "$here/Dockerfile" | cut -d ' ' -f 1)"
docker image inspect "$image" > /dev/null 2>&1 || docker build -q -t "$image" "$here" > /dev/null

LS_URL=
LS_KEY=
case "$1" in
  models | gen | edit | img2img)
    ns=llama-swap-system
    LS_URL=$(kubectl -n "$ns" get service llama-swap -o jsonpath='http://{.status.loadBalancer.ingress[0].ip}:{.spec.ports[0].port}')
    LS_KEY=$(kubectl -n "$ns" get secret llama-swap-api-key -o jsonpath='{.data.api-key}' | base64 -d)
    ;;
esac
export LS_URL LS_KEY

exec docker run --rm -e LS_URL -e LS_KEY \
  -v "$(cd "$job" && pwd):/work" -v "$here/imagegen.py:/app/imagegen.py:ro" \
  "$image" python -I /app/imagegen.py "$@"
