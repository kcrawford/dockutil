//
//  DockUtil.swift
//  dockutil
//
//  Created by Kyle Crawford on 2/15/22.
//  Copyright © 2022 KC. All rights reserved.
//

import Foundation
import ArgumentParser
import Darwin

let VERSION = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as! String
var gv = 0 // Global verbosity

struct DockAdditionOptions {
    var path: String
    var replacing: String?
    var position: String?
    var after: String?
    var before: String?
    var section: DockSection = .persistentOthers
    var view: FolderView = .auto
    var display: FolderDisplay = .folder
    var sort: FolderSort = .datemodified
    var tileType: TileType
    var label: String?
}

enum FolderDisplay: Int, CaseIterable, ExpressibleByArgument {
    case folder = 1
    case stack = 0
    
    static func withLabel(_ label: String) -> FolderDisplay? {
        return self.allCases.first{ "\($0)" == label }
    }
}

struct FolderDisplayArgument: ExpressibleByArgument {
    let value: FolderDisplay
    
    init(argument: String) {
        self.value = FolderDisplay.withLabel(argument)!
    }
}

enum FolderView: Int, CaseIterable, ExpressibleByArgument {
    case auto = 0
    case fan = 1
    case grid = 2
    case list = 3

    static func withLabel(_ label: String) -> FolderView? {
        return self.allCases.first{ "\($0)" == label }
    }

}

struct FolderViewArgument: ExpressibleByArgument {
    let value: FolderView
    
    init(argument: String) {
        self.value = FolderView.withLabel(argument)!
    }
}

enum FolderSort: Int, CaseIterable {
    case name = 1
    case dateadded = 2
    case datemodified = 3
    case datecreated = 4
    case kind = 5

    static func withLabel(_ label: String) -> FolderSort? {
        return self.allCases.first{ "\($0)" == label }
    }
}

struct FolderSortArgument: ExpressibleByArgument {
    let value: FolderSort
    
    init(argument: String) {
        self.value = FolderSort.withLabel(argument)!
    }
}

enum DockSection: String {
    case persistentApps = "persistent-apps"
    case recentApps = "recent-apps"
    case persistentOthers = "persistent-others"
}

struct SectionArgument: ExpressibleByArgument {
    let value: DockSection
    
    init(argument: String) {
        if argument.hasPrefix("recent") {
            self.value = .recentApps
        } else {
            self.value = DockSection(rawValue: "persistent-" + argument)!
        }
    }
}

enum TileType: String {
    case spacer = "spacer-tile"
    case smallSpacer = "small-spacer-tile"
    case flexSpacer = "flex-spacer-tile"
    case file = "file-tile"
    case directory = "directory-tile"
    case url = "url-tile"
}

struct TileTypeArgument: ExpressibleByArgument {
    var tileType: TileType

    init?(argument: String) {
        self.tileType = TileType(rawValue: argument + "-tile")!
    }
}

struct Dockutil: ParsableCommand {
    
    static var configuration = CommandConfiguration(
        abstract: "dockutil is a command line utility for managing macOS dock items",
        discussion:
"""
  usage:     dockutil -h
  usage:     dockutil --add <path to item> | <url> [--label <label>] [ folder_options ] [ position_options ] [--no-restart] [ plist_location_specification ]
  usage:     dockutil --remove <dock item label> | <app bundle id> | all | spacer-tiles [--no-restart] [ plist_location_specification ]
  usage:     dockutil --move <dock item label>  position_options [ plist_location_specification ]
  usage:     dockutil --find <dock item label> [ plist_location_specification ]
  usage:     dockutil --list [ plist_location_specification ]
  usage:     dockutil --version

  Examples:
    The following adds TextEdit.app to the end of the current user's dock:
             dockutil --add /System/Applications/TextEdit.app

    The following replaces Time Machine with TextEdit.app in the current user's dock:
             dockutil --add /System/Applications/TextEdit.app --replacing 'Time Machine'

    The following adds TextEdit.app after the item Time Machine in every user's dock on that machine:
             dockutil --add /System/Applications/TextEdit.app --after 'Time Machine' --allhomes

    The following adds ~/Downloads as a grid stack displayed as a folder for every user's dock on that machine:
             dockutil --add '~/Downloads' --view grid --display folder --allhomes

    The following adds a url dock item after the Downloads dock item for every user's dock on that machine:
             dockutil --add vnc://miniserver.local --label 'Mini VNC' --after Downloads --allhomes

    The following removes System Preferences from every user's dock on that machine:
             dockutil --remove 'System Preferences' --allhomes

    The following moves System Preferences to the second slot on every user's dock on that machine:
             dockutil --move 'System Preferences' --position 2 --allhomes

    The following finds any instance of iTunes in the specified home directory's dock:
             dockutil --find iTunes /Users/jsmith

    The following lists all dock items for all home directories at homeloc in the form: item<tab>path<tab><section>tab<plist>
             dockutil --list --homeloc /Volumes/RAID/Homes --allhomes

    The following adds Firefox after Safari in the Default User Template without restarting the Dock
             dockutil --add /Applications/Firefox.app --after Safari --no-restart '/System/Library/User Template/English.lproj'

    The following adds a spacer tile in the apps section after Mail
             dockutil --add '' --type spacer --section apps --after Mail

    The following removes all spacer tiles
             dockutil --remove spacer-tiles

  Notes:
    When specifying a relative path like ~/Documents with the --allhomes option, ~/Documents must be quoted like '~/Documents' to get the item relative to each home
""")
    
