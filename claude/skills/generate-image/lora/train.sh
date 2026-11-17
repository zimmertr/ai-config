#!/bin/sh
# usage: train.sh NAME SET RANK LR STEPS EVERY [PROMPTS]   (runs in the foreground; start it with nohup)
set -eu
. /work/venv/bin/activate
cd /work/ai-toolkit
sh /work/run/config.sh "$@" > "/work/run/$1.yaml"
echo "start $(date -u +%FT%TZ) $*" > "/work/logs/$1.log"
python run.py "/work/run/$1.yaml" >> "/work/logs/$1.log" 2>&1 && echo "DONE $(date -u +%FT%TZ)" >> "/work/logs/$1.log" || echo "FAILED $(date -u +%FT%TZ) exit $?" >> "/work/logs/$1.log"
