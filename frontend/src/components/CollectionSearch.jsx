import { useEffect, useRef, useState } from 'react'
import { DATABASES, LABELS, parseIdentifiers } from '../collection/analysis'
import CollectionResults from './CollectionResults'
import '../collection/collection.css'

const API = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`
async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, options)
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed. Check your inputs and try again.')
    return data
}

export default function CollectionSearch() {
    const [speciesQuery, setSpeciesQuery] = useState('')
    const [species, setSpecies] = useState(null)
    const [suggestions, setSuggestions] = useState([])
    const [identifiers, setIdentifiers] = useState('')
    const [inputType, setInputType] = useState('auto')
    const [databases, setDatabases] = useState(['IntAct', 'BioGrid'])
    const [mode, setMode] = useState('induced')
    const [job, setJob] = useState(null)
    const [choices, setChoices] = useState({})
    const [error, setError] = useState('')
    const [pending, setPending] = useState(false)
    const [duplicates, setDuplicates] = useState(0)
    const [pollRetry, setPollRetry] = useState(0)
    const jobRef = useRef(null)
    const busy = pending || ['resolving', 'running'].includes(job?.status)

    useEffect(() => {
        if (species || !speciesQuery.trim()) return
        const controller = new AbortController()
        const timer = setTimeout(() => {
            request(`/species/search?q=${encodeURIComponent(speciesQuery)}&limit=10`, { signal: controller.signal })
                .then(data => setSuggestions(data.results || []))
                .catch(err => { if (err.name !== 'AbortError') setError(err.message) })
        }, 180)
        return () => { clearTimeout(timer); controller.abort() }
    }, [speciesQuery, species])

    useEffect(() => {
        if (!job || !['resolving', 'running'].includes(job.status)) return
        const controller = new AbortController()
        const timer = setTimeout(async () => {
            try {
                const data = await request(`/collection/jobs/${job.job_id}`, { signal: controller.signal })
                setJob(data)
                setError('')
            } catch (err) {
                if (err.name !== 'AbortError') {
                    setError(`Progress refresh failed: ${err.message}. Retrying…`)
                    setPollRetry(value => value + 1)
                }
            }
        }, pollRetry ? 3000 : 1200)
        return () => { clearTimeout(timer); controller.abort() }
    }, [job, pollRetry])

    // A page unmount cancels the server job; changing tabs keeps this component mounted.
    useEffect(() => () => {
        if (jobRef.current) fetch(`${API}/collection/jobs/${jobRef.current}/cancel`, { method: 'POST', keepalive: true }).catch(() => {})
    }, [])

    const selectSpecies = value => {
        setSpecies(value)
        setSpeciesQuery(value.display_name)
        setSuggestions([])
        const available = value.supported_databases || value.databases
        if (Array.isArray(available)) setDatabases(current => current.filter(db => available.includes(db)))
    }
    const available = species?.supported_databases || species?.databases || DATABASES
    const upload = async event => {
        const file = event.target.files?.[0]
        if (!file) return
        try {
            if (file.size > 1024 * 1024) throw new Error('Use a list file smaller than 1 MB.')
            const text = await file.text()
            parseIdentifiers(text)
            setIdentifiers(text)
            setError('')
        } catch (err) { setError(err.message) }
        event.target.value = ''
    }
    const start = async event => {
        event.preventDefault()
        setError('')
        try {
            if (!species) throw new Error('Choose a species from the suggestions.')
            const parsed = parseIdentifiers(identifiers)
            if (!databases.length) throw new Error('Select at least one database.')
            setPending(true)
            if (job?.status === 'awaiting_selection') await request(`/collection/jobs/${job.job_id}/cancel`, { method: 'POST' })
            const data = await request('/collection/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
                identifiers: parsed.ids, input_type: inputType, species_name: species.display_name, tax_id: species.tax_id,
                selected_databases: databases, mode,
            }) })
            jobRef.current = data.job_id
            setJob(data)
            setDuplicates(parsed.duplicates)
            setChoices({})
            setPollRetry(0)
        } catch (err) { setError(err.message) }
        finally { setPending(false) }
    }
    const run = async () => {
        setPending(true)
        setError('')
        try { setJob(await request(`/collection/jobs/${job.job_id}/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ choices }) })) }
        catch (err) { setError(err.message) }
        finally { setPending(false) }
    }
    const cancel = async () => {
        try { setJob(await request(`/collection/jobs/${job.job_id}/cancel`, { method: 'POST' })); jobRef.current = null }
        catch (err) { setError(err.message) }
    }
    const undecided = job?.resolution?.some(row => row.candidates.length > 1 && !(row.input in choices))

    return <section className="collection-shell" aria-label="Collection search">
        <form className="collection-card collection-form" onSubmit={start}>
            <div className="collection-intro"><span className="collection-eyebrow">COLLECTION ANALYSIS</span><h2>From a protein list to an evidence network</h2><p>Choose a species, review your IDs, then explore interactions across databases.</p></div>
            <fieldset disabled={busy} className="collection-fields">
                <div className="collection-grid">
                    <div>
                        <label htmlFor="collection-species">Species <span className="required">required</span></label>
                        <input id="collection-species" autoComplete="off" placeholder="e.g. Homo sapiens" value={speciesQuery} onChange={e => { setSpeciesQuery(e.target.value); setSpecies(null); setSuggestions([]) }} aria-controls="collection-species-suggestions" />
                        {!species && suggestions.length > 0 && <ul id="collection-species-suggestions" className="species-options">{suggestions.map(s => <li key={s.tax_id}><button type="button" onClick={() => selectSpecies(s)}>{s.display_name} <small>Taxonomy {s.tax_id}</small></button></li>)}</ul>}
                        {species && <p className="collection-note">Selected: {species.display_name} · Taxonomy {species.tax_id}</p>}
                    </div>
                    <div><label htmlFor="collection-input-type">Identifier type</label><select id="collection-input-type" value={inputType} onChange={e => setInputType(e.target.value)}><option value="auto">Detect each ID (mixed list)</option><option value="UniProtKB">UniProt accession / entry name</option><option value="Gene_Name">Gene symbols</option><option value="Ensembl">Ensembl</option><option value="GeneID">NCBI GeneID</option></select><p className="collection-note">Use an explicit type when a gene symbol resembles another ID.</p></div>
                </div>
                <label htmlFor="collection-identifiers">Gene / protein list</label>
                <textarea id="collection-identifiers" rows={6} placeholder={'TP53\nBRCA1\nP04637'} value={identifiers} onChange={e => setIdentifiers(e.target.value)} required />
                <div className="collection-upload"><label htmlFor="collection-file">Or upload CSV, TSV or TXT</label><input id="collection-file" type="file" accept=".csv,.tsv,.txt,text/plain,text/csv,text/tab-separated-values" onChange={upload} /><p className="collection-note">One ID per line. No header or extra columns. Up to 200 distinct IDs; duplicates are merged.</p></div>
                <div className="collection-grid">
                    <fieldset className="mode-options"><legend>Network mode</legend>{[['induced', 'Induced network', 'Interactions among your resolved input proteins.'], ['expanded', 'Expanded network', 'Your inputs plus first-neighbor interactors. Neighbor edges appear gray.']].map(([value, title, detail]) => <label key={value} className={mode === value ? 'selected-mode' : ''}><input type="radio" name="collection-mode" value={value} checked={mode === value} onChange={() => setMode(value)} /><span><strong>{title}</strong><small>{detail}</small></span></label>)}</fieldset>
                    <fieldset className="database-options"><legend>Source databases</legend><div>{DATABASES.map(db => <label key={db} title={available.includes(db) ? '' : 'Unavailable for this species'}><input type="checkbox" checked={databases.includes(db)} disabled={!available.includes(db)} onChange={e => setDatabases(current => e.target.checked ? [...current, db] : current.filter(value => value !== db))} />{LABELS[db] || db}</label>)}</div></fieldset>
                </div>
            </fieldset>
            <div className="collection-actions"><button className="collection-primary" disabled={busy} type="submit">{busy ? 'Working…' : 'Resolve collection IDs'}</button>{['resolving', 'running', 'awaiting_selection'].includes(job?.status) && <button type="button" onClick={cancel}>Cancel job</button>}<span className="collection-note">No interactions are queried until you review the mappings.</span></div>
            {error && <p className="collection-error" role="alert">{error}</p>}
        </form>
        {job && <div className="collection-card" aria-live="polite"><div className="collection-job-heading"><h3>{job.species} · {job.mode} network</h3><span className="collection-status">{job.status.replaceAll('_', ' ')}</span></div><p>{job.progress}</p>{job.database_statuses && <div className="database-progress">{Object.entries(job.database_statuses).map(([db, state]) => <span key={db} className={state.status}><i />{LABELS[db] || db}{state.total > 0 && <small>{state.completed}/{state.total}</small>}</span>)}</div>}{duplicates > 0 && <p className="collection-note">{duplicates} duplicate input rows merged.</p>}</div>}
        {job?.status === 'awaiting_selection' && <div className="collection-card">
            <h3>Review ID resolution</h3><p className="collection-note">Multiple matches require a choice. Skipped and unresolved IDs stay isolated in the network.</p>
            <div className="collection-table-wrap"><table><thead><tr><th>Input</th><th>Status</th><th>UniProt mapping</th></tr></thead><tbody>{job.resolution.map(row => <tr key={row.input}><td>{row.input}<small>{row.input_type}</small></td><td>{row.status}</td><td>{row.candidates.length > 1 ? <select aria-label={`Mapping for ${row.input}`} value={choices[row.input] ?? '__choose__'} onChange={e => setChoices(current => ({ ...current, [row.input]: e.target.value || null }))}><option value="__choose__" disabled>Choose a match…</option><option value="">Skip this ID</option>{row.candidates.map(c => <option value={c.id} key={c.id}>{c.gene} · {c.id} · {c.reviewed ? 'reviewed' : 'unreviewed'}</option>)}</select> : row.candidates.length === 1 ? `${row.candidates[0].gene} · ${row.candidates[0].id}` : row.error || 'No match in the selected species'}</td></tr>)}</tbody></table></div>
            <button className="collection-primary" type="button" onClick={run} disabled={pending || undecided}>Run {job.mode} analysis</button>
        </div>}
        {job?.status === 'completed' && <CollectionResults key={job.job_id} job={job} />}
    </section>
}
