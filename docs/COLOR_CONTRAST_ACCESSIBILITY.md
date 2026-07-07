# Color contrast accessibility

Stable color-contrast policy for this repo. This summary propagates cleanly
across repos; detailed tooling and workflows live in the
color-accessibility-expert skill, the single source of truth for operational
detail.

## Target contrast policy

Target a **5.5:1** house contrast ratio for all foreground/background text
pairs. This exceeds WCAG AA's 4.5:1 minimum for normal text and stops short of
AAA.

| WCAG level | Minimum ratio (normal text) |
| --- | --- |
| AA | 4.5:1 |
| House target | 5.5:1 |
| AAA | 7:1 |

The maximum possible contrast ratio is 21:1 (black `#000000` on white
`#ffffff`).

## What contrast ratio is

**Formula:** `(L1 + 0.05) / (L2 + 0.05)`, where L1 is the lighter relative
luminance and L2 is the darker.

**Relative luminance:** `L = 0.2126*R + 0.7152*G + 0.0722*B`, where R, G, B are
linearized sRGB channels. Gamma-correct each 8-bit channel value v: when
`v/255 <= 0.04045` use `v/255 / 12.92`, otherwise use
`((v/255 + 0.055) / 1.055) ^ 2.4`.

## Online checkers

- WebAIM Contrast Checker -- interactive check for any foreground/background
  color pair.
- ACART Contrast Checker -- alternative checker with a visual preview.

## Where the details live

- Repo-specific audited palettes: see this repo's `docs/PALETTE_CONTRAST_AUDIT.md`
  when present.
- Tooling and how-to workflows (CLI usage, backward-solve method, bookmarklet
  and API permalink checks, darken/brighten/normalize fixes, and audit-file
  generation): see the color-accessibility-expert skill, the single source of
  truth for operational detail.
