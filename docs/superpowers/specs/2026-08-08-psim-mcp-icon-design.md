# PSIM-MCP README Icon Design

## Goal

Replace the dense cinematic README hero with a compact brand icon that remains recognizable at small GitHub README sizes.

## Visual direction

- Square app-icon composition with a dark navy rounded-square field.
- One centered, flat geometric symbol combining circuit nodes, a sine waveform, and an MCP-style connection motif.
- Electric blue and cyan as the only accent colors, with crisp high contrast.
- Strong silhouette, balanced negative space, generous outer padding, and legibility at 180 px.
- No text inside the image. The native Markdown `# PSIM-MCP` heading remains the wordmark.

## Exclusions

- No 3D rendering, chrome, photorealism, neon bloom, gradients, dashboard panels, charts, optimization surfaces, circuit schematics, decorative particles, logos, trademarks, or watermarks.
- No small details that disappear when the icon is reduced.

## Asset and README integration

- Generate a new project asset as `assets/psim-mcp-icon.png` using the built-in image generator.
- Preserve the existing hero until the new icon passes visual review, then remove the superseded file.
- Replace the current hero reference in all four README files with the same centered HTML image block:

```html
<p align="center">
  <img src="assets/psim-mcp-icon.png" alt="PSIM-MCP icon" width="180">
</p>
```

## Acceptance criteria

- The final image is square, has a single centered icon, and contains no unintended readable text.
- The icon is visually clear at original size and at an effective 180 px README display size.
- All four README files reference the same tracked asset and retain their existing ten-section technical structure.
- The old hero asset is no longer referenced or retained after replacement.
- Markdown structure checks, `git diff --check`, and the complete test suite pass before merge.

## Git integration

- Keep unrelated local changes out of the icon commit.
- Use the repository's existing Conventional Commit style.
- Commit the approved implementation on `refactor/simplify-leftovers`, merge it locally into `main`, rerun the complete test suite, and do not push unless separately requested.
