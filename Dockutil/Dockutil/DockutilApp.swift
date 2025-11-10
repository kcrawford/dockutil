//
//  DockutilApp.swift
//  Dockutil
//
//  Created by tempadmin on 10/15/25.
//

import SwiftUI

@main
struct DockutilApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onAppear() {
                    NSApplication.shared.terminate(nil)
                }
        }
    }
}
