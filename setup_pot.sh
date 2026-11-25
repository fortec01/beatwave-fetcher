#!/bin/sh
# Build the bgutil PO-token generation script into $HOME so the yt-dlp
# plugin (script mode) can find it at the default location:
#   ~/bgutil-ytdlp-pot-provider/server/build/generate_once.js
set -e
DEST="$HOME/bgutil-ytdlp-pot-provider"
if [ -f "$DEST/server/build/generate_once.js" ]; then
  echo "bgutil script already built"
  exit 0
fi
rm -rf "$DEST"
git clone --single-branch --branch 1.3.1 --depth 1 \
  https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$DEST"
cd "$DEST/server"
npm ci
npx tsc
echo "bgutil script built at $DEST/server/build/generate_once.js"
