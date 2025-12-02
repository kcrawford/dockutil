PRODUCT = $(shell /usr/bin/plutil -extract CFBundleName raw Sources/Resources/Info.plist)
VERSION = $(shell /usr/bin/plutil -extract CFBundleShortVersionString raw Sources/Resources/Info.plist)
BUNDLE_ID = $(shell /usr/bin/plutil -extract CFBundleIdentifier raw Sources/Resources/Info.plist)

BINARY = .build/apple/Products/Release/${PRODUCT}
PKG_ROOT = ./pkg/${PRODUCT}-${VERSION}
PKG_DIR =  ${PKG_ROOT}/root/usr/local/bin
APP_DIR = ${PKG_ROOT}/root/usr/local/dockutil
ARTIFACTS_DIR = "artifacts"
NONDIST_PKG = ${ARTIFACTS_DIR}/intermediary_${PRODUCT}-${VERSION}.pkg
PKG = ${ARTIFACTS_DIR}/${PRODUCT}-${VERSION}.pkg
APP = Dockutil/build/Release/Dockutil.app

CODESIGN_IDENTITY = "Developer ID Application: Kyle Crawford (Z5J8CJBUWC)"
PKG_CODESIGN_IDENTITY = "Developer ID Installer: Kyle Crawford (Z5J8CJBUWC)"
NOTARY_KEYCHAIN_PROFILE = "dockutil.notary"


${APP}:
	xcodebuild -project "Dockutil/Dockutil.xcodeproj" -configuration Release clean build OTHER_CODE_SIGN_FLAGS="--timestamp" CODE_SIGN_INJECT_BASE_ENTITLEMENTS=NO

${BINARY}:
	swift build -c release --product ${PRODUCT} --arch arm64 --arch x86_64
	xcrun codesign -s ${CODESIGN_IDENTITY} \
               --options=runtime \
               --timestamp \
               ${BINARY}

${PKG_ROOT}: ${APP} ${BINARY}
	rm -rf "${PKG_ROOT}" || true
	mkdir -p ${PKG_DIR}
	mkdir -p ${ARTIFACTS_DIR}
	cp ${BINARY} ${PKG_DIR}
	mkdir -p ${APP_DIR}
	cp -Rp ${APP} ${APP_DIR}

.PHONY: build
build: ${BINARY}

.PHONY: packagebuild
packagebuild: ${PKG_ROOT} ${APP} ${BINARY}
	xcrun pkgbuild --root ${PKG_ROOT}/root \
           --identifier "${PKG_BUNDLE_ID}" \
           --version "${VERSION}" \
           --install-location "/" \
           --sign ${PKG_CODESIGN_IDENTITY} \
           --component-plist pkg_resources/component.plist \
           --scripts ${POSTINSTALL_SCRIPTS} \
           ${NONDIST_PKG}
	productbuild --package ${NONDIST_PKG} \
           --identifier "${PKG_BUNDLE_ID}" \
           --version "${VERSION}" \
           --sign ${PKG_CODESIGN_IDENTITY} \
           ${PKG}

.PHONY: package
package: PKG_BUNDLE_ID = ${BUNDLE_ID}
package: PKG = ${ARTIFACTS_DIR}/${PRODUCT}-${VERSION}.pkg
package: POSTINSTALL_SCRIPTS = pkg_resources/scripts/standalone
package: packagebuild


.PHONY: agentpackage
agentpackage: PKG_BUNDLE_ID = ${BUNDLE_ID}.agent
agentpackage: PKG = ${ARTIFACTS_DIR}/${PRODUCT}_agent-${VERSION}.pkg
agentpackage: POSTINSTALL_SCRIPTS = pkg_resources/scripts/agent
agentpackage: packagebuild

.PHONY: notarize
notarize:
	xcrun notarytool submit ${PKG} \
          --keychain-profile ${NOTARY_KEYCHAIN_PROFILE} \
          --wait

.PHONY: staple
staple:
	xcrun stapler staple "${PKG}"

.PHONY: clean
clean:
	swift package clean
	xcodebuild clean -project "Dockutil/Dockutil.xcodeproj" || xcodebuild clean -project "Dockutil/Dockutil.xcodeproj"
	rm ${PKG} || true
	rm ${LA_PKG} || true
	rm -Rf ${PKG_ROOT} || true


.PHONY: release
release: PKG = ${ARTIFACTS_DIR}/${PRODUCT}-${VERSION}.pkg
release: package notarize staple


.PHONY: agentrelease
agentrelease: PKG = ${ARTIFACTS_DIR}/${PRODUCT}_agent-${VERSION}.pkg
agentrelease: agentpackage notarize staple
