// swift-tools-version:6.2

import PackageDescription

let package = Package(
    name: "dockutil",
    platforms: [.macOS(.v11)],
    products: [
        .library(name: "dockutil-lib", targets: ["DockUtilLib"]),
        .executable(name: "dockutil", targets: ["DockUtil"])
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.6.1"),
    ],
    targets: [
        .target(
            name: "DockUtilLib",
            dependencies: [
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
            ],
        ),
        .executableTarget(
            name: "DockUtil",
            dependencies: ["DockUtilLib"],
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-sectcreate",
                    "-Xlinker", "__TEXT",
                    "-Xlinker", "__info_plist",
                    "-Xlinker", "Sources/Resources/Info.plist"
                ])
            ]
        )
    ]
)
