export type SankeyNode = { id: string; label: string }
export type SankeyLink = { source: string; target: string; value: number }

function colorForStatus(id: string) {
  const status = id.replace(/^status-/, '')
  if (['sale', 'qualified'].includes(status)) return '#3e8f78'
  if (['refund', 'invalid'].includes(status)) return '#a3565e'
  return '#74849b'
}

export function Sankey({ total, nodes, links }: { total: number; nodes: SankeyNode[]; links: SankeyLink[] }) {
  const width = 1000
  const top = 30
  const gap = 22
  const minNodeHeight = 10
  const height = Math.max(360, links.length * 72)
  const targetStackHeight = links.reduce((sum, link) => sum + Math.max(link.value, minNodeHeight), 0) + gap * Math.max(links.length - 1, 0)
  const scale = Math.min(1.8, Math.max(0, (height - top * 2 - gap * Math.max(links.length - 1, 0)) / Math.max(total, 1)))
  const sourceHeight = Math.max(total * scale, minNodeHeight)
  const sourceY = (height - sourceHeight) / 2
  let targetY = Math.max(top, (height - targetStackHeight * scale) / 2)
  let sourceOffset = sourceY

  const layouts = links.map((link) => {
    const thickness = Math.max(link.value * scale, minNodeHeight)
    const layout = { link, thickness, sourceY: sourceOffset + thickness / 2, targetY: targetY + thickness / 2 }
    sourceOffset += thickness
    targetY += thickness + gap
    return layout
  })

  const labelFor = (id: string) => nodes.find((node) => node.id === id)?.label ?? id

  return <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-base font-semibold">Destino dos leads</h2><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Do recebimento até o status final informado pelo webhook.</p></div><span className="text-xs text-slate-500 dark:text-slate-400">Dados atuais dos leads</span></div>
    {links.length === 0 ? <p className="py-12 text-center text-sm text-slate-500">Ainda não há leads recebidos.</p> : <div className="overflow-x-auto"><svg className="min-w-[920px]" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Fluxo de leads recebidos para seus status finais">
      {layouts.map(({ link, thickness, sourceY: flowSourceY, targetY: flowTargetY }) => <path key={link.target} d={`M 250 ${flowSourceY} C 410 ${flowSourceY}, 560 ${flowTargetY}, 760 ${flowTargetY}`} fill="none" stroke={colorForStatus(link.target)} strokeOpacity=".9" strokeWidth={thickness} />)}
      <g><title>Leads recebidos</title><rect x="240" y={sourceY} width="12" height={sourceHeight} rx="2" fill="#4c9de0" /><text x="222" y={sourceY + sourceHeight / 2 + 6} textAnchor="end" fill="#d9e1ef" fontSize="16" fontWeight="700">LEADS RECEBIDOS · {total.toLocaleString('pt-BR')}</text></g>
      {layouts.map(({ link, thickness, targetY: flowTargetY }) => <g key={`${link.target}-label`}><title>{link.value.toLocaleString('pt-BR')} leads em {labelFor(link.target)}</title><rect x="752" y={flowTargetY - thickness / 2} width="12" height={thickness} rx="2" fill={colorForStatus(link.target)} /><text x="778" y={flowTargetY - 2} fill="#d9e1ef" fontSize="16" fontWeight="700">{labelFor(link.target).toUpperCase()}</text><text x="778" y={flowTargetY + 18} fill="#94a3b8" fontSize="13">{link.value.toLocaleString('pt-BR')} leads</text></g>)}
    </svg></div>}
  </section>
}
