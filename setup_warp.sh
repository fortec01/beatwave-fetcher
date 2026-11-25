#!/bin/sh
# Download the WARP tooling (wgcf + wireproxy) INSIDE the project dir
# (vendor/bin) so it survives into the Render runtime.
set -e
BIN="vendor/bin"
mkdir -p "$BIN"
if [ ! -x "$BIN/wgcf" ]; then
  curl -fsSL -o "$BIN/wgcf" \
    https://github.com/ViRb3/wgcf/releases/download/v2.3.1/wgcf_2.3.1_linux_amd64
  chmod +x "$BIN/wgcf"
fi
if [ ! -x "$BIN/wireproxy" ]; then
  curl -fsSL -o /tmp/wireproxy.tar.gz \
    https://github.com/windtf/wireproxy/releases/download/v1.1.3/wireproxy_linux_amd64.tar.gz
  tar -xzf /tmp/wireproxy.tar.gz -C "$BIN" --no-same-owner
  chmod +x "$BIN/wireproxy"
  rm -f /tmp/wireproxy.tar.gz
fi
echo "warp tooling ready in $BIN"
