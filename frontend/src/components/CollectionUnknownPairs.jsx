import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { unknownInputPairs } from '../collection/analysis'

const API = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`
const PAGE_SIZE = 20

function SharedTerms({ result, source, target }) {
    return <div className="shared-go-result">
        <h3>Shared GO terms: {source.gene} ↔ {target.gene}</h3>
        <p className="collection-note">UniProt reports {result.source_term_count} GO terms for <a href={`https://www.uniprot.org/uniprotkb/${source.id}/entry`} target="_blank" rel="noreferrer">{source.id}</a> and {result.target_term_count} for <a href={`https://www.uniprot.org/uniprotkb/${target.id}/entry`} target="_blank" rel="noreferrer">{target.id}</a>. {result.shared_terms.length} exact GO IDs are shared. Ancestor terms are not inferred.</p>
        {!result.source_term_count || !result.target_term_count ? <p>At least one protein has no GO annotations reported by UniProt, so no shared terms can be shown.</p> : !result.shared_terms.length ? <p>No exact shared GO terms were found in these UniProt entries.</p> :
            <div className="collection-table-wrap"><table><thead><tr><th>GO term</th><th>Category</th><th>{source.gene} evidence</th><th>{target.gene} evidence</th></tr></thead><tbody>{result.shared_terms.map(term => <tr key={term.id}><td><a href={`https://amigo.geneontology.org/amigo/term/${term.id}`} target="_blank" rel="noreferrer">{term.id}</a><small>{term.name}</small></td><td>{term.category}</td><td>{term.source_evidence.join(', ') || 'Not reported'}</td><td>{term.target_evidence.join(', ') || 'Not reported'}</td></tr>)}</tbody></table></div>}
    </div>
}

export default function CollectionUnknownPairs({ job, graph }) {
    const pairs = useMemo(() => unknownInputPairs(graph), [graph])
    const [query, setQuery] = useState('')
    const [page, setPage] = useState(0)
    const [results, setResults] = useState({})
    const [open, setOpen] = useState({})
    const [pending, setPending] = useState(null)
    const controller = useRef(null)
    useEffect(() => () => controller.current?.abort(), [])
    const filtered = useMemo(() => {
        const value = query.trim().toLowerCase()
        return pairs.filter(pair => [pair.source.gene, pair.source.id, pair.target.gene, pair.target.id].some(label => label?.toLowerCase().includes(value)))
    }, [pairs, query])
    const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
    const currentPage = Math.min(page, pages - 1)
    const check = async pair => {
        if (controller.current) return
        const abort = new AbortController()
        controller.current = abort
        setPending(pair.key)
        setOpen(current => ({ ...current, [pair.key]: true }))
        try {
            const params = new URLSearchParams({ source: pair.source.id, target: pair.target.id })
            const response = await fetch(`${API}/collection/jobs/${encodeURIComponent(job.job_id)}/shared-go?${params}`, { signal: abort.signal })
            const data = await response.json()
            if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'GO lookup failed. Please retry.')
            setResults(current => ({ ...current, [pair.key]: { data } }))
        } catch (error) {
            if (error.name !== 'AbortError') setResults(current => ({ ...current, [pair.key]: { error: error.message } }))
        } finally {
            controller.current = null
            if (!abort.signal.aborted) setPending(null)
        }
    }

    return <section className="collection-card unknown-pairs" aria-label="Unknown interaction pairs">
        <span className="collection-eyebrow">INDUCED NETWORK · UNEXPLORED PAIRS</span>
        <h2>Pairs with no interaction found</h2>
        <p>{pairs.length.toLocaleString()} pairs among your resolved input proteins have no interaction evidence in this search. Check GO to explore their shared UniProt annotations.</p>
        <p className="collection-note">This list uses the full search results before display filters. Missing evidence does not mean the proteins cannot interact. Shared GO terms describe common annotations and do not establish a protein interaction.</p>
        {(graph.truncated || job.warnings?.length > 0) && <p className="collection-warning">Search coverage may be incomplete; review the coverage notes above before interpreting these pairs.</p>}
        {!pairs.length ? <p>{graph.nodes.filter(node => node.input && !node.unresolved).length < 2 ? 'At least two resolved input proteins are needed to compare pairs.' : 'Every resolved input pair has interaction evidence in this search.'}</p> : <>
            <label htmlFor="unknown-pair-search">Find a protein in these pairs</label>
            <input id="unknown-pair-search" type="search" placeholder="Gene symbol or UniProt accession" value={query} onChange={event => { setQuery(event.target.value); setPage(0) }} />
            <div className="collection-table-wrap"><table><thead><tr><th>Protein A</th><th>Protein B</th><th>Shared annotations</th></tr></thead><tbody>{filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).map(pair => {
                const result = results[pair.key]
                const loading = pending === pair.key
                return <Fragment key={pair.key}>
                    <tr><td>{pair.source.gene}<small>{pair.source.id}</small></td><td>{pair.target.gene}<small>{pair.target.id}</small></td><td><button type="button" disabled={Boolean(pending)} aria-label={`${result?.data ? 'Toggle shared GO terms' : 'Check GO'} for ${pair.source.gene} and ${pair.target.gene}`} aria-expanded={Boolean(open[pair.key])} onClick={() => result?.data ? setOpen(current => ({ ...current, [pair.key]: !current[pair.key] })) : check(pair)}>{loading ? 'Checking GO…' : result?.data ? `${open[pair.key] ? 'Hide' : 'Show'} ${result.data.shared_terms.length} shared terms` : result?.error ? 'Retry GO' : 'Check GO'}</button></td></tr>
                    {open[pair.key] && <tr className="shared-go-row"><td colSpan={3}><div aria-live="polite" aria-busy={loading}>{loading ? <p role="status">Fetching GO annotations from UniProt…</p> : result?.error ? <p className="collection-error" role="alert">{result.error}</p> : result?.data ? <SharedTerms result={result.data} source={pair.source} target={pair.target} /> : null}</div></td></tr>}
                </Fragment>
            })}</tbody></table></div>
            {!filtered.length && <p>No pairs match this protein.</p>}
            <div className="collection-actions"><button type="button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous pairs</button><span>{filtered.length.toLocaleString()} pairs · Page {currentPage + 1} of {pages}</span><button type="button" disabled={currentPage + 1 >= pages} onClick={() => setPage(currentPage + 1)}>Next pairs</button></div>
        </>}
    </section>
}
