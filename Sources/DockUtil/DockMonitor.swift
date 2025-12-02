//
//  DockMonitor.swift
//  dockutil
//
//

import AppKit
import OSLog

@MainActor
class DockMonitor {
    let logger = Logger(subsystem: Bundle().bundleIdentifier ?? "dockutil.cli.tool", category: "monitor")
    let dock = Dock()
    var appsDefaultsObserver: NSKeyValueObservation?
    var metadataQueryObserver: NSObjectProtocol?
    let metadataQuery = NSMetadataQuery()

    init() {
        logger.info("started")
        logger.debug("Checking for running Dock")
        dock.waitForRunningDock(maxSeconds: 300)
        if !dock.isRunning() {
            print("Timed out while checking if Dock agent is running")
            exit(1)
        } else {
            logger.debug("Found running Dock")
        }
        logger.debug("Waiting for default apple modifications to Dock")
        dock.waitForAppleModifications(maxSeconds: 300)
        logger.debug("Setting up defaults observer")
        appsDefaultsObserver = UserDefaults.standard.observe(\.apps, options: [.initial, .new], changeHandler: {(defaults, change) in
            self.logger.debug("apps changed from \(String(describing: change.oldValue)) to \(String(describing: change.newValue))")

            self.logger.debug("Defaults key: apps, value: \(defaults.array(forKey: "apps") as? [String] ?? [String](), privacy: .public)")
                        Task { @MainActor in
                            if !self.handleClearDockOnceIfOnlyAppleItems() {
                                self.addItems()
                            }
                        }
                   })

    }

    func handleClearDockOnceIfOnlyAppleItems() -> Bool {
        let shouldClear = UserDefaults.standard.bool(forKey: "clearDockOnceIfOnlyAppleItems")
        let didClear = UserDefaults.standard.bool(forKey: "didClearDockOnce")
        if shouldClear && !didClear  {
            logger.info("Checking for only Apple items in dock")
            dock.read()
            for bundleID in dock.persistentAppBundleIDs() {
                if !bundleID.hasPrefix("com.apple.") {
                    logger.info("Found non-Apple items in dock -- will not clear dock")
                    UserDefaults.standard.set(true, forKey: "didClearDockOnce")
                    return false
                }
            }
            logger.debug("Only Apple items found in Dock -- clearing Dock")
            let modifiedDock = dock.removeItem("all")
            dock.save(restart: false)
            UserDefaults.standard.set(true, forKey: "didClearDockOnce")
            // Re-add any items that got removed
            UserDefaults.standard.set([String](), forKey: "appCompletions")
            self.addItems()
            return modifiedDock
        }
        return false
    }


    func addItems() -> Bool {
        dock.read() // get most up-to-date dock
        var dockWasModified = false
        defer {
            if dockWasModified {
                dock.save(restart: false)
                dock.bootstrap()
                dock.kickstart()
            }
        }
        let additions = UserDefaults.standard.array(forKey: "apps") as? [String] ?? [String]()
        logger.debug("additions: \(additions)")
        var appCompletions = UserDefaults.standard.array(forKey: "appCompletions") as? [String] ?? [String]()
        var dockItemPositions = [String:Int]()
        var missingAdditions = [String]()
        for (i, addition) in additions.enumerated() {
            var addPosition = dock.dockItems[.persistentApps]?.count ?? 0
            if !appCompletions.contains(addition) {
                if dock.find(addition) {
                    appCompletions.append(addition) // already in Dock
                } else if FileManager.default.fileExists(atPath: addition.resolvedPath()) {
                    // figure out where to add
                    // look for existing items starting with item to the left of addition
                    var foundOnLeft = false
                    for l in stride(from: i-1, through: 0, by: -1) {
                        // Check for item in cache otherwise fetch and update cache
                        if dockItemPositions[additions[l]] == nil {
                            let (foundIndex, _) = dock.indexAndSectionOfItem(additions[l])
                            dockItemPositions[additions[l]] = foundIndex
                        }

                        if dockItemPositions[additions[l]]! > -1 { // Found
                            addPosition = dockItemPositions[additions[l]]! + 2
                            foundOnLeft = true
                            break
                        }
                    }

                    // if no items on left are found, check on right for first item to insert addition before
                    if !foundOnLeft {
                        for r in stride(from: i+1, through: (additions.count - 1), by: 1) {
                            // Check for item in cache otherwise fetch and update cache
                            if dockItemPositions[additions[r]] == nil {
                                let (foundIndex, _) = dock.indexAndSectionOfItem(additions[r])
                                dockItemPositions[additions[r]] = foundIndex
                            }

                            // Check for item in cache
                            if dockItemPositions[additions[r]]! > -1 { // Found
                                addPosition = dockItemPositions[additions[r]]! + 1
                                break
                            }
                        }
                    }
                    dockWasModified = true
                    dock.bootout()
                    if dock.add(DockAdditionOptions(path: addition.resolvedPath(), position: String(addPosition), section: .persistentApps, tileType: .file)) {
                        dockItemPositions = [String:Int]() // invalidate cache
                        appCompletions.append(addition)
                    }
                } else {
                    missingAdditions.append(addition)
                }
            }
        }
        UserDefaults.standard.set(appCompletions, forKey: "appCompletions")

        setupMetadataQuery(for: missingAdditions)

        return dockWasModified
    }

