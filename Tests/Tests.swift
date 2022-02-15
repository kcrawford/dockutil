//
//  Tests.swift
//  Tests
//
//  Created by KC on 6/18/20.
//  Copyright © 2020 KC. All rights reserved.
//

import XCTest
@testable import dockutil

class Tests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }
    
    func testDock() throws {
        // This is an example of a functional test case.
        // Use XCTAssert and related functions to verify your tests produce the correct results.
        let dock = Dock()
        XCTAssert(dock.items.count > 0)
//        XCTAssert(dock.apps() as Any is [PersistentApp])
//        XCTAssert(dock.apps().count > 0, "There should be some apps in dock")
    }


    func testExample() throws {
        // This is an example of a functional test case.
        // Use XCTAssert and related functions to verify your tests produce the correct results.
        
    }

    func testPerformanceExample() throws {
        // This is an example of a performance test case.
        measure {
            // Put the code you want to measure the time of here.
        }
    }

}
