//
//  Extensions.swift
//  dockutil
//
//

import AppKit

extension String {
    func resolvedPath() -> String {
        var resolved = self
        // Handle Applications that reside at /System/Applications
        if self.hasPrefix("/Applications/") {
            if !FileManager.default.fileExists(atPath: self) {
                let possibleSystemAppPath = "/System" + self
                if FileManager.default.fileExists(atPath: possibleSystemAppPath) {
                    FileHandle.standardError.write("Notice: using item at \(possibleSystemAppPath) rather than \(self)\n".data(using: .utf8)!)
                    resolved = possibleSystemAppPath
                }
            }

            // Handle Applications that are symlinks to Cryptexes like Safari so they don't show as symlinks in Dock
            if #available(macOS 13.0, *) {
                let appselfURL = URL(filePath: self)
                let appIsSymlink = (try? appselfURL.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) ?? false
                gv > 0 ? print("App is symlink: \(appIsSymlink)"):nil
                if appIsSymlink {
                    let resolvedPath = appselfURL.resolvingSymlinksInPath().path(percentEncoded: false)
                    gv > 0 ? print("Application symlink resolves to \(resolvedPath)"):nil
                    if resolvedPath.hasPrefix("/System/Volumes/Preboot/Cryptexes/App/System/") {
                        gv > 0 ? print("Application is a symlink to Cryptexes. Set actual path to \(resolvedPath)"):nil
                        FileHandle.standardError.write("Notice: using item at \(resolvedPath) rather than \(self)\n".data(using: .utf8)!)
                        resolved = resolvedPath
			// "_CFURLString" = "file:///System/Volumes/Preboot/Cryptexes/App/System/Applications/Safari.app/";
                    }
                }
            }
        }
        return resolved
    }
}


extension UserDefaults {

    // KVO enablement
    @objc dynamic var apps: Bool {
        return bool(forKey: "apps")
    }

}
