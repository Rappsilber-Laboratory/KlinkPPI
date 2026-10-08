import { useEffect, useMemo, useRef, useState } from 'react'
import { COLORS, LABELS, filterGraph } from '../collection/analysis'
import { analysisPDF, cx, download, graphML, sif } from '../collection/exports'
import CollectionNetworkCanvas from './CollectionNetworkCanvas'

export default function CollectionResults({ job }) {
    const [filters, setFilters] = useState({ databases: job.databases, type: 'all', method: '', scoreDatabase: '', minScore: '', minPublications: 0 })
    const [colors, setColors] = useState(true)
    const [widthMode, setWidthMode] = useState('consensus')
    const [labels, setLabels] = useState(true)
    const [nodeScale, setNodeScale] = useState(1)
    const [detail, setDetail] = useState(null)
    const [calculation, setCalculation] = useState(null)
    const [exportError, setExportError] = useState('')
    const [exportBusy, setExportBusy] = useState(false)
    const [search, setSearch] = useState('')
    const [degreePage, setDegreePage] = useState(0)
    const networkRef = useRef(null)
    const graph = useMemo(() => filterGraph(job.graph, filters), [job.graph, filters])
    const stats = calculation?.graph === graph ? calculation.stats : null
    const calculationError = calculation?.graph === graph ? calculation.error : null
    const scoreDBs = useMemo(() => [...new Set(job.graph.edges.flatMap(e => e.evidence.filter(ev => ev.score != null).map(ev => ev.database)))], [job.graph])
    const update = (key, value) => setFilters(current => ({ ...current, [key]: value }))

    useEffect(() => {
        const worker = new Worker(new URL('../collection/statistics.worker.js', import.meta.url), { type: 'module' })
        worker.onmessage = ({ data }) => setCalculation({ graph, ...data })
        worker.onerror = () => setCalculation({ graph, error: 'Statistics could not be calculated.' })
        worker.postMessage({ graph, databases: job.databases })
        return () => worker.terminate()
    }, [graph, job.databases])

    const exportGraph = async format => {
        setExportError('')
        setExportBusy(true)
        try {
            if (format === 'json') download(JSON.stringify({ ...graph, analysis: { species: job.species, tax_id: job.tax_id, mode: job.mode, filters, resolution: job.resolution, selections: job.selections, warnings: job.warnings }, statistics: stats }, null, 2), 'klinkppi-network.json')
            if (format === 'graphml') download(graphML(graph), 'klinkppi-network.graphml', 'application/xml')
            if (format === 'sif') download(sif(graph), 'klinkppi-network.sif', 'text/plain')
            if (format === 'cx') download(JSON.stringify(cx(graph, job), null, 2), 'klinkppi-network.cx')
            if (format === 'svg') download(networkRef.current.svg(), 'klinkppi-network.svg', 'image/svg+xml')
            if (format === 'png') download(await networkRef.current.png(), 'klinkppi-network.png')
            if (format === 'pdf') await analysisPDF(job, graph, stats, filters, { png: () => networkRef.current.pngDataURL() })
        } catch (error) { setExportError(`Export failed: ${error.message}`) }
        finally { setExportBusy(false) }
    }
    const focus = () => {
        const query = search.trim().toLowerCase()
        const matched = networkRef.current.focus(query)
        if (matched) setExportError('')
        else setExportError(`No visible node matches '${search}'.`)
    }
    const resolutionCount = Object.values(job.selections).filter(Boolean).length
    const visibleDetail = detail && { ...detail, data: (detail.kind === 'node' ? graph.nodes : graph.edges).find(item => item.id === detail.data.id) }
    const shownDetail = visibleDetail?.data ? visibleDetail : null
    const page = Math.min(degreePage, Math.max(0, Math.ceil((stats?.degrees.length || 0) / 100) - 1))
    return <>
        {job.warnings.length > 0 && <div className="collection-card collection-warning" role="status"><h3>Coverage notes</h3><ul>{job.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
        <div className="collection-card">
            <div className="collection-job-heading"><div><span className="collection-eyebrow">EVIDENCE EXPLORER</span><h2>Your interaction network</h2></div><button onClick={() => exportGraph('pdf')} disabled={!stats || exportBusy} className="collection-primary">Download analysis PDF</button></div>
            <div className="collection-metrics">{[[job.tokens.length, 'Input IDs'], [resolutionCount, 'Resolved / selected'], [job.tokens.length - resolutionCount, 'Unresolved / skipped'], [graph.nodes.length, 'Visible nodes'], [graph.edges.length, 'Visible edges']].map(([value, label]) => <div key={label}><strong>{value.toLocaleString()}</strong><span>{label}</span></div>)}</div>
            <div className="network-workspace">
                <aside className="network-controls">
                    <fieldset><legend>Source databases</legend>{job.databases.map(db => <label className="source-toggle" key={db}><input type="checkbox" checked={filters.databases.includes(db)} onChange={e => update('databases', e.target.checked ? [...filters.databases, db] : filters.databases.filter(value => value !== db))} /><span className="source-dot" style={{ background: COLORS[db] }} />{LABELS[db] || db}</label>)}</fieldset>
                    <label>Evidence category<select value={filters.type} onChange={e => update('type', e.target.value)}><option value="all">All categories</option><option value="direct">Direct / physical</option><option value="functional">Functional / co-membership</option><option value="predicted">Predicted</option></select></label>
                    <label>Minimum known publications<input type="number" min="0" step="1" value={filters.minPublications} onChange={e => update('minPublications', Math.max(0, Number(e.target.value)))} /></label>
                    <label>Experimental method<input placeholder="e.g. two hybrid" value={filters.method} onChange={e => update('method', e.target.value)} /></label>
                    <label>Score threshold source<select value={filters.scoreDatabase} onChange={e => { update('scoreDatabase', e.target.value); update('minScore', '') }}><option value="">No score threshold</option>{scoreDBs.map(db => <option key={db}>{db}</option>)}</select></label>
                    {filters.scoreDatabase && <label>Minimum raw source score<input type="number" step="any" value={filters.minScore} onChange={e => update('minScore', e.target.value)} placeholder="No minimum" /></label>}
                    <p className="collection-note">A score threshold removes evidence only from that source. Other selected sources can still support the pair. Missing publication or method data are unknown.</p>
                    <details><summary>Appearance</summary><label className="source-toggle"><input type="checkbox" checked={colors} onChange={e => setColors(e.target.checked)} />Database edge colors</label><label className="source-toggle"><input type="checkbox" checked={labels} onChange={e => setLabels(e.target.checked)} />Gene labels</label><label>Node size <output>{Math.round(nodeScale * 100)}%</output><input type="range" min="0.5" max="2.5" step="0.1" value={nodeScale} onChange={e => setNodeScale(Number(e.target.value))} /></label><label>Edge width<select value={widthMode} onChange={e => setWidthMode(e.target.value)}><option value="consensus">Database consensus count</option><option value="score">Relative source scores</option><option value="off">Uniform width</option></select></label><p className="collection-note">Drag any node to reposition it. Click an edge to open its evidence; moving near an edge does not select it.</p></details>
                </aside>
                <div className="network-main"><div className="network-toolbar"><div><input aria-label="Find network node" placeholder="Find gene / UniProt…" value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') focus() }} /><button onClick={focus} disabled={!graph.nodes.length}>Find</button></div><div><button onClick={() => networkRef.current.fit()}>Fit</button><button onClick={() => networkRef.current.rearrange()}>Rearrange</button><button onClick={e => { const separated = networkRef.current.separate(); e.currentTarget.textContent = separated ? 'Compact communities' : 'Separate communities' }}>Separate communities</button></div></div>
                    <div className="network-detail" aria-live="polite"><div className="network-detail-heading"><span>{shownDetail?.kind === 'edge' ? 'INTERACTION EVIDENCE' : 'PROTEIN INSPECTOR'}</span><strong>{shownDetail ? shownDetail.kind === 'node' ? shownDetail.data.gene : `${shownDetail.data.source} ↔ ${shownDetail.data.target}` : 'Select a protein or interaction'}</strong></div><div className="network-detail-content">{!shownDetail ? <p>Click a node or edge to inspect its details.</p> : shownDetail.kind === 'node' ? <><p>{shownDetail.data.unresolved ? 'Unresolved / skipped input — no connections' : `UniProt: ${shownDetail.data.id}`} · {shownDetail.data.species} · Taxonomy {shownDetail.data.tax_id}</p>{stats && <p>Degree: {stats.degrees.find(n => n.id === shownDetail.data.id)?.degree ?? 0}</p>}</> : <><div className="evidence-chips">{shownDetail.data.databases.map(db => <span key={db} style={{ borderColor: COLORS[db], color: COLORS[db] }}>{LABELS[db] || db}</span>)}</div><div className="collection-table-wrap"><table><thead><tr><th>Source</th><th>Type</th><th>Score</th><th>Publications</th><th>Methods / direction</th></tr></thead><tbody>{shownDetail.data.evidence.map((ev, i) => <tr key={i}><td>{/^https?:\/\//.test(ev.link) ? <a href={ev.link} target="_blank" rel="noreferrer">{ev.database}</a> : ev.database}</td><td>{ev.type}<small>{ev.interaction_type}</small></td><td>{ev.score == null ? 'Unknown' : Object.entries(ev.scores || { [ev.score_name]: ev.score }).map(([key, value]) => `${key}: ${value}`).join('; ')}</td><td>{ev.publications.join(', ') || 'Unknown'}</td><td>{ev.methods.join(', ') || 'Unknown'}{ev.directed && <small>{ev.regulator} → {ev.target} · {ev.effect}</small>}</td></tr>)}</tbody></table></div></>}</div></div>
                    <div className="network-meta"><span>{graph.nodes.length.toLocaleString()} nodes</span><span>{graph.edges.length.toLocaleString()} edges</span><span>{new Set(graph.edges.flatMap(e => e.databases)).size} sources</span><span>{stats?.components.length ?? '—'} groups</span></div>
                    <div className="network-canvas"><CollectionNetworkCanvas ref={networkRef} graph={graph} colors={colors} widthMode={widthMode} labels={labels} nodeScale={nodeScale} onPick={setDetail} /></div>
                    {!graph.edges.length && <p className="network-empty">No interactions match this mode and the current filters. Input proteins remain visible as isolated nodes.</p>}
                    <div className="network-legend"><span><i style={{ background: '#ff775f' }} />Input protein</span><span><i style={{ background: '#66e3b4' }} />First neighbor</span><span><i style={{ background: '#d9ff43' }} />Unresolved / skipped</span><span>Muted edges: first-neighbor connections · Acid edges: shared sources</span></div>
                    <p className="collection-note">Drag nodes, scroll to zoom, and hover or tap for evidence. Large networks use a circle layout to keep interaction responsive.</p>
                </div>
            </div>
            <div className="collection-actions"><span>Export filtered network:</span>{['svg', 'png', 'graphml', 'sif', 'cx', 'json'].map(format => <button key={format} onClick={() => exportGraph(format)} disabled={exportBusy || (['svg', 'png'].includes(format) && !graph.nodes.length)}>{format.toUpperCase()}</button>)}</div>
            {exportError && <p className="collection-error" role="alert">{exportError}</p>}
        </div>
        <div className="collection-card"><span className="collection-eyebrow">ANALYSIS REPORT</span><h2>Evidence, overlap and topology</h2><p className="collection-note">All statistics describe the filtered, undirected network. Isolated inputs count as components. Evidence categories follow source semantics; complex membership and functional associations do not establish direct binding.</p>
            {!stats ? <p role="status">{calculationError || 'Calculating statistics…'}</p> : <>
                <div className="collection-metrics"><div><strong>{stats.components.length}</strong><span>Connected components</span></div><div><strong>{stats.components[0] || 0}</strong><span>Largest component</span></div><div><strong>{stats.clustering.toFixed(3)}</strong><span>Mean local clustering</span></div><div><strong>{stats.degrees.filter(n => n.degree === 0).length}</strong><span>Isolated nodes</span></div></div>
                <div className="collection-grid"><div><h3>Pairs unique to a database vs shared</h3><div className="collection-table-wrap"><table><thead><tr><th>Database</th><th>All pairs</th><th>Unique</th><th>Shared</th></tr></thead><tbody>{stats.byDatabase.map(row => <tr key={row.database}><td>{LABELS[row.database] || row.database}</td><td>{row.edges}</td><td>{row.unique}</td><td>{row.shared}</td></tr>)}</tbody></table></div></div><div><h3>Hubs</h3><table><thead><tr><th>Gene / UniProt</th><th>Degree</th><th>Clustering</th></tr></thead><tbody>{stats.hubs.map(n => <tr key={n.id}><td>{n.gene}<small>{n.id}</small></td><td>{n.degree}</td><td>{n.clustering.toFixed(3)}</td></tr>)}</tbody></table>{!stats.hubs.length && <p>No connected nodes.</p>}</div></div>
                <details><summary>Pairwise Jaccard overlap</summary><p className="collection-note">Shared pairs / union of pairs. N/A means neither database has pairs in this view.</p><div className="collection-table-wrap"><table><thead><tr><th>Database pair</th><th>Intersection</th><th>Union</th><th>Jaccard</th></tr></thead><tbody>{stats.jaccard.map(row => <tr key={`${row.a}:${row.b}`}><td>{row.a} / {row.b}</td><td>{row.intersection}</td><td>{row.union}</td><td>{row.value == null ? 'N/A' : row.value.toFixed(3)}</td></tr>)}</tbody></table></div></details>
                <h3>Evidence score distributions by database</h3><p className="collection-note">Raw source scales; eight equal-width bins per series. Counts describe retained evidence records.</p><div className="score-distributions">{stats.scores.map(s => <div className="score-series" key={`${s.database}:${s.name}`}><strong>{s.database}</strong><small>{s.name} · n={s.count}</small><div className="histogram" role="img" aria-label={`${s.database} ${s.name}: min ${s.min}, median ${s.median}, max ${s.max}; bins ${s.bins.join(', ')}`}>{s.bins.map((count, i) => <div key={i} title={`${count} evidence records`} style={{ height: `${Math.max(2, count / Math.max(...s.bins) * 100)}%`, background: COLORS[s.database] }} />)}</div><div className="histogram-range"><span>{s.min.toFixed(3)}</span><span>{s.max.toFixed(3)}</span></div><small>Median {s.median.toFixed(3)} · Mean {s.mean.toFixed(3)}</small></div>)}</div>{!stats.scores.length && <p>No reported numeric scores in this view.</p>}
                <div className="collection-grid"><div><h3>Top shared interactors</h3>{stats.sharedInteractors.length ? <ul>{stats.sharedInteractors.map(n => <li key={n.id}><strong>{n.gene}</strong> ({n.id}) · {n.databases.join(', ')} · degree {n.degree}</li>)}</ul> : <p>No shared interactors in this view.</p>}</div><div><h3>Database-only interactors</h3>{Object.entries(stats.databaseOnlyInteractors).map(([db, nodes]) => <p key={db}><strong>{LABELS[db] || db}: </strong>{nodes.map(n => `${n.gene} (${n.id})`).join(', ') || 'None'}</p>)}</div></div>
                <details><summary>Degree and clustering for all nodes</summary><div className="collection-table-wrap degree-table"><table><thead><tr><th>Gene</th><th>UniProt / input</th><th>Degree</th><th>Clustering</th></tr></thead><tbody>{stats.degrees.slice(page * 100, (page + 1) * 100).map(n => <tr key={n.id}><td>{n.gene}</td><td>{n.unresolved ? 'Unresolved' : n.id}</td><td>{n.degree}</td><td>{n.clustering.toFixed(3)}</td></tr>)}</tbody></table></div><div className="collection-actions"><button disabled={page === 0} onClick={() => setDegreePage(page - 1)}>Previous</button><span>Page {page + 1} of {Math.max(1, Math.ceil(stats.degrees.length / 100))}</span><button disabled={(page + 1) * 100 >= stats.degrees.length} onClick={() => setDegreePage(page + 1)}>Next</button></div></details>
            </>}
        </div>
    </>
}