    func monitoringDirectories(for appPaths: [String]) -> [URL] {
        var monitorPaths = Set([URL]())
        for addition in appPaths {
            // add the closest parent directory that exists for monitoring
            var url = URL(fileURLWithPath: addition)
            while true {
                let parent = url.deletingLastPathComponent()
                logger.debug("Checking for parent directory \(parent.path) of \(addition)")
                if FileManager.default.fileExists(atPath: parent.path) {
                    monitorPaths.insert(parent)
                    break
                }
                url = parent
            }
        }
        return Array(monitorPaths)
    }

    func createMetadataPredicate(for appPaths: [String]) -> NSPredicate {

        let appsPredicate = NSPredicate(format: "%K == %@", argumentArray: [NSMetadataItemContentTypeKey, "com.apple.application-bundle"])

        let fileNames = appPaths.map { URL(fileURLWithPath: $0).lastPathComponent }

        var namePredicates = [NSPredicate]()

        for fileName in fileNames {
            namePredicates.append(NSPredicate(format: "%K == %@", NSMetadataItemFSNameKey, fileName))
        }
        let appNamesPredicate: NSPredicate
        if namePredicates.count > 1 {
            appNamesPredicate = NSCompoundPredicate(orPredicateWithSubpredicates: namePredicates)
        } else {
            appNamesPredicate = namePredicates[0]
        }

        let futureAddsOnlyPredicate = NSPredicate(format: "%K > %@", NSMetadataItemDateAddedKey, Date() as NSDate)

        return NSCompoundPredicate(andPredicateWithSubpredicates: [
            appsPredicate,
            futureAddsOnlyPredicate,
            appNamesPredicate,
        ])

    }

    func setupMetadataQuery(for appPaths: [String]) {
        guard appPaths.count > 0 else {
            metadataQuery.stop()
            logger.info("no apps to monitor")
            if UserDefaults.standard.bool(forKey: "disableBackgroundItemWhenDone") {
                logger.info("disableBackgroundItemWhenDone is true. Disabling launch agent")
                disableLaunchAgent()
                logger.info("booting out launch agent")
                bootoutLaunchAgent()
                exit(0)
            } else if UserDefaults.standard.bool(forKey: "quitWhenDone") {
                logger.info("quitWhenDone is true. Will exit now.")
                exit(0)
            }
            return
        }
        metadataQuery.searchScopes = monitoringDirectories(for: appPaths)
        metadataQuery.predicate = createMetadataPredicate(for: appPaths)
        metadataQuery.notificationBatchingInterval = 5
        metadataQuery.start()
        metadataQuery.enableUpdates()
        logger.info("metadataQuery.searchScopes: \(self.metadataQuery.searchScopes)")
        logger.info("metadataQuery.predicate: \(self.metadataQuery.predicate)")
        NotificationCenter.default.removeObserver(metadataQueryObserver)
        metadataQueryObserver = NotificationCenter.default.addObserver(forName: .NSMetadataQueryDidUpdate, object: metadataQuery, queue: .main) { notification in
            let addedItems, changedItems, removedItems: [NSMetadataItem]

            addedItems = notification.userInfo?[kMDQueryUpdateAddedItems] as? [NSMetadataItem] ?? [NSMetadataItem]()
            let newAdditions = addedItems.map { $0.value(forAttribute: NSMetadataItemPathKey) } as? [String] ?? [String]()
            self.logger.debug("Added: \(newAdditions)")

            changedItems = notification.userInfo?[kMDQueryUpdateChangedItems] as? [NSMetadataItem] ?? [NSMetadataItem]()
            let changes = changedItems.map { $0.value(forAttribute: NSMetadataItemPathKey) } as? [String] ?? [String]()
            self.logger.debug("Changed: \(changes)")

            let possibleAdditions = Set(newAdditions+changes)

            // Check for any additions in our pending items
            let additions = UserDefaults.standard.array(forKey: "apps") as? [String] ?? [String]()
            let appCompletions = UserDefaults.standard.array(forKey: "appCompletions") as? [String] ?? [String]()

            let pending = Set(additions).subtracting(Set(appCompletions))

            if !Set(possibleAdditions).isDisjoint(with: pending) {
                // We have items that are pending
                self.logger.debug("Calling addItems for pending item(s) that were just added")
                Task {@MainActor in
                    self.addItems()
                }
            } else {
                self.logger.debug("No new items found in pending")
            }
//            removedItems = notification.userInfo?[kMDQueryUpdateRemovedItems] as? [NSMetadataItem]
//            print(Date(), "Removed", removedItems?.map { $0.values(forAttributes: [NSMetadataItemPathKey,NSMetadataItemCFBundleIdentifierKey]) })
        }
    }

    func disableLaunchAgent() {
//        disableBackgroundItemWhenDone
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = [
            "disable",
            "gui/\(Dock.consoleUserUID())/dockutil.cli.tool.agent",
        ]
        do {
            try p.run()
        } catch {
            print(error)
        }
        p.waitUntilExit()
    }

    func bootoutLaunchAgent() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = [
            "bootout",
            "gui/\(Dock.consoleUserUID())/dockutil.cli.tool.agent",
        ]
        do {
            try p.run()
        } catch {
            print(error)
        }
        p.waitUntilExit()
    }

}
