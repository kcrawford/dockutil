//
//  Dock.swift
//  dockutil
//
//  Created by Kyle Crawford on 6/18/20.
//  Copyright © 2022 Kyle Crawford. All rights reserved.
//

import Cocoa
import SystemConfiguration

class Dock {
    let dockDomain = "com.apple.dock"
    let sections : [DockSection] = [.persistentApps, .recentApps, .persistentOthers]
    
    var dockItems = [DockSection:[DockTile]]()
    var path: String
    var plist = [String:AnyObject]()
    
    
    init(path: String) {
        self.path = path
        read()
    }
    
    func readDockKeys()-> [String] {
        if let keys = CFPreferencesCopyKeyList(dockDomain as CFString, kCFPreferencesCurrentUser, kCFPreferencesAnyHost) as? [String] {
            print(keys)
            return keys
        }
        return []
    }
    
    
    func runningAsConsoleUser() -> Bool {
        return ProcessInfo.processInfo.userName.lowercased() == consoleUser()?.lowercased()
    }
    
    func isLoggedInUserDock() -> Bool {
        guard let user = consoleUser() else { return false }
        let loggedInUserPlistPath = URL(fileURLWithPath: NSHomeDirectoryForUser(user) ?? NSHomeDirectory()).appendingPathComponent("Library/Preferences/com.apple.dock.plist").path
        let caseInsensitivelyEquivalentDockPaths = self.path.lowercased() == loggedInUserPlistPath.lowercased()

        if caseInsensitivelyEquivalentDockPaths {
            gv > 0 ? print("Ignoring case,", loggedInUserPlistPath, "and", self.path, "are the same so this dock is the logged in user's dock"):nil
        } else {
            gv > 0 ? print("Ignoring case,", loggedInUserPlistPath, "and", self.path, "are different so this dock is not the logged in user's dock"):nil
        }
        
        return caseInsensitivelyEquivalentDockPaths
    }
    
    func read() {
        if isLoggedInUserDock() && runningAsConsoleUser() {
            gv > 0 ? print("Reading dock as a logged in user"):nil
            for section in sections {
                if let value = CFPreferencesCopyAppValue(section.rawValue as CFString, dockDomain as CFString) as? [[String: AnyObject]] {
                    dockItems[section] = value.map({item in
                        DockTile(dict: item, section: section)
                    })
                }
            }
        } else {

            // Read using defaults because we can't trust what is on disk and defaults uses cfprefs cache
            gv > 0 ? print("Reading dock using defaults command"):nil
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/defaults")
            p.arguments = ["export", path, "-"]
            let outPipe = Pipe()
            p.standardOutput = outPipe
            p.launch()
            p.waitUntilExit()
                        
            let defaultsExportData = outPipe.fileHandleForReading.readDataToEndOfFile()
                        
            guard let dict = try? PropertyListSerialization.propertyList(from: defaultsExportData, options: .mutableContainersAndLeaves, format: nil) as? [String:AnyObject] else {
                print("failed to deserialize plist", self.path)
                return
            }
            
            self.plist = dict
            for section in sections {
                if let value = dict[section.rawValue] as? [[String: AnyObject]] {
                    dockItems[section] = value.map({item in
                        DockTile(dict: item, section: section)
                    })
                }
            }
        }
    }
    
