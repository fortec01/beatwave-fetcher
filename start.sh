#!/bin/sh
# Start the fetcher behind a Cloudflare WARP SOCKS5 proxy (userspace
# WireGuard via wireproxy), then run the app.
WARP_DIR="$HOME/warp"
BIN="$WARP_DIR/bin"
mkdir -p "$WARP_DIR"

if [ -x "$BIN/wgcf" ] && [ -x "$BIN/wireproxy" ]; then
  cd "$WARP_DIR"
  if [ ! -f wgcf-profile.conf ]; then
    echo "[warp] registering free WARP account..."
    "$BIN/wgcf" register --accept-tos > warp-register.log 2>&1 || echo "[warp] register failed (see warp-register.log)"
    "$BIN/wgcf" generate > warp-generate.log 2>&1 || echo "[warp] generate failed (see warp-generate.log)"
  fi
  if [ -f wgcf-profile.conf ]; then
    grep -q "Socks5" wgcf-profile.conf || printf '\n[Socks5]\nBindAddress = 127.0.0.1:1080\n' >> wgcf-profile.conf
    echo "[warp] starting wireproxy..."
    nohup "$BIN/wireproxy" -c wgcf-profile.conf > wireproxy.log 2>&1 &
    # wait up to ~20s for the SOCKS port
    i=0
    while [ $i -lt 20 ]; do
      if python3 -c "import socket; s=socket.socket(); s.settimeout(1); exit(0 if s.connect_ex(('127.0.0.1',1080))==0 else 1)"; then
        echo "[warp] socks5 proxy up on 127.0.0.1:1080"
        break
      fi
      i=$((i+1)); sleep 1
    done
    curl -s -m 10 -x socks5h://127.0.0.1:1080 https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -E "^(ip|warp)=" || echo "[warp] trace check inconclusive"
  fi
  cd - > /dev/null
fi

exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 300
