#!/bin/bash
# Refresh every 15 minutes until the poll closes, plus one last read just after the close.
# Each round moves the mouse inside WhatsApp Desktop for about 20 seconds.
source "$(dirname "$0")/env.sh"
end=$(date -d "$CLOSES" +%s)
while :; do
  "$REPO/tools/refresh.sh" 2>&1 | sed "s/^/[$(date +%H:%M)] /"
  now=$(date +%s)
  [ "$now" -ge $((end + 120)) ] && break
  next=$((now + ${CTI_EVERY:-900}))
  [ "$next" -gt "$end" ] && [ "$now" -lt "$end" ] && next=$((end + 60))  # last read right after the close
  sleep $((next - now))
done
echo "poll closed, loop finished"