    func save(restart: Bool) {
        if isLoggedInUserDock() && runningAsConsoleUser() {
            gv > 0 ? print("Handling dock as a logged in user"):nil
            
            for section in sections {
                if let sectionItems = self.dockItems[section] {
                    let items = sectionItems.map({dockItem in
                        dockItem.dict
                    })
                    CFPreferencesSetAppValue(section.rawValue as CFString, items as CFPropertyList?, dockDomain as CFString)
                }
            }
            
            CFPreferencesSynchronize(dockDomain as CFString, kCFPreferencesCurrentUser, kCFPreferencesAnyHost)
            
            if restart {
                self.terminate()
            }

        } else {
            gv > 0 ? print("Handling dock while running as \(ProcessInfo.processInfo.userName)"):nil
            if ProcessInfo.processInfo.userName.lowercased() != "root" {
                print("Warning: dockutil is not running as the user of this Dock nor root so dockutil may be unable to save the change or set the proper owner")
            }
            for section in sections {
                if let sectionItems = self.dockItems[section] {
                    let items = sectionItems.map({dockItem in
                        dockItem.dict
                    })
                    plist[section.rawValue] = items as AnyObject?
                }
            }
            guard let originalOwnerID = try? FileManager.default.attributesOfItem(atPath: self.path)[.ownerAccountID] as? Int else {
                print("unable to get owner of plist", self.path)
                return
            }
                        
//            IF WE WRITE DIRECTLY TO PLIST, CFPREFS IGNORES THE FILE ON DISK UNLESS WE KILL CFPREFS
//            SO WE HAVE TO WRITE TO CFPREFS AS USER USING APIs or defaults
//            FOR NOW WE USE defaults because we need to run as user.  Alternatively we could spawn dockutil as the user

            guard let plistData = try? PropertyListSerialization.data(fromPropertyList: plist, format: .binary, options: 0) else {
                print("unable to serialize plist to data")
                return
            }
                        
            if getpwuid(uid_t(originalOwnerID)) != nil { // make sure we have a valid uid we can run as
                gv > 0 ? print("Using sudo to run defaults to write to dock as user \(String(originalOwnerID))"):nil
                let p = Process()
                p.executableURL = URL(fileURLWithPath: "/usr/bin/sudo")
                p.arguments = ["-u", "#\(originalOwnerID)", "/usr/bin/defaults", "import", path, "-"]
                let stdInPipe = Pipe()
                p.standardInput = stdInPipe
                p.launch()
                stdInPipe.fileHandleForWriting.write(plistData)
                stdInPipe.fileHandleForWriting.closeFile()
                p.waitUntilExit()
                gv > 0 ? print(p.terminationStatus):nil
            } else {
                gv > 0 ? print("Unable to run as user \(originalOwnerID). Using defaults to write to dock (will attempt to chown after)"):nil
                let p = Process()
                p.executableURL = URL(fileURLWithPath: "/usr/bin/defaults")
                p.arguments = ["import", path, "-"]
                let stdInPipe = Pipe()
                p.standardInput = stdInPipe
                p.launch()
                stdInPipe.fileHandleForWriting.write(plistData)
                stdInPipe.fileHandleForWriting.closeFile()
                p.waitUntilExit()
                gv > 0 ? print(p.arguments, p.terminationStatus):nil
                gv > 0 ? print("Changing owner to original owner \(String(originalOwnerID))"):nil
                do {
                    try FileManager.default.setAttributes([.ownerAccountID: originalOwnerID], ofItemAtPath: self.path) // chown to original owner
                } catch {
                    print("Failed to set owner to original owner \(String(originalOwnerID))")
                }
            }

            if restart && isLoggedInUserDock() {
                gv > 0 ? print("Restarting dock for console user"):nil
                terminate()
            }

        }
        
    }
    
    func printOptional(_ item: String?) -> String {
        item != nil ? item! : ""
    }
    
    func printList() {
        forEach() {tile in
            print("\(printOptional(tile.label))\t\(printOptional(tile.url))\t\(tile.section)\t\(path)\t\(printOptional(tile.bundleIdentifier))")
        }
    }
    
    func forEach(closure: (DockTile) -> Void) {
        for section in sections {
            if let items = dockItems[section] {
                for dockItem in items {
                    closure(dockItem)
                }
            }
        }
    }
    
    func waitForAppleModifications(maxSeconds: Int = 5) {
        var secondsWaited = 0
        while CFPreferencesCopyAppValue("mod-count" as CFString, dockDomain as CFString) as? Int ?? 0 < 2 && secondsWaited < maxSeconds {
            Thread.sleep(forTimeInterval: 1.0)
            secondsWaited += 1
        }
    }

    func consoleUser() -> String? {
        let store = SCDynamicStoreCreate(nil, "dockutil.consoleUser" as CFString, nil, nil)
        return SCDynamicStoreCopyConsoleUser(store, nil, nil) as String?
    }


    func consoleUserUID() -> uid_t {
        let store = SCDynamicStoreCreate(nil, "dockutil.consoleUserID" as CFString, nil, nil)
        var uid: uid_t = 0
        SCDynamicStoreCopyConsoleUser(store, &uid, nil)
        return uid
    }
    