    @Option(name: [.customShort("a"), .customLong("add")], help: ArgumentHelp(
    "Path or url of item to add",
//    discussion: "usage:     dockutil --add <path to item> | <url> [--add ...] [--label <label>] [ folder_options ] [ position_options ] [--no-restart] [ plist_location_specification ]",
    valueName: "path to item | url"))
    var additions: [String] = [String]()
    //    usage:     dockutil --add <path to item> | <url> [--label <label>] [ folder_options ] [ position_options ] [--no-restart] [ plist_location_specification ]
    
    @Option(name: [.customShort("r"), .customLong("remove")],
            help: ArgumentHelp(
                "Label or app bundle id of item to remove",
//                discussion:"usage:     dockutil --remove <dock item label> | <app bundle id> | all | spacer-tiles [--remove ...] [--no-restart] [ plist_location_specification ]",
                valueName: "label | app bundle id | path | url"
            ))
    var removals: [String] = [String]()
    //    usage:     dockutil --remove <dock item label> | <app bundle id> | all | spacer-tiles [--no-restart] [ plist_location_specification ]
   
    @Option(name: .shortAndLong, help: ArgumentHelp("Label or app bundle id of item to move", valueName: "label | app bundle id | path | url"))
    var move: String?
    //    usage:     dockutil --move <dock item label>  position_options [ plist_location_specification ]

    @Option(name: .shortAndLong, help: ArgumentHelp("Label or app bundle id of item to find", valueName: "label | app bundle id | path | url"))
    var find: String?
    //    usage:     dockutil --find <dock item label> [ plist_location_specification ]
   
    @Flag(name: [.customShort("L"), .long], inversion: .prefixedNo, help: "List dock items")
    var list: Bool = false
    //    usage:     dockutil --list [ plist_location_specification ]
    
    @Flag(name: [.customShort("V"), .long], inversion: .prefixedNo, help: "Display the version of dockutil")
    var version: Bool = false
    //    usage:     dockutil --version
    
    //    position_options:
    @Option(name: [.customShort("R"), .long], help: ArgumentHelp("Label or app bundle id of item to replace. Replaces the item with the given dock label or adds the item to the end if item to replace is not found.", valueName: "label | app bundle id | path | url"))
    var replacing: String?
    //      --replacing <dock item label name>                            replaces the item with the given dock label or adds the item to the end if item to replace is not found
    
    @Option(name: .shortAndLong, help: ArgumentHelp("Inserts the item at a fixed position: can be position by index number or keyword", valueName: "[+/-]index_number | beginning | end | middle"))
    var position: String?
    //      --position [ index_number | beginning | end | middle ]        inserts the item at a fixed position: can be an position by index number or keyword
    
    @Option(name: [.customShort("A"), .long], help: ArgumentHelp("Inserts the item immediately after the given dock label or at the end if the item is not found", valueName: "label | application bundle id"))
    var after: String?
    //      --after <dock item label name>                                inserts the item immediately after the given dock label or at the end if the item is not found
    
    @Option(name: [.customShort("B"), .long], help: ArgumentHelp("Inserts the item immediately before the given dock label or at the end if the item is not found", valueName: "label | application bundle id"))
    var before: String?
    //      --before <dock item label name>                               inserts the item immediately before the given dock label or at the end if the item is not found
    
    @Option(name: [.short, .customLong("section")], help: ArgumentHelp("Specifies whether the item should be added to the apps or others section", valueName: "apps | others"))
    var sectionArgument : SectionArgument?
    //      --section [ apps | others ]                                   specifies whether the item should be added to the apps or others section

    @Flag(inversion: .prefixedNo, help: "Whether to attempt to locate all home directories and perform the operation on each of them")
    var allhomes: Bool = false
    //      --allhomes                                                    attempts to locate all home directories and perform the operation on each of them
    
