#!/bin/sh

# usage: [SIGN_PKG=1] sh packaging.sh [install | install-pkg | clean]

PKG=dockutil
VERSION=1.1.2
DESCRIPTION="command line tool for modifying the dock"

if [ "$1" = "clean" ]; then
  rm -rf osxpkg-root ${PKG}*.pkg Distribution.xml
  exit 0
fi

if [ "$1" = "install" ]; then
  cp scripts/dockutil /usr/local/bin
  chown root:wheel /usr/local/bin/dockutil
  chmod 755 /usr/local/bin/dockutil
  exit 0
fi

# use pkgbuild/productbuild as provided with current xcode to build .pkg

mkdir -p osxpkg-root/usr/bin
cp scripts/dockutil osxpkg-root/usr/bin
pkgbuild --root osxpkg-root --identifier com.${PKG}.pkg --version ${VERSION} ${PKG}.pkg
productbuild --synthesize --package ${PKG}.pkg Distribution.xml
perl -pi -e 's@</installer-gui-script>@ \
  <title>dockutil</title> \
  <welcome file="welcome.rtf" mime-type="text/rtf" /> \
  <conclusion file="conclusion.rtf" mime-type="text/rtf" /> \
  <background file="dockutil.png" mime-type="image/png" alignment="bottomleft" scaling="none" /> \
  </installer-gui-script>@' Distribution.xml
productbuild --distribution Distribution.xml --resources osxpkgresources ${PKG}_${VERSION}-unsigned.pkg
[ "$SIGN_PKG" ] && productsign --sign 'Developer ID Installer' ${PKG}_${VERSION}-unsigned.pkg ${PKG}_${VERSION}.pkg

[ "$1" = "install-pkg" ] && sudo installer -tgt / -pkg ${PKG}_${VERSION}-unsigned.pkg

# the resulting pkg can be attached as a binary asset to github releases:
# https://github.com/blog/1547-release-your-software
# the xml-referenced media files (.rtf/.png) might be used to further pimp the .pkg