    func terminate() {
        if let runningDock = NSWorkspace.shared.runningApplications.first(where: {$0.bundleIdentifier == "com.apple.dock"}) {
            gv > 0 ? print("Terminating running Dock"):nil
            runningDock.terminate()
        } else {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/killall")
            p.arguments = ["Dock"]
            do {
                try p.run()
            } catch {
                print(error)
            }
            p.waitUntilExit()
            gv > 0 ? print(p.arguments, p.terminationStatus):nil
        }
    }

    func add(_ _opts: DockAdditionOptions) -> Bool {
        
        var opts = _opts
        
        if opts.label == nil {
            if opts.tileType == .url {
                opts.label = opts.path
            } else {
                if opts.path.hasSuffix(".app") || opts.path.hasSuffix(".app/")  {
                    opts.label = URL(fileURLWithPath: opts.path).deletingPathExtension().lastPathComponent
                } else {
                    opts.label = URL(fileURLWithPath: opts.path).lastPathComponent
               }
            }
        }
        
        if opts.replacing != opts.label {
            let findResult = indexAndSectionOfItem(opts.label)
            if findResult.0 != -1 && findResult.1 == opts.section {
                print(opts.label!, "already exists in dock. Use --replacing '\(opts.label!)' to update an existing item")
                return false
            }
        }
                
        if opts.replacing != nil {
            let replaceOffset = index(within: opts.section, item: opts.replacing!)
            if replaceOffset > -1 {
                gv > 0 ? print("found", opts.replacing!):nil
                dockItems[opts.section]!.remove(at: replaceOffset)
                opts.position = String(replaceOffset + 1)
            }
        }
        
        let newGUID = Int.random(in: 1000000000..<9999999999)

        var itemDictionary: [String:AnyObject]
        switch opts.tileType {
        case .file:
            itemDictionary = [
                "GUID": newGUID as AnyObject,
                "tile-data": [
                    "file-data": [
                        "_CFURLString": opts.path,
                        "_CFURLStringType": 0
                    ],
                    "file-label": opts.label,
                    "file-type": (opts.section == .recentApps) ? 1 : 41
                ] as AnyObject,
                "tile-type": opts.tileType.rawValue as AnyObject
            ]
        case .directory:
            itemDictionary = [
                "GUID": newGUID as AnyObject,
                "tile-data": [
                    "directory": 1,
                    "arrangement": opts.sort.rawValue,
                    "displayas": opts.display.rawValue,
                    "showas": opts.view.rawValue,
                    "file-data": [
                        "_CFURLString": opts.path,
                        "_CFURLStringType": 0
                    ],
                    "file-label": opts.label,
                    "file-type": 2
                ] as AnyObject,
                "tile-type": opts.tileType.rawValue as AnyObject
            ]
        case .url:
            itemDictionary = [
                "GUID": newGUID as AnyObject,
                "tile-data": [
                    "label": opts.label,
                    "url": [
                        "_CFURLString": opts.path,
                        "_CFURLStringType": 15
                    ]
                ] as AnyObject,
                "tile-type": opts.tileType.rawValue as AnyObject
            ]
        case .spacer,.smallSpacer,.flexSpacer:
            itemDictionary = [
                "GUID": newGUID as AnyObject,
                "tile-data": [String:AnyObject]() as AnyObject,
                "tile-type": opts.tileType.rawValue as AnyObject
            ]
        }
        
        let newDockTile = DockTile(dict: itemDictionary, section: opts.section)
        
        return add(newDockTile, within: opts.section, at: opts.position, after: opts.after, before: opts.before)

    }
    
    func index(within section: DockSection, item: String?)-> Int {
        if let items = dockItems[section] {
            for (i, dockItem) in items.enumerated() {
                gv > 0 ? print(dockItem.label):nil
                let itemPath = URL(string: dockItem.url ?? "")?.path
                if dockItem.label == item || dockItem.bundleIdentifier == item || itemPath == item || dockItem.url == item {
                    return (i)
                }
            }
        }
        return -1 // negative index indicates item not found
    }
    
    func indexAndSectionOfItem(_ item: String?) -> (Int, DockSection) {
        var i = -1
        var foundWithinSection = DockSection.persistentApps
        for section in sections {
            i = index(within: section, item: item)
            if i != -1 {
                foundWithinSection = section
                break
            }
        }
        return (i, foundWithinSection)
    }
    
