#!/bin/sh
# Build the bgutil PO-token generation script INSIDE the project dir
# (vendor/) — Render only carries the project directory into the runtime,
# $HOME build artifacts are lost.
set -e
DEST="vendor/bgutil"
if [ -f "$DEST/server/build/generate_once.js" ]; then
  echo "bgutil script already built"
  exit 0
fi
rm -rf "$DEST"
mkdir -p vendor
git clone --single-branch --branch 1.3.1 --depth 1 \
  https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$DEST"
cd "$DEST/server"
npm ci
npx tsc
echo "bgutil script built at $DEST/server/build/generate_once.js"
