#!/bin/bash

PKGROOT=$(mktemp -d /tmp/dockutil-build-root-XXXXXXXXXXX)
OUTPUTDIR=$(mktemp -d /tmp/dockutil-output-XXXXXXXXXXX)
mkdir -p "${PKGROOT}/usr/local/bin/"
cp ./scripts/dockutil "${PKGROOT}/usr/local/bin/"
VERSION=$(./scripts/dockutil --version)
echo packaging verion: $VERSION
OUTFILE="${OUTPUTDIR}/dockutil-${VERSION}.pkg"
pkgbuild --root "$PKGROOT" --identifier dockutil.cli.tool --version $VERSION "$OUTFILE"
echo $OUTFILE
open $OUTPUTDIR
