# Modern Swift/SwiftUI Best Practices for macOS 26 and Newer

Modern Swift/SwiftUI best practice means building Mac apps with SwiftUI as the default app architecture, Swift 6 concurrency as a correctness model, AppKit as a deliberate platform boundary, and Apple's current design, accessibility, testing, and performance tools as part of normal development.

A concise definition:

> Modern Swift/SwiftUI for macOS 26+ means SwiftUI-first, Mac-native, Swift 6-safe, system-design-aligned development. Use SwiftUI for app structure and standard interface layers. Isolate AppKit interop behind narrow adapters. Model state with Observation and clear domain types. Use async/await and strict concurrency. Prefer standard macOS controls, materials, menus, commands, windows, and document models. Validate behavior with focused tests and measured performance. Custom UI, compatibility scaffolding, and fallback code should exist only when they serve the intended design.

## 1. Use SwiftUI first, but not SwiftUI only

For new macOS apps, SwiftUI should usually own the app shell: `App`, scenes, windows, navigation, settings, commands, toolbars, sheets, forms, and ordinary UI composition.

Apple describes SwiftUI as a declarative, data-driven framework for building apps across Apple platforms. Apple's technology overview also describes SwiftUI as the best choice for creating new apps, while still allowing existing AppKit views and view controllers to be incorporated when needed.[^swiftui-docs][^swiftui-apps][^app-design-ui]

Modern SwiftUI does not mean avoiding AppKit completely. It means using AppKit intentionally when platform-specific behavior needs it.

Good rule:

> SwiftUI owns app structure and normal UI. AppKit fills platform gaps.

## 2. Make the app feel native to macOS

A modern Mac app should feel like a Mac app before it feels like a cross-platform SwiftUI app.

For macOS, this means using menus, commands, keyboard shortcuts, toolbars, sidebars, settings windows, document behavior, file drag and drop, undo and redo, focus behavior, accessibility, and flexible window layouts where they fit.

Apple's macOS design guidance emphasizes the Mac as a powerful, spacious, flexible platform where people often use several apps at once.[^designing-for-macos] Apple's interface guidance also notes that Mac windows should support flexible layouts and adapt to different sizes and modes.[^interface-fundamentals]

In practice, avoid forcing an iOS-style interaction model onto macOS. A Mac app should respect mouse, keyboard, menu bar, multi-window, and file-system expectations.

## 3. Use the current macOS design system

For macOS 26-era apps, follow Apple's current design system instead of recreating older macOS chrome by hand.

Apple's Liquid Glass documentation says standard SwiftUI, UIKit, and AppKit components such as controls and navigation elements pick up the new appearance and behavior automatically.[^liquid-glass] Apple's adoption guidance also says that apps using standard components pick up the latest look and feel when built with the latest SDKs and run on the latest platform releases.[^adopting-liquid-glass]

In practice:

- Prefer standard controls, materials, sidebars, toolbars, menus, search fields, sheets, popovers, and SF Symbols.
- Let the system provide the current visual language where possible.
- Use custom chrome only when the product needs it.
- Keep content readable.
- Treat translucency and depth as hierarchy tools, not decoration.

Liquid Glass should not mean making everything translucent. A modern app should use the system look while preserving clarity, contrast, and task focus.

## 4. Treat Swift 6 concurrency as architecture, not cleanup

Swift 6 language mode makes data-race safety checks required. Swift.org states that with Swift 6 language mode, the compiler can guarantee that concurrent programs are free of data races, and safety checks that were previously optional become required.[^swift6-migration]

Modern Swift code should have clear ownership:

- UI state belongs on the main actor.
- Long-running work uses `async` and `await`.
- Parallel work uses structured concurrency.
- Values that cross task or actor boundaries are `Sendable`.
- Shared mutable state is isolated behind actors or removed.
- `@preconcurrency` and `@unchecked Sendable` are narrow boundary tools, not general fixes.

Swift.org's migration guide notes that complete concurrency checking can reveal many issues in existing code, including latent data-isolation problems.[^swift6-strategy][^swift6-common] Apple's Swift 6 guidance also recommends adopting strict concurrency checking as part of migration.[^swift6-apple]

Good rule:

> UI state is main-actor isolated. Background work is async, cancellable, and does not mutate UI state directly.

## 5. Use Observation and value-driven state

Modern SwiftUI style is data-driven. Views describe UI as a function of state. State should be small, explicit, and close to its owner.

Apple's SwiftUI model-data documentation says to use the `Observable` macro when adding observation support to a type, and that SwiftUI forms dependencies when a view reads observable model data in its body.[^model-data][^managing-model-data] Apple also provides migration guidance from `ObservableObject` to the `Observable` macro.[^observable-migration]

A good default ownership model:

- View-local state stays in the view.
- Shared app state lives in small observable models.
- Services perform work.
- Actors protect shared mutable resources.
- Persistence is chosen by product need, not by fashion.

Avoid large view models that only mirror view state. SwiftUI is already a state-driven UI framework. A view model should earn its existence by owning meaningful coordination, transformation, or feature behavior.