    func removeItem(_ removal: String) -> Bool {
        switch removal {
        case "all":
            for section in sections {
                dockItems[section] = []
            }
            return true
        case "spacer-tiles":
            for section in sections {
                if dockItems[section] != nil {
                    let items = dockItems[section]!
                    // Iterate from the end so removing items doesn not affect indices we have not visited yet.
                    for i in stride(from: items.count - 1, through: 0, by: -1) {
                        let item = items[i]
                        if item.tileType != nil && item.tileType!.contains("spacer") {
                            dockItems[section]!.remove(at: i)
                        }
                    }
                }
            }
            return true
        default:
            let result = indexAndSectionOfItem(removal)
            if result.0 > -1 {
                dockItems[result.1]?.remove(at: result.0)
                return true
            }
        }
        return false
    }
    
    func moveItem(_ label: String, position rawPosition: String?, before: String?, after: String?)-> Bool {
        
        let position = rawPosition?.replacingOccurrences(of: "\\", with: "") // handles necessary escape of "-" in argument so it is not interpretted as a flag/option

        let result = indexAndSectionOfItem(label)
        if result.0 < 0 { // negative index means not found
            return false
        }

        let originalIndex = result.0
        let destinationSection = result.1
        
        // Save the removed item for the move to new location
        guard let itemToMove = dockItems[result.1]?.remove(at: result.0) else {
            return false
        }
                
        return add(itemToMove, within: destinationSection, at: position, after: after, before: before, originalIndex: originalIndex)
    }
    
    func find(_ query: String) -> Bool {        
        let result = indexAndSectionOfItem(query)
        if result.0 > -1 {
            print(query, "was found in", result.1.rawValue, "at slot", result.0+1, "in", self.path)
            return true
        }
        print(query, "was not found in", self.path)
        return false
    }
    
    func add(_ tile: DockTile, within destinationSection: DockSection, at position: String?, after: String?, before: String?, originalIndex: Int = 0) -> Bool {
        gv > 0 ? print("adding \(tile.url)"): nil
        if position != nil {
            gv > 0 ? print("using position \(position)"):nil
            if ["beginning", "begin", "first", "start"].contains(position) {
                dockItems[destinationSection]!.insert(tile, at: 0)
                return true
            } else if ["end", "last"].contains(position) {
                print("moving to end of \(destinationSection)")
                dockItems[destinationSection]!.append(tile)
                return true
            } else if ["middle", "center"].contains(position) {
                let midpoint = Int(dockItems[destinationSection]!.count/2)
                dockItems[destinationSection]!.insert(tile, at: midpoint)
                return true
            } else {
                guard let offset = Int(position!) else {
                    print("Could not parse position")
                    return false
                }
                var newPosition = offset
                if position!.starts(with: "+") || position!.starts(with: "-") {
                    newPosition = offset + originalIndex + 1
                }
                newPosition -= 1 // dockutil has always used a start index of 1 which is annoying but I suppose one could consider Finder to be index 0
                if newPosition > dockItems[destinationSection]!.count {
                    dockItems[destinationSection]!.append(tile)
                    return true
                } else if newPosition < 0 {
                    dockItems[destinationSection]!.insert(tile, at: 0)
                    return true
                } else {
                    dockItems[destinationSection]!.insert(tile, at: newPosition)
                    return true
                }
            }
        } else {
            if after != nil {
                let result = indexAndSectionOfItem(after!)
                if result.0 > -1 {
                    dockItems[result.1]!.insert(tile, at: result.0 + 1)
                    return true
                } else {
                    print("relative item not found")
                    dockItems[destinationSection]!.append(tile)
                    return true
                }
            } else if before != nil {
                let result = indexAndSectionOfItem(before!)
                if result.0 > -1 {
                    dockItems[result.1]!.insert(tile, at: result.0)
                    return true
                } else {
                    print("relative item not found")
                    dockItems[destinationSection]!.append(tile)
                    return true
                }
            } else {
                gv > 0 ? print("appending item to end of dock"):nil
                dockItems[destinationSection]!.append(tile)
                return true
            }
        }
        return false
    }

}
