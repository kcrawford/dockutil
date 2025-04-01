#!/bin/bash
set -euo pipefail

ARCH="${1:-x86_64}"

# build.
swift build \
    --arch "$ARCH" \
    --configuration release

# package.
rm -f ".build/dockutil-$ARCH.tar.gz"
tar czf ".build/dockutil-$ARCH.tar.gz" \
    -C ".build/$ARCH-apple-macosx/release" \
    dockutil