## 6. Keep architecture simple and domain-centered

For most modern SwiftUI apps, avoid starting with heavyweight MVVM, Redux, or custom architecture unless the app truly needs it.

A good default architecture is:

```text
App / Scene
Views
Feature models
Domain services
Persistence layer
Platform adapters
```

Key principle:

> Put business rules outside the view, but do not create abstraction only to move code around.

The goal is not to maximize abstraction. The goal is to make ownership obvious, keep compiler isolation checks meaningful, and make the app easier to change.

## 7. Keep platform boundaries explicit

Modern macOS SwiftUI code can bridge to AppKit, but the boundary should be clean.

Good pattern:

```text
SwiftUI view/state layer
?
small adapter or coordinator boundary
?
AppKit view/controller/delegate
```

Use `NSViewRepresentable`, `NSViewControllerRepresentable`, coordinators, and narrow adapter types when SwiftUI needs AppKit support. Do not let AppKit objects leak through the whole app.

This is especially useful for advanced text editing, low-level drawing, custom window behavior, mature drag and drop behavior, responder-chain integration, or controls SwiftUI does not yet model well.

For example, Apple describes `NSTextView` as the AppKit front-end class for drawing text, handling selection and editing, user events, input management, key bindings, rich text, attachments, and marked text attributes.[^nstextview]

## 8. Use TextKit 2 where it fits text-heavy apps

For text-heavy macOS apps, use the modern text system where it is appropriate.

Apple's TextKit documentation says that when using `NSTextView`, the TextKit engine is available through properties such as `textLayoutManager`, `textContainer`, and `textStorage`. Apple also states that `NSTextView` provides access to a modern `textLayoutManager` engine and a legacy `layoutManager` engine.[^textkit]

Modern practice is to use current text APIs when they are stable for the app's needs, while keeping the AppKit/TextKit boundary contained.

## 9. Prefer native document and window models when they fit

For document-style apps, prefer SwiftUI's document architecture when it matches the app's needs.

Apple describes `DocumentGroup` as a SwiftUI scene that adds document support to an app. On macOS, this includes document-based menu support and opening multiple documents. The document model must conform to `FileDocument` or `ReferenceFileDocument`.[^documentgroup]

Apple's document-based SwiftUI sample uses a `DocumentGroup` scene and a document type that conforms to `FileDocument`.[^document-sample]

Use document architecture when the user thinks in files. Use app-state or database architecture when the user thinks in libraries, projects, accounts, or synced collections.

## 10. Measure SwiftUI performance instead of guessing

Modern SwiftUI best practice includes profiling. Apple's SwiftUI performance documentation recommends using Instruments to detect hangs and hitches, long view-body updates, and frequent SwiftUI updates that hurt responsiveness.[^swiftui-performance]

Apple's Xcode performance guidance also describes improving rendering efficiency by profiling with the SwiftUI instrument to identify long-running view body updates and frequent updates.[^rendering-efficiency]

Good performance practice means checking real behavior:

- Launch time
- View update frequency
- Memory use
- Scrolling smoothness
- File I/O latency
- Task cancellation
- Main-thread stalls
- Energy use where relevant

Avoid guessing from code shape alone. Measure the user-visible behavior.

## 11. Use Swift Testing for new tests where practical

For new Swift code, prefer Swift Testing where it fits. Keep XCTest where the project, framework, or existing tests still need it.

Apple describes Swift Testing as a framework for Swift packages and Xcode projects that integrates with Swift Package Manager, supports flexible test organization, customizable metadata, and scalable execution.[^swift-testing] Apple also states that Swift Testing works with XCTest, so newer Swift Testing tests can run side by side with existing XCTest tests.[^swift-testing-xcode]

Test behavior first:

- Domain rules
- Parsing and formatting
- Persistence behavior
- Concurrency and cancellation behavior
- Platform adapters
- Critical UI flows

Previews are useful for design feedback, but previews are not a substitute for tests.

## 12. Use SwiftPM and reproducible dependencies

Use Swift Package Manager for modular Swift code and explicit dependencies. Keep dependencies small, pinned, and justified.

SwiftPM resolves dependencies using `Package.swift` and `Package.resolved` when that file is present.[^swiftpm-resolve] The `swift package resolve` command can also be configured to use only versions from `Package.resolved` and fail if resolution is out of date.[^swiftpm-package-resolve]

For app repositories, commit `Package.resolved` so app builds are reproducible. Use binary packages and build plugins only when they are worth the build and maintenance cost.

Good rule:

> Dependencies should reduce product risk, not become hidden architecture.

## 13. Design for accessibility, localization, and system behavior

Modern macOS apps should respect platform behavior:

- VoiceOver labels
- Keyboard navigation
- Focus rings
- High contrast
- Reduced motion
- Reduced transparency
- Localization
- Right-to-left layout where relevant
- Autosave and resume behavior
- Sandboxing expectations
- Privacy prompts

Apple's Human Interface Guidelines describe design guidance and best practices for Apple platforms.[^hig] Apple's SwiftUI documentation also describes built-in support for accessibility and localization.[^swiftui-docs]

