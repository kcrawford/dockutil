//
//  Dock.swift
//  dockutil
//
//  Created by Kyle Crawford on 6/18/20.
//  Copyright © 2022 Kyle Crawford. All rights reserved.
//

import Foundation
import SystemConfiguration

class Dock {
    let dockApplicationID = "com.apple.dock"
    let sections : [DockSection] = [.persistentApps, .recentApps, .persistentOthers]
    
    var dockItems = [DockSection:[DockTile]]()
    var path: String
    var plist = [String:AnyObject]()
    
    
    init(path: String) {
        self.path = path
        read()
    }
    
    func readDockKeys()-> [String] {
        if let keys = CFPreferencesCopyKeyList(dockApplicationID as CFString, kCFPreferencesCurrentUser, kCFPreferencesAnyHost) as? [String] {
            print(keys)
            return keys
        }
        return []
    }
    
    func runningAsConsoleUser() -> Bool {
        return ProcessInfo.processInfo.userName == consoleUser()
    }
    
    func isLoggedInUserDock() -> Bool {
        guard let user = consoleUser() else { return false }
        let loggedInUserPlistPath = URL(fileURLWithPath: NSHomeDirectoryForUser(user) ?? NSHomeDirectory()).appendingPathComponent("Library/Preferences/com.apple.dock.plist").path
        gv > 0 ? print("Comparing", loggedInUserPlistPath, "to", self.path):nil

        return self.path == loggedInUserPlistPath
    }
    
    func read() {
        if isLoggedInUserDock() && runningAsConsoleUser() {
            gv > 0 ? print("Reading dock as a logged in user"):nil
            for section in sections {
                if let value = CFPreferencesCopyAppValue(section.rawValue as CFString, dockApplicationID as CFString) as? [[String: AnyObject]] {
                    dockItems[section] = value.map({item in
                        DockTile(dict: item, section: section)
                    })
                }
            }
        } else {
            guard let plistData = FileManager.default.contents(atPath: self.path) else {
                print("failed to read", self.path)
                return
            }
            
            guard let dict = try? PropertyListSerialization.propertyList(from: plistData, options: .mutableContainersAndLeaves, format: nil) as? [String:AnyObject] else {
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

            if restart {
                monitorDockForRestart()
            }
        
            for section in sections {
                if let sectionItems = self.dockItems[section] {
                    let items = sectionItems.map({dockItem in
                        dockItem.dict
                    })
                    CFPreferencesSetAppValue(section.rawValue as CFString, items as CFPropertyList?, dockApplicationID as CFString)
                }
            }
            CFPreferencesSynchronize(dockApplicationID as CFString, kCFPreferencesCurrentUser, kCFPreferencesAnyHost)
            if restart {
                DispatchQueue.main.asyncAfter(deadline: .now() + DispatchTimeInterval.seconds(15)) {
                    gv > 0 ? print("timed out waiting for dock plist file update"):nil
                    self.kickstart()
                }
                RunLoop.current.run()
            }
        } else {
            for section in sections {
                if let sectionItems = self.dockItems[section] {
                    let items = sectionItems.map({dockItem in
                        dockItem.dict
                    })
                    plist[section.rawValue] = items as AnyObject?
                }
            }
            guard let originalOwnerID = try? FileManager.default.attributesOfItem(atPath: self.path)[.ownerAccountID] else {
                print("unable to get owner of plist", self.path)
                return
            }
            guard let plistData = try? PropertyListSerialization.data(fromPropertyList: plist, format: .binary, options: 0) else {
                print("unable to serialize plist to data")
                return
            }
            do {
                try plistData.write(to: URL(fileURLWithPath: path))
                try FileManager.default.setAttributes([.ownerAccountID: originalOwnerID], ofItemAtPath: self.path)
                if restart && isLoggedInUserDock() {
                    gv > 0 ? print("Restarting dock for console user"):nil
                    kickstart()
                }
            } catch {
                print("Error saving plist", error)
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
        while CFPreferencesCopyAppValue("mod-count" as CFString, dockApplicationID as CFString) as? Int ?? 0 < 2 && secondsWaited < maxSeconds {
            Thread.sleep(forTimeInterval: 1.0)
            secondsWaited += 1
        }
    }
    
    
    func monitorDockForRestart() {
        let url = URL(fileURLWithPath: "Library/Preferences/com.apple.dock.plist", relativeTo: URL(fileURLWithPath: NSHomeDirectory()))
        gv > 0 ? print(url.absoluteString):nil
        if let fileHandle = try? FileHandle(forReadingFrom: url) {
            gv > 0 ? print("Got filehandle"):nil
            DispatchQueue.global().async {
                let source = DispatchSource.makeFileSystemObjectSource(
                    fileDescriptor: fileHandle.fileDescriptor,
                    eventMask: .all,
                    queue: DispatchQueue.main
                )
                source.setEventHandler {
                    let event = source.data
                    gv > 0 ? print("Got fileSystemEvent \(event)"):nil
                    gv > 0 ? print(source.dataStrings):nil
                    source.cancel()
                    DispatchQueue.global().asyncAfter(deadline: .now() + DispatchTimeInterval.milliseconds(250)) {
                        self.kickstart()
                    }
                }
                source.setCancelHandler {
                    try? fileHandle.close()
                }
                
                source.resume()
            }
        } else {
            print("couldn't open fileHandle for Dock plist")
        }
        

    }

    func consoleUser() -> String? {
        let store = SCDynamicStoreCreate(nil, "dockutil" as CFString, nil, nil)
        return SCDynamicStoreCopyConsoleUser(store, nil, nil) as String?
    }


    func consoleUserUID() -> uid_t {
        let store = SCDynamicStoreCreate(nil, "dockutil" as CFString, nil, nil)
        var uid: uid_t = 0
        SCDynamicStoreCopyConsoleUser(store, &uid, nil)
        return uid
    }

    func kickstart() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = [
            "kickstart",
            "-k",
            "gui/\(String(consoleUserUID()))/com.apple.Dock.agent"
        ]
        do {
            try p.run()
        } catch {
            print(error)
        }
        p.waitUntilExit()
        gv > 0 ? print(p.terminationStatus):nil
        exit(0)
    }

    func add(_ _opts: DockAdditionOptions) -> Bool {
        
        var opts = _opts
        
        if opts.label == nil {
            if opts.tileType == .url {
                opts.label = opts.path
            } else {
                opts.label = URL(fileURLWithPath: opts.path).deletingPathExtension().lastPathComponent
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
                    "file-type": 32
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
                    for (i, item) in dockItems[section]!.enumerated() {
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


extension DispatchSourceFileSystemObject {
    var dataStrings: [String] {
        var s = [String]()
        if data.contains(.all)      { s.append("all") }
        if data.contains(.attrib)   { s.append("attrib") }
        if data.contains(.delete)   { s.append("delete") }
        if data.contains(.extend)   { s.append("extend") }
        if data.contains(.funlock)  { s.append("funlock") }
        if data.contains(.link)     { s.append("link") }
        if data.contains(.rename)   { s.append("rename") }
        if data.contains(.revoke)   { s.append("revoke") }
        if data.contains(.write)    { s.append("write") }
        return s
    }
}
