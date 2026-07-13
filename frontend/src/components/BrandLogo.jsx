import { useState } from 'react'
import { cn } from '../lib/utils'

/**
 * The bank's wordmark.
 *
 * Loaded as an asset, never hand-drawn. The HDFC Bank logo is a registered trademark: an SVG
 * approximation would be legally awkward and would look subtly wrong — wrong red, wrong kerning —
 * next to the real thing on a slide.
 *
 * Drop the official file in `frontend/public/brand/` as ANY of:
 *   hdfc-logo.svg | .png | .jpg     full wordmark  (expanded sidebar)
 *   hdfc-mark.svg | .png | .jpg     square mark    (collapsed rail, optional)
 *
 * The component tries each extension in turn and falls back to a neutral monogram if none exist,
 * so a missing file degrades quietly instead of leaving a broken-image icon in the header.
 */
const EXTS = ['svg', 'png', 'jpg', 'jpeg', 'webp']

function Asset({ name, className, onExhausted }) {
  const [i, setI] = useState(0)
  if (i >= EXTS.length) {
    onExhausted?.()
    return null
  }
  return (
    <img
      src={`/brand/${name}.${EXTS[i]}`}
      alt="HDFC Bank"
      className={className}
      onError={() => setI(i + 1)}
    />
  )
}

export default function BrandLogo({ collapsed = false }) {
  const [noFull, setNoFull] = useState(false)
  const [noMark, setNoMark] = useState(false)

  if (collapsed) {
    if (noMark) return <Fallback compact />
    return (
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white p-1 shadow-sm ring-1 ring-line/60">
        <Asset name="hdfc-mark" className="h-full w-full object-contain"
               onExhausted={() => setNoMark(true)} />
      </div>
    )
  }

  if (noFull) return <Fallback />

  // Stacked, not side by side. The sidebar is 248px: a 130px logo plate plus a text block leaves
  // the label ~70px, which truncates to "Agentic S…". Stacking gives the wordmark its full width
  // and the label a whole line — nothing is cropped, and the logo is bigger for it.
  return (
    <div className="flex min-w-0 flex-col gap-1">
      {/* The logo is designed for a white field. Recolouring or reversing a trademark is normally a
          brand-guideline violation; giving it the background it was made for is not — so it sits on
          a white plate in both light and dark themes. */}
      <div className="flex h-9 w-fit items-center rounded-lg bg-white px-2.5 shadow-sm ring-1 ring-line/60">
        <Asset name="hdfc-logo" className="h-[22px] w-auto max-w-[172px] object-contain"
               onExhausted={() => setNoFull(true)} />
      </div>
      <div className="whitespace-nowrap text-[10.5px] font-medium tracking-wide text-muted">
        Agentic SDLC Platform
      </div>
    </div>
  )
}

/** No asset supplied — a neutral monogram, not a guess at the trademark. */
const Fallback = ({ compact }) => (
  <div className={cn('flex min-w-0 items-center gap-2.5')}>
    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand shadow-sm">
      <span className="text-[15px] font-bold text-brand-fg">H</span>
    </div>
    {!compact && (
      <div className="min-w-0">
        <div className="truncate text-[13px] font-semibold leading-tight">HDFC Bank</div>
        <div className="text-[10.5px] leading-tight text-muted">Agentic SDLC Platform</div>
      </div>
    )}
  </div>
)
