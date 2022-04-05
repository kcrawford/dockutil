//
//  DockItem.swift
//  dockutil
//
//  Created by Kyle Crawford on 6/18/20.
//  Copyright © 2022 Kyle Crawford. All rights reserved.
//

import Foundation

class DockTile {
    var dict: [String: AnyObject]
    var section: DockSection
    
    init(dict: [String:AnyObject], section: DockSection) {
        self.dict = dict
        self.section = section
    }
    
//    GUID = 1706939552;
//    "tile-data" =             {
//        book = {length = 592, bytes = 0x626f6f6b 50020000 00000410 30000000 ... 04000000 00000000 };
//        "bundle-identifier" = "com.apple.TV";
//        "dock-extra" = 0;
//        "file-data" =                 {
//            "_CFURLString" = "file:///System/Applications/TV.app/";
//            "_CFURLStringType" = 15;
//        };
//        "file-label" = TV;
//        "file-mod-date" = 3665116737;
//        "file-type" = 41;
//        "parent-mod-date" = 3665366337;
//    };
//    "tile-type" = "file-tile";
    
    func itemAtKeyPath(_ keyPath: String) -> Any? {
        (dict as NSDictionary).value(forKeyPath: keyPath)
    }

    var label : String? {
        get {
            (itemAtKeyPath("tile-data.file-label") ?? itemAtKeyPath("tile-data.label"))  as? String
        }
    }

    var tileType : String? {
        get {
            itemAtKeyPath("tile-type") as? String
        }
    }

    
    var bundleIdentifier : String? {
        get {
            itemAtKeyPath("tile-data.bundle-identifier") as? String
        }
    }
    
    var url : String? {
        get {
            (itemAtKeyPath("tile-data.file-data._CFURLString") ?? itemAtKeyPath("tile-data.url._CFURLString")) as? String
        }
    }
    
}
