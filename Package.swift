// swift-tools-version:5.5

import PackageDescription

let package = Package(
    name: "DockUtil",
    platforms: [.macOS(.v10_15)],
    products: [
        .executable(name: "dockutil", targets: ["DockUtil"])
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.0.0"),
    ],
    targets: [
        .executableTarget(
            name: "DockUtil",
            dependencies: [.product(name: "ArgumentParser", package: "swift-argument-parser")],
            exclude: ["Info.plist"]
        ),
        .testTarget(
            name: "DockUtilTests",
            dependencies: ["DockUtil"],
            exclude: ["Info.plist"]
        ),
    ]
)
