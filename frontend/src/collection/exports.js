import { COLORS } from './analysis.js'

export const xml = value => String(value ?? '').replace(/[<>&"']/g, char => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[char])
export function download(content, filename, type = 'application/json') {
    const blob = content instanceof Blob ? content : new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function graphML(graph) {
    const keys = [['label', 'node'], ['uniprot', 'node'], ['species', 'node'], ['input', 'node'], ['unresolved', 'node'], ['databases', 'edge'], ['evidence', 'edge']]
    return `<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/xmlns">${keys.map(([key, scope]) => `<key id="${key}" for="${scope}" attr.name="${key}" attr.type="string"/>`).join('')}<graph id="KlinkPPI" edgedefault="undirected">${graph.nodes.map(n => `<node id="${xml(n.id)}"><data key="label">${xml(n.gene)}</data><data key="uniprot">${n.unresolved ? '' : xml(n.id)}</data><data key="species">${xml(n.species)}</data><data key="input">${n.input}</data><data key="unresolved">${n.unresolved}</data></node>`).join('')}${graph.edges.map(e => `<edge id="${e.id}" source="${xml(e.source)}" target="${xml(e.target)}"><data key="databases">${xml(e.databases.join('|'))}</data><data key="evidence">${xml(JSON.stringify(e.evidence))}</data></edge>`).join('')}</graph></graphml>`
}

export function sif(graph) {
    const linked = new Set(graph.edges.flatMap(e => [e.source, e.target]))
    return [...graph.edges.map(e => `${e.source}\tinteracts_with\t${e.target}`), ...graph.nodes.filter(n => !linked.has(n.id)).map(n => n.id)].join('\n') + '\n'
}

export function cx(graph, job) {
    const ids = new Map(graph.nodes.map((n, i) => [n.id, i]))
    const aspects = {
        nodes: graph.nodes.map(n => ({ '@id': ids.get(n.id), n: n.gene, r: n.unresolved ? n.gene : `uniprot:${n.id}` })),
        edges: graph.edges.map((e, i) => ({ '@id': i, s: ids.get(e.source), t: ids.get(e.target), i: 'interacts_with' })),
        nodeAttributes: graph.nodes.flatMap(n => ['species', 'tax_id', 'input', 'unresolved'].map(key => ({ po: ids.get(n.id), n: key, v: String(n[key]) }))),
        edgeAttributes: graph.edges.flatMap((e, i) => [
            { po: i, n: 'databases', v: e.databases, d: 'list_of_string' },
            { po: i, n: 'evidence', v: JSON.stringify(e.evidence) },
        ]),
        networkAttributes: [{ n: 'name', v: `KlinkPPI ${job.species} ${job.mode}` }, { n: 'warnings', v: JSON.stringify(job.warnings) }],
    }
    const metadata = Object.entries(aspects).map(([name, value]) => ({ name, version: '1.0', elementCount: value.length, consistencyGroup: 1 }))
    return [{ numberVerification: [{ longNumber: 281474976710655 }] }, { metaData: metadata },
        ...Object.entries(aspects).map(([key, value]) => ({ [key]: value })), { status: [{ error: '', success: true }] }]
}

export function networkSVG(cy, graph, { colors, widths }) {
    const bb = cy.elements().boundingBox(), pad = 50
    const edgeParts = graph.edges.map(e => {
        const a = cy.getElementById(e.source).position(), b = cy.getElementById(e.target).position()
        const color = e.expanded || !colors ? '#94a3b8' : e.databases.length > 1 ? '#334155' : COLORS[e.databases[0]]
        const width = widths ? cy.getElementById(e.id).data('width') : 1.5
        return `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${color}" stroke-width="${width}" opacity="0.65"/>`
    }).join('')
    const nodes = graph.nodes.map(n => {
        const p = cy.getElementById(n.id).position()
        return `<g><title>${xml(`${n.gene} · ${n.unresolved ? 'Unresolved' : n.id} · ${n.species}`)}</title><circle cx="${p.x}" cy="${p.y}" r="${n.input ? 12 : 8}" fill="${n.unresolved ? '#fbbf24' : n.input ? '#0f766e' : '#cbd5e1'}" stroke="#ffffff" stroke-width="2"/><text x="${p.x}" y="${p.y + 26}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#334155">${xml(n.gene)}</text></g>`
    }).join('')
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${bb.x1 - pad} ${bb.y1 - pad} ${bb.w + 2 * pad} ${bb.h + 2 * pad}"><rect x="${bb.x1 - pad}" y="${bb.y1 - pad}" width="${bb.w + 2 * pad}" height="${bb.h + 2 * pad}" fill="white"/>${edgeParts}${nodes}</svg>`
}

export async function analysisPDF(job, graph, stats, filters, cy) {
    const { jsPDF } = await import('jspdf')
    const doc = new jsPDF()
    let y = 18
    const line = (text, size = 10) => {
        doc.setFontSize(size)
        const lines = doc.splitTextToSize(String(text), 174)
        for (const value of lines) {
            if (y > 278) { doc.addPage(); y = 18 }
            doc.text(value, 18, y)
            y += size * 0.45 + 2
        }
    }
    line('KlinkPPI collection analysis', 18)
    line(`${job.species} | Taxonomy ${job.tax_id} | ${job.mode} network`)
    line(`Generated ${new Date().toISOString()}`)
    const resolved = Object.values(job.selections).filter(Boolean).length
    line(`Input IDs: ${job.tokens.length}; resolved/selected: ${resolved}; unresolved/skipped: ${job.tokens.length - resolved}`)
    line(`Filtered network: ${stats.nodes} nodes; ${stats.edges} edges; ${stats.components.length} components; mean local clustering ${stats.clustering.toFixed(4)}`)
    line(`Filters: ${JSON.stringify(filters)}`)
    line('Scores remain on their original database scales. Pair overlap does not imply direct binding. Statistics treat the network as an undirected simple graph, including isolated input nodes.')
    for (const warning of job.warnings) line(`Warning: ${warning}`)
    if (cy && graph.nodes.length) {
        if (y > 165) { doc.addPage(); y = 18 }
        const png = cy.png({ full: true, bg: '#ffffff', maxWidth: 1400, maxHeight: 800 })
        const props = doc.getImageProperties(png)
        const height = Math.min(100, 174 * props.height / props.width)
        doc.addImage(png, 'PNG', 18, y, Math.min(174, height * props.width / props.height), height)
        y += height + 8
    }
    line('Database evidence', 13)
    stats.byDatabase.forEach(row => line(`${row.database}: ${row.edges} pairs; ${row.unique} unique; ${row.shared} shared`))
    line('Jaccard overlap', 13)
    stats.jaccard.forEach(row => line(`${row.a} / ${row.b}: ${row.value == null ? 'N/A (empty union)' : row.value.toFixed(4)}; shared ${row.intersection}, union ${row.union}`))
    line('Hubs and degree', 13)
    stats.hubs.forEach(n => line(`${n.gene} (${n.id}): degree ${n.degree}; clustering ${n.clustering.toFixed(4)}`))
    line('Component sizes', 13)
    line(stats.components.join(', ') || 'No nodes')
    line('Evidence score distributions', 13)
    stats.scores.forEach(s => line(`${s.database} / ${s.name}: n=${s.count}; min=${s.min}; median=${s.median}; mean=${s.mean.toFixed(4)}; max=${s.max}; 8-bin counts=${s.bins.join(',')}`))
    line('Shared interactors', 13)
    stats.sharedInteractors.forEach(n => line(`${n.gene} (${n.id}): ${n.databases.join(', ')}; degree ${n.degree}`))
    line('Database-only interactors', 13)
    Object.entries(stats.databaseOnlyInteractors).forEach(([db, nodes]) => line(`${db}: ${nodes.map(n => `${n.gene} (${n.id})`).join(', ') || 'None'}`))
    line('Input resolution', 13)
    job.resolution.forEach(row => line(`${row.input}: ${job.selections[row.input] || 'unresolved/skipped'}; candidates=${row.candidates.map(c => c.id).join(', ') || 'none'}${row.error ? '; ' + row.error : ''}`))
    doc.save('klinkppi-analysis-report.pdf')
}
