PRODUCT = $(shell /usr/bin/plutil -extract CFBundleName raw Sources/Resources/Info.plist)
VERSION = $(shell /usr/bin/plutil -extract CFBundleShortVersionString raw Sources/Resources/Info.plist)
BUNDLE_ID = $(shell /usr/bin/plutil -extract CFBundleIdentifier raw Sources/Resources/Info.plist)

BINARY = .build/apple/Products/Release/${PRODUCT}
PKG_ROOT = ./pkg/${PRODUCT}-${VERSION}
PKG_DIR =  ${PKG_ROOT}/usr/local/bin
ARTIFACTS_DIR = "artifacts"
NONDIST_PKG = ${ARTIFACTS_DIR}/intermediary_${PRODUCT}-${VERSION}.pkg
PKG = ${ARTIFACTS_DIR}/${PRODUCT}-${VERSION}.pkg

CODESIGN_IDENTITY = "Developer ID Application: Kyle Crawford (Z5J8CJBUWC)"
PKG_CODESIGN_IDENTITY = "Developer ID Installer: Kyle Crawford (Z5J8CJBUWC)"
NOTARY_KEYCHAIN_PROFILE = "notarytool.dockutil.com"


${BINARY}:
	swift build -c release --product ${PRODUCT} --arch arm64 --arch x86_64
	xcrun codesign -s ${CODESIGN_IDENTITY} \
               --options=runtime \
               --timestamp \
               ${BINARY}

${PKG}: ${BINARY}
	rm -rf "${PKG_ROOT}" || true
	mkdir -p ${PKG_DIR}
	mkdir -p ${ARTIFACTS_DIR}
	cp ${BINARY} ${PKG_DIR}
	xcrun pkgbuild --root ${PKG_ROOT} \
           --identifier "${BUNDLE_ID}" \
           --version "${VERSION}" \
           --install-location "/" \
           --sign ${PKG_CODESIGN_IDENTITY} \
           ${NONDIST_PKG}
	productbuild --package ${NONDIST_PKG} \
           --identifier "${BUNDLE_ID}" \
           --version "${VERSION}" \
           --sign ${PKG_CODESIGN_IDENTITY} \
           ${PKG}

.PHONY: build
build: ${BINARY}

.PHONY: package
package: ${PKG}

.PHONY: notarize
notarize: ${PKG}
	xcrun notarytool submit ${PKG} \
          --keychain-profile ${NOTARY_KEYCHAIN_PROFILE} \
          --wait

.PHONY: staple
staple:
	xcrun stapler staple "${PKG}"

.PHONY: clean
clean:
	swift package clean

.PHONY: release
release: clean package notarize staple