For macOS 26 Liquid Glass, accessibility matters even more because transparency and depth can reduce readability if overused.

## 14. Remove old compatibility layers when targeting only modern macOS

When the target is macOS 26 or newer, modern practice means using current APIs directly.

Avoid keeping old compatibility branches, legacy delegates, old layout workarounds, or deprecated patterns unless they still serve a real need. Compatibility code should exist because the product needs it, not because inherited architecture already has it.

Good rule:

> Fix the design, not the symptom. Use narrow fallbacks only when they are part of the intended design.

## 15. Compact checklist

Use this as a quick review checklist for a macOS 26+ SwiftUI app:

- SwiftUI owns the app shell.
- AppKit interop is isolated behind narrow adapters.
- The app feels native to macOS.
- Standard controls and materials carry the current design system.
- Swift 6 strict concurrency is treated as a correctness baseline.
- UI state is main-actor isolated.
- Background work is async, cancellable, and structured.
- Observable state is small and owned.
- Architecture follows domain ownership rather than pattern fashion.
- Document, window, command, and menu models match Mac expectations.
- Performance is measured with Instruments.
- New tests use Swift Testing where practical.
- Dependencies are explicit, small, and reproducible.
- Accessibility and localization are built in early.
- Legacy compatibility code exists only when it serves the product.

## References

[^swiftui-docs]: Apple Developer Documentation, "SwiftUI." https://developer.apple.com/documentation/swiftui
[^swiftui-apps]: Apple Developer Documentation, "SwiftUI apps." https://developer.apple.com/documentation/technologyoverviews/swiftui
[^app-design-ui]: Apple Developer Documentation, "App design and UI." https://developer.apple.com/documentation/technologyoverviews/app-design-and-ui
[^hig]: Apple Developer Documentation, "Human Interface Guidelines." https://developer.apple.com/design/human-interface-guidelines/
[^designing-for-macos]: Apple Developer Documentation, "Designing for macOS." https://developer.apple.com/design/human-interface-guidelines/designing-for-macos
[^interface-fundamentals]: Apple Developer Documentation, "Interface fundamentals." https://developer.apple.com/documentation/technologyoverviews/interface-fundamentals
[^liquid-glass]: Apple Developer Documentation, "Liquid Glass." https://developer.apple.com/documentation/technologyoverviews/liquid-glass
[^adopting-liquid-glass]: Apple Developer Documentation, "Adopting Liquid Glass." https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass
[^swift6-migration]: Swift.org, "Migrating to Swift 6." https://www.swift.org/migration/documentation/migrationguide/
[^swift6-strategy]: Swift.org, "Migration Strategy." https://www.swift.org/migration/documentation/swift-6-concurrency-migration-guide/migrationstrategy/
[^swift6-common]: Swift.org, "Common Compiler Errors." https://www.swift.org/migration/documentation/swift-6-concurrency-migration-guide/commonproblems/
[^swift6-apple]: Apple Developer Documentation, "Adopting Swift 6." https://developer.apple.com/documentation/Swift/AdoptingSwift6
[^model-data]: Apple Developer Documentation, "Model data." https://developer.apple.com/documentation/swiftui/model-data
[^managing-model-data]: Apple Developer Documentation, "Managing model data in your app." https://developer.apple.com/documentation/swiftui/managing-model-data-in-your-app
[^observable-migration]: Apple Developer Documentation, "Migrating from the ObservableObject protocol to the Observable macro." https://developer.apple.com/documentation/swiftui/migrating-from-the-observable-object-protocol-to-the-observable-macro
[^nstextview]: Apple Developer Documentation, "NSTextView." https://developer.apple.com/documentation/appkit/nstextview
[^textkit]: Apple Developer Documentation, "TextKit." https://developer.apple.com/documentation/appkit/textkit
[^documentgroup]: Apple Developer Documentation, "DocumentGroup." https://developer.apple.com/documentation/swiftui/documentgroup
[^document-sample]: Apple Developer Documentation, "Building a document-based app with SwiftUI." https://developer.apple.com/documentation/swiftui/building-a-document-based-app-with-swiftui
[^swiftui-performance]: Apple Developer Documentation, "Performance analysis." https://developer.apple.com/documentation/swiftui/performance-analysis
[^rendering-efficiency]: Apple Developer Documentation, "Improving your app's rendering efficiency." https://developer.apple.com/documentation/xcode/improving-your-app-s-rendering-efficiency/
[^swift-testing]: Apple Developer Documentation, "Swift Testing." https://developer.apple.com/documentation/testing/
[^swift-testing-xcode]: Apple Developer, "Swift Testing." https://developer.apple.com/xcode/swift-testing/
[^swiftpm-resolve]: Swift Package Manager Documentation, "Resolving and updating dependencies." https://docs.swift.org/swiftpm/documentation/packagemanagerdocs/resolvingpackageversions/
[^swiftpm-package-resolve]: Swift Package Manager Documentation, "swift package resolve." https://docs.swift.org/swiftpm/documentation/packagemanagerdocs/packageresolve/
