// swift-tools-version:6.0

import PackageDescription

let package = Package(
    name: "dockutil",
    platforms: [.macOS(.v11)],
    products: [
        .executable(name: "dockutil", targets: ["DockUtil"])
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.6.1"),
    ],
    targets: [
        .executableTarget(
            name: "DockUtil",
            dependencies: [
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
            ],
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-sectcreate",
                    "-Xlinker", "__TEXT",
                    "-Xlinker", "__info_plist",
                    "-Xlinker", "Sources/Resources/Info.plist"
                ])
            ]
        ),
        .testTarget(
            name: "DockUtilTests",
            dependencies: ["DockUtil"]
        ),
    ]
)