    @Option(name: [.customShort("H"), .long], help: "Location for home directories")
    var homeloc: String = "/Users"
    //      --homeloc                                                     overrides the default /Users location for home directories

    //    folder_options:
    @Option(help: ArgumentHelp("Folder view option when adding a folder", valueName: "grid|fan|list|auto"))
    var view: FolderViewArgument?
    //      --view [grid|fan|list|auto]                                   stack view option
    
    @Option(help: ArgumentHelp("Folder display option when adding a folder", valueName: "folder|stack"))
    var display: FolderDisplayArgument?
    //      --display [folder|stack]                                      how to display a folder's icon
    
    @Option(help: ArgumentHelp("Folder sort option when adding a folder", valueName: "name|dateadded|datemodified|datecreated|kind"))
    var sort: FolderSortArgument?
    //      --sort [name|dateadded|datemodified|datecreated|kind]         sets sorting option for a folder view

    @Option(name: .shortAndLong, help: "Label or bundle identifier of item to add, remove, move or find")
    var label: String?
    
    
    @Option(name: [.short, .customLong("type")], help: ArgumentHelp("Specify a custom tile type for adding spacers (spacer|small-spacer|flex-spacer)", valueName:"spacer|small-spacer|flex-spacer"))
    var tileTypeArgument: TileTypeArgument?

//    %(progname)s --add '' --type spacer --section apps --after Mail
//    %(progname)s --add '' --type small-spacer --section apps --after Mail
//    %(progname)s --add '' --type flex-spacer --section apps --after Mail

    
    @Flag(inversion: .prefixedNo, help: "Whether to restart the Dock to apply the changes.")
    var restart = true

    //    global_options:
    //      -v                                                            verbose output
    
    @Flag(name: [.short, .customLong("verbose")], help: "Verbose output")
    var verbosity: Int

    
    @Argument(help: ArgumentHelp(
        "",
        discussion: """
<path(s) to specific dock plist(s)>                           /Users/username/Library/Preferences/com.apple.dock.plist
<path(s) to home directory>                                   /Users/username
--allhomes                                                    attempts to locate all home directories and perform the operation on each of them
--homeloc                                                     overrides the default /Users location for home directories
"""
    ))
    var plistLocationSpecifications: [String] = [URL(fileURLWithPath: NSHomeDirectoryForUser(ProcessInfo.processInfo.environment["SUDO_USER"] ?? NSUserName()) ?? NSHomeDirectory()).appendingPathComponent("Library/Preferences/com.apple.dock.plist").path]

