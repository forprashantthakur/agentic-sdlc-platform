import { useState } from 'react'
import { cn } from '../lib/utils'

/**
 * The bank's wordmark.
 *
 * Deliberately loaded as an asset rather than hand-drawn in SVG. The HDFC Bank logo is a
 * registered trademark: an approximation would be legally awkward and would look subtly wrong
 * next to the real thing on a deck. Drop the official file in and it renders; leave it out and
 * this falls back to a neutral monogram rather than breaking the header.
 *
 *   frontend/public/brand/hdfc-logo.svg   full wordmark   (expanded sidebar)
 *   frontend/public/brand/hdfc-mark.svg   square mark     (collapsed sidebar) — optional
 *
 * The logo is dark-blue-on-white, so on the dark theme it sits on a white plate. Reversing a
 * trademark's colours is usually a brand-guideline violation; giving it the white field it was
 * designed for is not.
 */
export default function BrandLogo({ collapsed = false }) {
  const [full, setFull] = useState(true)
  const [mark, setMark] = useState(true)

  if (collapsed) {
    return mark ? (
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white p-1 shadow-sm ring-1 ring-line/60">
        <img
          src="/brand/hdfc-mark.svg"
          alt="HDFC Bank"
          className="h-full w-full object-contain"
          onError={() => setMark(false)}
        />
      </div>
    ) : (
      <Fallback compact />
    )
  }

  if (!full) return <Fallback />

  return (
    <div className="flex min-w-0 items-center gap-2.5">
      {/* The white plate is the logo's designed background — it keeps the mark legible in dark mode
          without recolouring a trademark. */}
      <div className="flex h-10 items-center rounded-lg bg-white px-2 shadow-sm ring-1 ring-line/60">
        <img
          src="/brand/hdfc-logo.svg"
          alt="HDFC Bank"
          className="h-6 w-auto max-w-[128px] object-contain"
          onError={() => setFull(false)}
        />
      </div>
      <div className="min-w-0 leading-tight">
        <div className="truncate text-[11px] font-semibold text-ink">Agentic SDLC</div>
        <div className="truncate text-[10px] text-muted">Platform</div>
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
