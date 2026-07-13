import { AlertTriangle, ExternalLink, Image as ImageIcon, Layers } from 'lucide-react'
import { Badge, Card, CardBody, CardHeader, CardTitle, Empty } from './ui'

/**
 * The screens Agent 3 generated.
 *
 * Rendered as a gallery, not as rows in a markdown table, because a wireframe that a sponsor cannot
 * SEE is not a wireframe — it is a URL. The whole reason for moving off Figma was that a link behind
 * a paid seat never gets opened; putting the picture in front of the person reading the BRD is the
 * entire point.
 *
 * Each screen carries the requirement it satisfies. A screen that traces to no requirement should
 * not exist, and if one shows up here with an empty trace, that is worth noticing.
 */
export default function Wireframes({ payload }) {
  const wf = payload?.wireframes || payload?.figma
  const screens = wf?.screens || []

  if (!wf) {
    return <Empty icon={ImageIcon} title="No screens yet" hint="Agent 3 has not run for this project." />
  }

  if (wf.error || wf.status === 'SCREENS_PENDING') {
    return (
      <Card className="border-warning/40">
        <CardBody className="flex gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-warning" />
          <div>
            <p className="text-[13px] font-semibold text-warning">
              Screens pending — the spec was produced, the pictures were not
            </p>
            <p className="mt-1 text-[12px] text-muted leading-relaxed">
              {wf.error || 'The wireframe provider was unavailable.'}
            </p>
            <p className="mt-2 text-[12px] text-muted leading-relaxed">
              The run completed anyway, and the BRD is unaffected: Agent 4 consumes the structured
              screen spec, never the rendered image. A wireframe generator is never allowed to fail a
              requirements run — so the screens can be regenerated later without redoing anything.
            </p>
          </div>
        </CardBody>
      </Card>
    )
  }

  if (wf.mock) {
    return (
      <Card className="border-warning/40">
        <CardBody className="flex gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-warning" />
          <div>
            <p className="text-[13px] font-semibold text-warning">These are mock screens</p>
            <p className="mt-1 text-[12px] text-muted leading-relaxed">
              Stitch was not called — the URLs point at <code className="font-mono">example.invalid</code> and
              will 404 on purpose. Set <code className="font-mono">STITCH_API_KEY</code> and{' '}
              <code className="font-mono">STITCH_MOCK=false</code>, then run again.
            </p>
            <p className="mt-2 text-[12px] text-muted">
              {screens.length} screen spec{screens.length === 1 ? '' : 's'} were still produced, and they
              are what Agent 4 actually consumes.
            </p>
          </div>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <Layers className="h-4 w-4 text-brand" />
        <CardTitle>Generated screens — {(wf.provider || 'stitch').replace(/^\w/, (c) => c.toUpperCase())}</CardTitle>
        <Badge tone="brand" className="ml-auto">{screens.length}</Badge>
        {wf.project_url && (
          <a href={wf.project_url} target="_blank" rel="noreferrer"
            className="flex items-center gap-1 text-[11.5px] font-semibold text-brand hover:underline">
            Open project <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </CardHeader>
      <CardBody className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {screens.map((s) => (
          <div key={s.screen_id || s.name} className="rounded-xl border border-line bg-bg/40 overflow-hidden">
            {s.screenshot_url ? (
              <a href={s.url || s.screenshot_url} target="_blank" rel="noreferrer">
                <img
                  src={s.screenshot_url}
                  alt={s.name}
                  loading="lazy"
                  className="h-56 w-full bg-white object-contain transition-transform hover:scale-[1.02]"
                />
              </a>
            ) : (
              <div className="grid h-56 w-full place-items-center bg-bg">
                <span className="text-[11.5px] text-muted">No preview returned</span>
              </div>
            )}
            <div className="p-3">
              <p className="text-[12.5px] font-medium leading-snug">{s.name}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1">
                {(s.requirement_ids || []).length > 0 ? (
                  s.requirement_ids.map((id) => <Badge key={id} tone="brand">{id}</Badge>)
                ) : (
                  <Badge tone="warning">traces to nothing</Badge>
                )}
              </div>
              {s.html_url && (
                <a href={s.html_url} target="_blank" rel="noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-brand hover:underline">
                  HTML <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  )
}
