#!/bin/sh
# Download the WARP tooling (wgcf + wireproxy) into $HOME/warp/bin.
# wgcf registers a free Cloudflare WARP account; wireproxy turns the
# WireGuard profile into a local SOCKS5 proxy with no root/TUN needed.
set -e
BIN="$HOME/warp/bin"
mkdir -p "$BIN"
if [ ! -x "$BIN/wgcf" ]; then
  curl -fsSL -o "$BIN/wgcf" \
    https://github.com/ViRb3/wgcf/releases/download/v2.3.1/wgcf_2.3.1_linux_amd64
  chmod +x "$BIN/wgcf"
fi
if [ ! -x "$BIN/wireproxy" ]; then
  curl -fsSL -o /tmp/wireproxy.tar.gz \
    https://github.com/windtf/wireproxy/releases/download/v1.1.3/wireproxy_linux_amd64.tar.gz
  tar -xzf /tmp/wireproxy.tar.gz -C "$BIN"
  chmod +x "$BIN/wireproxy"
  rm -f /tmp/wireproxy.tar.gz
fi
echo "warp tooling ready: $($BIN/wgcf --version 2>/dev/null | head -1)"