    mutating func run() throws {
        
        gv = verbosity
        var errors = [String]()
        
        gv > 0 ? print("verbose mode \(gv)") : nil
        
        
        if version {
            print(VERSION)
            throw(ExitCode(0))
        }
        
        if additions.count < 1 && removals.count < 1 && move == nil && find == nil && !list && !version {
            print(Dockutil.helpMessage()) // no action options specified
            errors.append("No action specified")
        }
        
        var plistPaths = plistLocationSpecifications

        if allhomes {
            plistPaths = [String]()
            let homesURL = URL(fileURLWithPath: homeloc)
            let possibleHomes = (try? FileManager.default.contentsOfDirectory(at: homesURL, includingPropertiesForKeys: [.isDirectoryKey], options: [])) ?? []
            gv > 0 ? print(possibleHomes) : nil
            for possibleHome in possibleHomes {
                let prefsDirURL = possibleHome.appendingPathComponent("Library/Preferences")
                gv > 0 ? print(prefsDirURL.path): nil
                if FileManager.default.fileExists(atPath: prefsDirURL.path) {
                    let path = prefsDirURL.appendingPathComponent("com.apple.dock.plist").path
                    plistPaths.append(path)
                }
            }
        }
        
        gv > 0 ? print("Plist paths:", plistPaths):nil
                
        if plistPaths.count < 1 {
            throw(ValidationError("no dock plists were found"))
        }
        
        for _plistPath in plistPaths {
            var plistPath = _plistPath

            gv > 0 ? print("processing", plistPath):nil

            if  ["~", "~/"].contains(plistPath) {
                plistPath = NSHomeDirectory()
            }
            var isDir: ObjCBool = false
            FileManager.default.fileExists(atPath: plistPath, isDirectory: &isDir)
            if isDir.boolValue {
                gv > 0 ? print(plistPath, "is a directory"):nil
                plistPath = URL(fileURLWithPath: plistPath).appendingPathComponent("Library/Preferences/com.apple.dock.plist").path
            }

            plistPath = URL(fileURLWithPath: plistPath).absoluteURL.path

            if !FileManager.default.fileExists(atPath: plistPath) {
                if allhomes {
                    gv > 0 ? print("Skipping:", plistPath, "does not seem to be a home directory or a dock plist"):nil
                    continue
                } else {
                    throw(ValidationError("\(plistPath) does not seem to be a home directory or a dock plist"))
                }
            }
            
            gv > 0 ? print(plistPath):nil

            let dock = Dock(path: plistPath)

            let defaultPlistPath = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Preferences/com.apple.dock.plist").path
            
            if plistPath == defaultPlistPath {
                dock.waitForAppleModifications(maxSeconds: 5)
            }
            
        
            var dockWasModified = false

            if move != nil {
                if position == nil && after == nil && before == nil {
                    throw ValidationError("Please specify a 'position' for the move")
                }
                
                if dock.moveItem(move!, position: position, before: before, after: after) {
                    dockWasModified = true
                } else {
                    print("Move failed for \(move!)")
                    errors.append("Move failed for \(move!) in \(plistPath)")
                }
            }
            
            if removals.count > 0 {
                for removal in removals {
                    if dock.removeItem(removal) {
                        dockWasModified = true
                    } else {
                        errors.append("Remove failed for \(removal) in \(plistPath)")
                    }
                }
            }
            
            if additions.count > 0 {
                for _addition in additions {
                    
                    // Copy addition so we can modify it
                    var addition = _addition

                    // Remove file:// prefix so url is treated as a path
                    if addition.starts(with: "file://") {
                        addition = String(addition.dropFirst(7))
                    }
                    
                    // Expand "~" to home directory
                    if addition.starts(with: "~") {
                        let homeDir = plistPath.replacingOccurrences(of: "/Library/Preferences/com.apple.dock.plist", with: "")
                        addition = homeDir + addition.dropFirst(1)
                    }
                    
                    // Handle Applications that reside at /System/Applications
                    if addition.hasPrefix("/Applications/") && !FileManager.default.fileExists(atPath: addition) {
                        let possibleSystemAppPath = "/System" + addition
                        if FileManager.default.fileExists(atPath: possibleSystemAppPath) {
                            FileHandle.standardError.write("Notice: adding item at \(possibleSystemAppPath) rather than \(addition)\n".data(using: .utf8)!)
                            addition = possibleSystemAppPath
                        }
                    }
                                        
                    var section = DockSection.persistentOthers // default value
                    
                    if sectionArgument != nil {
                        section = sectionArgument!.value
                    } else {
                        if addition.hasSuffix(".app") || addition.hasSuffix(".app/") {
                            section = .persistentApps
                        } else if display != nil || view != nil || sort != nil {
                            section = .persistentOthers
                        }
                    }
                    
                    var tileType: TileType
                    if tileTypeArgument != nil {
                        tileType = tileTypeArgument!.tileType
                    } else {
                        var additionIsDirectory: ObjCBool = false
                        FileManager.default.fileExists(atPath: addition, isDirectory: &additionIsDirectory)
                        if additionIsDirectory.boolValue && section != .persistentApps {
                            tileType = .directory
                        } else if addition.contains("://") {
                            tileType = .url
                            section = .persistentOthers
                        } else {
                            tileType = .file
                        }
                    }
                    
                    if tileType != .url { // paths can't be relative in dock items
                        addition = URL(fileURLWithPath: addition).absoluteURL.path
                    }
                    
                    print("adding \(addition)")

                    let additionOptions = DockAdditionOptions(
                        path: addition,
                        replacing: replacing,
                        position: position,
                        after: after,
                        before: before,
                        section: section,
                        view: view?.value ?? .auto,
                        display: display?.value ?? .folder,
                        sort: sort?.value ?? .datemodified,
                        tileType: tileType,
                        label: label
                    )
                    
                    if dock.add(additionOptions) {
                        dockWasModified = true
                    } else {
                        print("item", addition, "was not added to Dock")
                        errors.append("Add failed for \(addition) in \(plistPath)")
                    }

                }
            }
            
            if find != nil {
                if !dock.find(find!) {
                    errors.append("Find failed for \(find!) in \(plistPath)")
                }
            }
            
            if list {
                dock.printList()
            }
            
            if dockWasModified {
                dock.save(restart: restart)
            }

        }

        if errors.count > 0 {
            let errorOutput = "\(errors.joined(separator: "\n"))\n"
            FileHandle.standardError.write(errorOutput.data(using: .utf8)!)
            throw(ExitCode(1))
        }
        
    }

}
