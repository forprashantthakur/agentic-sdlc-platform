# Brand assets

Drop the **official** HDFC Bank logo files here. They are not committed to this repo — the mark is
a registered trademark, and a hand-drawn approximation would be both legally awkward and visibly
wrong next to the real one.

| File | Used where | Recommended |
|---|---|---|
| `hdfc-logo.svg` | Expanded sidebar (full wordmark) | SVG. PNG works — use ≥2x (about 256×64) or it will look soft on a Retina display. |
| `hdfc-mark.svg` | Collapsed sidebar (square mark only) | Optional. Without it, the collapsed rail falls back to a monogram tile. |

If neither file is present the header falls back to a neutral "H" tile — the app does not break.

**Using a PNG or JPG instead of SVG:** either keep the same base filename with the new extension and
update the two `src` paths in `src/components/BrandLogo.jsx`, or simply rename your file to
`hdfc-logo.svg`… no — do not do that. Update the path; a mislabelled file will not render.

The logo renders on a white plate in both light and dark themes. That is deliberate: the mark is
designed for a white field, and recolouring or reversing a trademark is normally a brand-guideline
violation. Giving it the background it was designed for is not.
