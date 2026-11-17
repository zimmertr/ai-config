#!/bin/sh
# Runs each line of /work/run/queue.txt (train.sh arguments) one after another; a failed run doesn't
# stop the queue. Edit queue.txt while it runs to add runs; done lines are moved to queue-done.txt.
while :; do
  line=$(head -n 1 /work/run/queue.txt 2>/dev/null || true)
  [ -n "$line" ] || { echo "QUEUE EMPTY $(date -u +%FT%TZ)" >> /work/logs/sweep.log; exit 0; }
  sed -i '1d' /work/run/queue.txt
  echo "run $line $(date -u +%FT%TZ)" >> /work/logs/sweep.log
  # shellcheck disable=SC2086
  sh /work/run/train.sh $line
  echo "$line" >> /work/run/queue-done.txt
done
