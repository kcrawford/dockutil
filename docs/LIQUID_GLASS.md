# Liquid Glass Guidance for macOS 26+ SwiftUI Apps

Liquid Glass should be treated as the default macOS 26 visual language, not as an optional decorative layer. The best way to get strong Liquid Glass adoption is to use standard SwiftUI and AppKit components first, then add custom glass only where the interface needs a deliberate control, navigation, or transient surface.

## 1. Use system components first

Apple's Liquid Glass guidance says standard SwiftUI, UIKit, and AppKit components such as controls and navigation elements adopt the new appearance and behavior automatically.[^liquid-glass] Apple's adoption guidance also says apps using standard framework components pick up the latest look and feel when built with the latest SDKs and run on the latest platforms.[^adopting-liquid-glass]

Prefer standard system UI for:

- Windows and scenes
- Toolbars
- Sidebars
- Split views
- Sheets
- Popovers
- Menus
- Search fields
- Buttons
- Toggles
- Pickers
- Sliders
- Segmented controls
- Inspectors
- Alerts

Good rule:

> Maximize Liquid Glass adoption by maximizing standard system UI.

## 2. Use Liquid Glass for controls and navigation

Apple describes Liquid Glass as a dynamic material that combines the optical qualities of glass with a sense of fluidity. It reflects and refracts its surroundings and helps bring focus to underlying content.[^liquid-glass][^meet-liquid-glass]

Use Liquid Glass most aggressively on:

- Toolbars
- Navigation controls
- Floating controls
- Inspectors
- Search and filter controls
- Popovers
- Sheets
- Menus
- Selection controls
- Mode controls
- Transient overlays

Use quieter, more stable surfaces for:

- Dense text
- Long-form documents
- Code editors
- Tables
- Scientific figures
- Charts
- Reading panes
- Data-heavy views
- Primary content canvases

Good rule:

> Controls can be glassy. Content should stay legible.

## 3. Keep content readable

Liquid Glass should clarify hierarchy without making the app harder to use. It should not turn the content layer into decoration.

Use Liquid Glass to express:

- Navigation
- Control grouping
- Mode changes
- Transient actions
- Selection state
- Tool availability
- Interface depth

Avoid using Liquid Glass as:

- A general background texture
- A replacement for layout hierarchy
- A styling pass over every surface
- A way to hide weak information architecture
- A treatment for dense reading or editing areas

Good rule:

> Build the hierarchy first. Let Liquid Glass express the hierarchy.

## 4. Separate content, control, and navigation layers

A good macOS 26 layout usually separates visual responsibility:

```text
window and scene structure
  sidebar / navigation / document tabs where appropriate

control layer
  toolbar, search, filters, view mode, inspectors, transient actions

content layer
  text, tables, editors, diagrams, media, scientific data, documents
```

Liquid Glass belongs mostly in the control layer and selected navigation surfaces. The content layer should remain calm, readable, and predictable.

## 5. Use custom Liquid Glass deliberately

Apple documents SwiftUI APIs for applying Liquid Glass to custom interface elements and animations. Standard components already use Liquid Glass, while custom components can adopt glass effects to move, combine, and morph with unique transitions.[^custom-liquid-glass]

Custom Liquid Glass is appropriate for:

- Custom tool palettes
- Floating control groups
- Transient overlays
- Small navigation affordances
- Mode selectors
- Inspector controls
- Selection controls
- Custom controls that need to feel system-native

Custom Liquid Glass is usually not appropriate for:

- Full-window backgrounds
- Large text regions
- Dense tables
- Code or prose editors
- Scientific data displays
- Decorative cards with no interaction role

Good rule:

> Custom glass should explain interaction. It should not merely announce style.

## 6. Preserve native macOS behavior

Liquid Glass should support native Mac behavior, not replace it.

A modern macOS app should still respect:

- Menu bar commands
- Keyboard shortcuts
- Focus rings
- Toolbar conventions
- Multi-window workflows
- Document behavior
- File drag and drop
- Undo and redo
- Resizable windows
- Accessibility settings
- Light mode and dark mode
- High contrast
- Reduced transparency
- Reduced motion

Apple's macOS design guidance emphasizes the Mac as a powerful, spacious, flexible platform where people often use several apps at once.[^designing-for-macos]

Good rule:

> Liquid Glass should make the app feel more native, not more custom.

## 7. Check accessibility early

Liquid Glass depends on translucency, depth, reflection, refraction, and motion. These can reduce usability if applied too broadly.

Check the interface in:

- Light mode
- Dark mode
- High contrast
- Increased contrast
- Reduced transparency
- Reduced motion
- VoiceOver
- Keyboard-only navigation
- Different window sizes
- Busy content backgrounds

If a glass surface harms readability, reduce the effect or move the effect to the control layer.

Good rule:

> Accessibility is part of the Liquid Glass design, not a cleanup pass.

## 8. Keep AppKit bridges visually owned

If an AppKit bridge owns a visible control surface, decide whether SwiftUI or AppKit owns the Liquid Glass styling. Do not split visual responsibility across both layers.

Good pattern:

```text
SwiftUI feature
  owns state and app structure

SwiftUI glass/control wrapper
  owns visual system integration

AppKit adapter
  owns platform-specific behavior
```

For advanced text editing, custom drawing, low-level window behavior, or responder-chain work, AppKit may still be the correct implementation layer. Keep that boundary narrow and deliberate.

## 9. Review custom UI against a simple test

Before adding custom Liquid Glass, ask:

1. Is this surface a control, navigation element, or transient interface layer?
2. Does glass clarify hierarchy or interaction?
3. Does the content remain readable behind it?
4. Does the effect behave well in light and dark mode?
5. Does the interface still work with reduced transparency and reduced motion?
6. Would a standard system component solve this better?

If the answer to the last question is yes, use the standard component.

## 10. Compact rule set

Use this as the short version:

- Use standard SwiftUI and AppKit components first.
- Let toolbars, sidebars, sheets, popovers, menus, and controls inherit Liquid Glass.
- Add custom glass only to controls, navigation, and transient overlays.
- Keep dense content stable and readable.
- Preserve native macOS behavior.
- Test accessibility modes early.
- Isolate visual ownership at AppKit boundaries.
- Treat glass as hierarchy, not decoration.

## References

[^liquid-glass]: Apple Developer Documentation, "Liquid Glass." https://developer.apple.com/documentation/technologyoverviews/liquid-glass
[^adopting-liquid-glass]: Apple Developer Documentation, "Adopting Liquid Glass." https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass
[^meet-liquid-glass]: Apple Developer, WWDC25, "Meet Liquid Glass." https://developer.apple.com/videos/play/wwdc2025/219/
[^custom-liquid-glass]: Apple Developer, WWDC25, "Explore custom Liquid Glass with SwiftUI." https://developer.apple.com/videos/play/wwdc2025/284/
[^designing-for-macos]: Apple Developer Documentation, "Designing for macOS." https://developer.apple.com/design/human-interface-guidelines/designing-for-macos
