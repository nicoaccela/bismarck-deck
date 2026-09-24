#!/bin/bash
# Full start: deck server (port 8080) + a NEW public Cloudflare quick tunnel. URL is written to url.txt.
# Starting a new tunnel CHANGES the public URL (and so the QR code). To restart only the server, use:
#   ./serve.sh server
cd "$(dirname "$0")"
start_server(){
  pkill -f "bismarck-deck-site/server.py" 2>/dev/null; sleep 1
  nohup python3 "$PWD/server.py" > server.log 2>&1 &
  sleep 1; echo "Server restarted on 127.0.0.1:8080"
}
if [ "$1" = "server" ]; then start_server; exit 0; fi

pkill -f "cloudflared tunnel --url http://localhost:8080" 2>/dev/null
: > tunnel.log
nohup $HOME/.local/bin/cloudflared tunnel --url http://localhost:8080 --no-autoupdate > tunnel.log 2>&1 &
u=""
for i in $(seq 1 45); do
  # skip api.trycloudflare.com, which appears in error lines when the tunnel request fails
  u=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | grep -v '^https://api\.' | head -1)
  [ -n "$u" ] && break; sleep 1
done
if [ -z "$u" ]; then echo "Tunnel did not come up. url.txt left unchanged. See tunnel.log."; start_server; exit 1; fi
echo "$u" > url.txt
start_server            # restart so follow-qr.png is regenerated for the new URL
echo "Public deck:   $u"
echo "Follow-along:  $u/follow"
echo "Presenter:     $u/?presenter=\$(cat presenter.key)"
