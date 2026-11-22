import { useEffect, useState } from 'react'
import { API } from '../lib/routing'

const ACCESSION = /^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-\d+)?$/i
// One request per protein per page load, shared by every place that shows it.
const lookups = new Map()

function lookup(key) {
    if (!lookups.has(key)) {
        lookups.set(key, fetch(`${API}/uniprot/function?${key}`).then(async response => {
            const data = await response.json().catch(() => ({}))
            if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'UniProt lookup failed. Please retry.')
            return data
        }).catch(error => { lookups.delete(key); throw error }))
    }
    return lookups.get(key)
}

function uniprotEntryUrl(accession, gene, taxId) {
    if (accession && ACCESSION.test(accession)) return `https://www.uniprot.org/uniprotkb/${encodeURIComponent(accession.replace(/-\d+$/, '').toUpperCase())}/entry`
    if (gene && taxId) return `https://www.uniprot.org/uniprotkb?query=${encodeURIComponent(`gene_exact:${gene} AND organism_id:${taxId}`)}`
    return null
}

function FunctionText({ data, gene }) {
    return <>
        <p className="uniprot-function-title"><strong>{data.protein_name || data.accession}</strong>
            <span>{[data.gene, data.accession, data.organism].filter(Boolean).join(' · ')}{data.reviewed ? ' · reviewed (Swiss-Prot)' : ' · unreviewed (TrEMBL)'}</span></p>
        {gene && <p className="uniprot-function-note">Best UniProt match for gene {gene}.</p>}
        {data.function.length ? data.function.map((paragraph, index) => <p key={index}>
            {/* UniProt writes citations inline as "(PubMed:123, …)"; link them in place. */}
            {paragraph.text.split(/(PubMed:\d+)/).map((part, i) => /^PubMed:\d+$/.test(part)
                ? <a key={i} href={`https://pubmed.ncbi.nlm.nih.gov/${part.slice(7)}/`} target="_blank" rel="noopener noreferrer">{part}</a> : part)}
            {!/PubMed:\d+/.test(paragraph.text) && paragraph.pubmed.length > 0 && <> ({paragraph.pubmed.map((id, i) => <span key={id}>{i > 0 && ', '}<a href={`https://pubmed.ncbi.nlm.nih.gov/${encodeURIComponent(id)}/`} target="_blank" rel="noopener noreferrer">PubMed:{id}</a></span>)})</>}
        </p>) : <p>UniProt reports no function annotation for this entry.</p>}
        <p className="uniprot-function-note">Source: the Function section of the <a href={data.url} target="_blank" rel="noopener noreferrer">UniProt entry</a>.</p>
    </>
}

// UniProt link plus an on-demand "Show function" panel. Accepts an accession,
// or a gene symbol with a taxonomy ID (e.g. STRING interactors).
export default function UniProtProtein({ accession, gene, taxId, defaultOpen = false }) {
    const byAccession = Boolean(accession && ACCESSION.test(accession))
    const key = byAccession ? new URLSearchParams({ accession }).toString() : gene && taxId ? new URLSearchParams({ gene, tax_id: taxId }).toString() : ''
    const url = uniprotEntryUrl(accession, gene, taxId)
    const autoOpen = defaultOpen && Boolean(key)
    const [open, setOpen] = useState(autoOpen)
    const [state, setState] = useState(autoOpen ? { loading: true } : {})
    const load = () => {
        setState({ loading: true })
        lookup(key).then(data => setState({ data })).catch(error => setState({ error: error.message }))
    }
    // Opened by default (the searched protein): fetch once on mount. Remount with a new key for another protein.
    useEffect(() => {
        if (!autoOpen) return
        let active = true
        lookup(key).then(data => { if (active) setState({ data }) }).catch(error => { if (active) setState({ error: error.message }) })
        return () => { active = false }
    }, [autoOpen, key])
    if (!url) return null
    const toggle = () => {
        if (!open && !state.data && !state.loading) load()
        setOpen(!open)
    }
    return <span className="uniprot-protein">
        <span className="uniprot-actions">
            <a href={url} target="_blank" rel="noopener noreferrer" title={byAccession ? `Open ${accession} in UniProt` : `Search UniProt for ${gene}`}>UniProt ↗</a>
            {key && <button type="button" aria-expanded={open} onClick={toggle}>{open ? 'Hide function' : 'Show function'}</button>}
        </span>
        {open && <span className="uniprot-function" role="region" aria-live="polite" aria-label={`UniProt function of ${accession || gene}`}>
            {state.loading && <p role="status">Loading UniProt function…</p>}
            {state.error && <p className="uniprot-function-error" role="alert">{state.error} <button type="button" onClick={load}>Retry</button></p>}
            {state.data && <FunctionText data={state.data} gene={byAccession ? null : gene} />}
        </span>}
    </span>
}
