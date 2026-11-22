import { useEffect, useRef, useState } from 'react'
import { DATABASES, LABELS, MAX_IDENTIFIERS, MAX_PAIRS, parseIdentifiers, parsePairs } from '../collection/analysis'
import CollectionResults from './CollectionResults'
import CollectionResultsBoundary from './CollectionResultsBoundary'
import '../collection/collection.css'
import { API, resultUrl, useLimits } from '../lib/routing'
import Link from './Link'
import UniProtProtein from './UniProtProtein'

// Human homologous-recombination / Fanconi anaemia module (same as the server's example result).
const EXAMPLE_IDENTIFIERS = ['P38398', 'Q99728', 'Q86YC2', 'P51587', 'Q06609', 'O15315', 'O43502', 'O75771', 'O43543', 'O43542', 'Q9BXW9', 'Q9NVI1', 'O15360', 'Q14565']
const EXAMPLE_FILE = `${import.meta.env.BASE_URL}examples/collection_example.txt`
// Same pairs as the server's PPI example: known (BRCA1–BARD1, PALB2–BRCA2, RAD51–RAD51C, FANCD2–FANCI, TP53–MDM2)
// and without evidence (RAD51C–DMC1, BARD1–XRCC3).
const EXAMPLE_PAIRS = [['P38398', 'Q99728'], ['Q86YC2', 'P51587'], ['Q06609', 'O43502'], ['Q9BXW9', 'Q9NVI1'], ['P04637', 'Q00987'], ['O43502', 'Q14565'], ['Q99728', 'O43542']]
const PPI_EXAMPLE_FILE = `${import.meta.env.BASE_URL}examples/ppi_example.txt`
async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, options)
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
        const error = new Error(typeof data.detail === 'string' ? data.detail : 'Request failed. Check your inputs and try again.')
        error.status = response.status
        throw error
    }
    return data
}

function ResultLink({ job, retentionDays }) {
    const [copied, setCopied] = useState(false)
    const url = resultUrl(job.job_id, job.search_type)
    const copy = async () => {
        try { await navigator.clipboard.writeText(url); setCopied(true); window.setTimeout(() => setCopied(false), 2000) }
        catch { setCopied(false) }
    }
    const expires = job.expires_at ? new Date(job.expires_at * 1000).toLocaleDateString() : null
    return <div className="result-link" role="note">
        <strong>{job.pinned ? 'Example result (read-only, always available)' : 'Bookmark your result'}</strong>
        <p>{job.pinned
            ? 'This permanent example lets you explore every result view. Load the example into the form to run your own copy.'
            : `Your analysis keeps running on the server if you close this page. Return any time with this private link${expires ? ` until ${expires}` : ` for ${retentionDays} days`}; only people you share it with can open it.`}</p>
        <div className="result-link-row"><input readOnly value={url} aria-label="Result link" onFocus={event => event.target.select()} /><button type="button" onClick={copy}>{copied ? 'Copied' : 'Copy link'}</button></div>
    </div>
}

const parseInput = (searchType, text) => searchType === 'ppi' ? parsePairs(text) : parseIdentifiers(text)

export default function CollectionSearch({ searchType = 'batch', initialJobId = null, onJobChange = () => {} }) {
    const isPPI = searchType === 'ppi'
    const limits = useLimits()
    const [loadError, setLoadError] = useState('')
    const [speciesQuery, setSpeciesQuery] = useState('')
    const [species, setSpecies] = useState(null)
    const [suggestions, setSuggestions] = useState([])
    const [identifiers, setIdentifiers] = useState('')
    const [inputType, setInputType] = useState('auto')
    const [databases, setDatabases] = useState(['IntAct', 'BioGrid'])
    const [mode, setMode] = useState('induced')
    const [neighborLimit, setNeighborLimit] = useState(String(limits.default_neighbor_limit))
    const [neighborScope, setNeighborScope] = useState('protein')
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

    // Jobs are persisted on the server and keep running when the page closes;
    // a bookmarked /results/<id> link reopens them with the submitted settings.
    useEffect(() => {
        if (!initialJobId || jobRef.current === initialJobId) return
        const controller = new AbortController()
        setLoadError('')
        request(`/collection/jobs/${encodeURIComponent(initialJobId)}`, { signal: controller.signal })
            .then(data => {
                // A shared link may point to the other search type; hand it to that tab.
                if ((data.search_type || 'batch') !== searchType) { onJobChange(data.job_id, data.search_type || 'batch', searchType); return }
                jobRef.current = data.job_id
                setJob(data)
                setSpecies({ display_name: data.species, tax_id: data.tax_id })
                setSpeciesQuery(data.species)
                setSuggestions([])
                setIdentifiers(isPPI ? (data.pairs || []).map(pair => pair.join('\t')).join('\n') : (data.tokens || []).join('\n'))
                setInputType(data.input_type || 'auto')
                setDatabases(data.databases || [])
                setMode(data.mode || 'induced')
                if (data.neighbor_limit) setNeighborLimit(String(data.neighbor_limit))
                setNeighborScope(data.neighbor_scope || 'protein')
                setChoices({})
                setPollRetry(0)
            })
            .catch(err => {
                if (err.name === 'AbortError') return
                setLoadError(err.status === 404
                    ? `This result does not exist or has expired. Results are kept for ${limits.result_retention_days} days after submission.`
                    : `The result could not be loaded: ${err.message}`)
            })
        return () => controller.abort()
    }, [initialJobId, limits.result_retention_days, isPPI, searchType, onJobChange])

    const selectSpecies = value => {
        setSpecies(value)
        setSpeciesQuery(value.display_name)
        setSuggestions([])
        const available = value.supported_databases || value.databases
        if (Array.isArray(available)) setDatabases(current => current.filter(db => available.includes(db)))
    }
    const available = species?.supported_databases || species?.databases || DATABASES
    const loadExample = async () => {
        setPending(true)
        setError('')
        try {
            const data = await request('/species/search?q=Homo%20sapiens&limit=10')
            const human = data.results?.find(value => String(value.tax_id) === '9606')
            if (!human) throw new Error('Human species information is unavailable. Please retry loading the example.')
            selectSpecies(human)
            setIdentifiers(isPPI ? EXAMPLE_PAIRS.map(pair => pair.join('-')).join('\n') : EXAMPLE_IDENTIFIERS.join('\n'))
            setInputType('UniProtKB')
            setMode('induced')
            setDatabases(DATABASES.filter(db => (human.supported_databases || DATABASES).includes(db)))
        } catch (err) { setError(err.message) }
        finally { setPending(false) }
    }
    const upload = async event => {
        const file = event.target.files?.[0]
        if (!file) return
        try {
            if (file.size > 1024 * 1024) throw new Error('Use a list file smaller than 1 MB.')
            const text = await file.text()
            parseInput(searchType, text)
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
            const parsed = parseInput(searchType, identifiers)
            if (!databases.length) throw new Error('Select at least one database.')
            const limit = Number(neighborLimit)
            if (mode === 'expanded' && !(Number.isInteger(limit) && limit >= 1 && limit <= limits.max_neighbor_limit)) throw new Error(`Show 1–${limits.max_neighbor_limit} neighbors per ${isPPI && neighborScope === 'pair' ? 'PPI' : 'protein'}.`)
            setPending(true)
            if (job?.status === 'awaiting_selection') await request(`/collection/jobs/${job.job_id}/cancel`, { method: 'POST' })
            const common = { input_type: inputType, species_name: species.display_name, tax_id: species.tax_id, selected_databases: databases, mode,
                neighbor_limit: mode === 'expanded' ? limit : null }
            const data = await request(isPPI ? '/collection/ppi-jobs' : '/collection/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(isPPI ? { ...common, pairs: parsed.pairs, neighbor_scope: neighborScope } : { ...common, identifiers: parsed.ids }) })
            jobRef.current = data.job_id
            setJob(data)
            setLoadError('')
            onJobChange(data.job_id, searchType, searchType)
            setDuplicates(parsed.duplicates + (parsed.selfPairs || 0))
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
    const rerun = async () => {
        if (busy) return
        setPending(true)
        setError('')
        try {
            const data = await request(`/collection/jobs/${job.job_id}/rerun`, { method: 'POST' })
            jobRef.current = data.job_id
            setJob(data)
            setPollRetry(0)
        } catch (err) { setError(err.message) }
        finally { setPending(false) }
    }
    const cancel = async () => {
        try { setJob(await request(`/collection/jobs/${job.job_id}/cancel`, { method: 'POST' })) }
        catch (err) { setError(err.message) }
    }
    const undecided = job?.resolution?.some(row => row.candidates.length > 1 && !(row.input in choices))

    const inputId = `${searchType}-identifiers`
    return <section className="collection-shell" aria-label={isPPI ? 'PPI search' : 'Batch search'}>
        <form className="collection-card collection-form" onSubmit={start}>
            {isPPI
                ? <div className="collection-intro"><span className="collection-eyebrow">PPI SEARCH</span><h2>Check specific protein–protein interactions</h2><p>List protein pairs such as P1-P2. Known pairs show their evidence across databases; pairs without evidence get the same follow-ups as in batch search (shared GO terms, sequence alignment, embeddings).</p></div>
                : <div className="collection-intro"><span className="collection-eyebrow">BATCH SEARCH</span><h2>From a protein list to an evidence network</h2><p>Choose a species, review your IDs, then explore interactions across databases.</p></div>}
            <fieldset disabled={busy} className="collection-fields">
                <div className="collection-grid">
                    <div>
                        <label htmlFor={`${searchType}-species`}>Species <span className="required">required</span></label>
                        <input id={`${searchType}-species`} autoComplete="off" placeholder="e.g. Homo sapiens" value={speciesQuery} onChange={e => { setSpeciesQuery(e.target.value); setSpecies(null); setSuggestions([]) }} aria-controls={`${searchType}-species-suggestions`} />
                        {!species && suggestions.length > 0 && <ul id={`${searchType}-species-suggestions`} className="species-options">{suggestions.map(s => <li key={s.tax_id}><button type="button" onClick={() => selectSpecies(s)}>{s.display_name} <small>Taxonomy {s.tax_id}</small></button></li>)}</ul>}
                        {species && <p className="collection-note">Selected: {species.display_name} · Taxonomy {species.tax_id}</p>}
                    </div>
                    <div><label htmlFor={`${searchType}-input-type`}>Identifier type</label><select id={`${searchType}-input-type`} value={inputType} onChange={e => setInputType(e.target.value)}><option value="auto">Detect each ID (mixed list)</option><option value="UniProtKB">UniProt accession / entry name</option><option value="Gene_Name">Gene symbols</option><option value="Ensembl">Ensembl</option><option value="GeneID">NCBI GeneID</option></select><p className="collection-note">Use an explicit type when a gene symbol resembles another ID.</p></div>
                </div>
                <div className="collection-job-heading"><label htmlFor={inputId}>{isPPI ? `PPI list (up to ${MAX_PAIRS} pairs)` : `Gene / protein list (up to ${MAX_IDENTIFIERS} entries)`}</label><div className="collection-job-buttons"><button type="button" onClick={loadExample} disabled={busy}>Load example</button><Link className="collection-link-button" to={isPPI ? `/ppi-results/${limits.ppi_example_job_id}` : `/results/${limits.example_job_id}`}>View example result</Link></div></div>
                <textarea id={inputId} rows={6} placeholder={isPPI ? 'TP53-MDM2\nBRCA1\tBARD1\nP38398,O15360' : 'TP53\nBRCA1\nP04637'} value={identifiers} onChange={e => setIdentifiers(e.target.value)} required />
                <div className="collection-upload"><label htmlFor={`${searchType}-file`}>Or upload CSV, TSV or TXT</label><input id={`${searchType}-file`} type="file" accept=".csv,.tsv,.txt,text/plain,text/csv,text/tab-separated-values" onChange={upload} />
                    {isPPI
                        ? <p className="collection-note">One PPI per line, no header: <code>A-B</code>, or the two IDs separated by a tab, comma or space (use a separator when an ID contains a hyphen, e.g. isoforms or HLA-A). Up to {MAX_PAIRS} distinct pairs over {limits.ppi_max_proteins} proteins; A-B and B-A are merged. <a href={PPI_EXAMPLE_FILE} download="ppi_example.txt">Download the example file</a> to check the format. <Link to="/help#input-formats">Input format help</Link></p>
                        : <p className="collection-note">One ID per line. No header or extra columns. Up to {MAX_IDENTIFIERS} distinct IDs; duplicates are merged. <a href={EXAMPLE_FILE} download="collection_example.txt">Download the example file</a> to check the format. <Link to="/help#input-formats">Input format help</Link></p>}</div>
                <div className="collection-grid">
                    <fieldset className="mode-options"><legend>Network mode</legend>{[['induced', 'Induced network', isPPI ? 'Interactions among all proteins in your PPIs.' : 'Interactions among your resolved input proteins.'], ['expanded', 'Expanded network', 'Adds the best-supported first-neighbor interactors, up to the number you choose. Neighbor edges appear gray.']].map(([value, title, detail]) => <label key={value} className={mode === value ? 'selected-mode' : ''}><input type="radio" name={`${searchType}-mode`} value={value} checked={mode === value} onChange={() => setMode(value)} /><span><strong>{title}</strong><small>{detail}</small></span></label>)}
                        {mode === 'expanded' && <div className="neighbor-limit">
                            <div><label htmlFor={`${searchType}-neighbors`}>Neighbors to show</label><input id={`${searchType}-neighbors`} type="number" min="1" max={limits.max_neighbor_limit} step="1" required value={neighborLimit} onChange={e => setNeighborLimit(e.target.value)} /></div>
                            {isPPI ? <div><label htmlFor={`${searchType}-neighbor-scope`}>Count neighbors</label><select id={`${searchType}-neighbor-scope`} value={neighborScope} onChange={e => setNeighborScope(e.target.value)}><option value="protein">Per protein</option><option value="pair">Per PPI (shared neighbors first)</option></select></div> : <p className="collection-note">Per input protein.</p>}
                            <p className="collection-note" style={{ gridColumn: '1 / -1' }}>Neighbors are ranked by the number of supporting databases, then publications, then evidence records. Lower-ranked neighbors are hidden, not deleted from the sources.</p>
                        </div>}</fieldset>
                    <fieldset className="database-options"><legend>Source databases</legend><div>{DATABASES.map(db => <label key={db} title={available.includes(db) ? '' : 'Unavailable for this species'}><input type="checkbox" checked={databases.includes(db)} disabled={!available.includes(db)} onChange={e => setDatabases(current => e.target.checked ? [...current, db] : current.filter(value => value !== db))} />{LABELS[db] || db}</label>)}</div></fieldset>
                </div>
            </fieldset>
            <div className="collection-actions"><button className="collection-primary" disabled={busy} type="submit">{busy ? 'Working…' : 'Resolve collection IDs'}</button>{!job?.pinned && ['resolving', 'running', 'awaiting_selection'].includes(job?.status) && <button type="button" onClick={cancel}>Cancel job</button>}<span className="collection-note">No interactions are queried until you review the mappings.</span></div>
            {error && <p className="collection-error" role="alert">{error}</p>}
        </form>
        {loadError && <div className="collection-card collection-warning" role="alert"><p>{loadError}</p><p><Link to="/">Start a new search</Link> · <Link to={isPPI ? `/ppi-results/${limits.ppi_example_job_id}` : `/results/${limits.example_job_id}`}>Open the example result</Link></p></div>}
        {job && <ResultLink job={job} retentionDays={limits.result_retention_days} />}
        {job && <div className="collection-card" aria-live="polite"><div className="collection-job-heading"><h3>{job.species} · {job.mode} network{job.pairs ? ` · ${job.pairs.length} PPIs` : ''}{job.neighbor_limit ? ` · top ${job.neighbor_limit} neighbors per ${job.neighbor_scope === 'pair' ? 'PPI' : 'protein'}` : ''}</h3><div className="collection-job-buttons"><span className="collection-status">{job.status.replaceAll('_', ' ')}</span>{job.status === 'completed' && !job.pinned && <button type="button" onClick={rerun} disabled={busy} title="Repeat this search with the same IDs, mappings, species, databases and network mode">Rerun</button>}</div></div><p>{job.progress}</p>{job.database_statuses && <div className="database-progress">{Object.entries(job.database_statuses).map(([db, state]) => <span key={db} className={state.status}><i />{LABELS[db] || db}{state.total > 0 && <small>{state.completed}/{state.total}</small>}</span>)}</div>}{duplicates > 0 && <p className="collection-note">{duplicates} duplicate {isPPI ? 'or self-pair rows skipped' : 'input rows merged'}.</p>}{job.status === 'completed' && <p className="collection-note"><Link to="/help#collection-results">How to interpret these results</Link></p>}</div>}
        {job?.status === 'awaiting_selection' && <div className="collection-card">
            <h3>Review ID resolution</h3><p className="collection-note">Multiple matches require a choice. Skipped and unresolved IDs stay isolated in the network.</p>
            <div className="collection-table-wrap"><table><thead><tr><th>Input</th><th>Status</th><th>UniProt mapping</th></tr></thead><tbody>{job.resolution.map(row => <tr key={row.input}><td>{row.input}<small>{row.input_type}</small></td><td>{row.status}</td><td>{row.candidates.length > 1 ? <select aria-label={`Mapping for ${row.input}`} value={choices[row.input] ?? '__choose__'} onChange={e => setChoices(current => ({ ...current, [row.input]: e.target.value || null }))}><option value="__choose__" disabled>Choose a match…</option><option value="">Skip this ID</option>{row.candidates.map(c => <option value={c.id} key={c.id}>{c.gene} · {c.id} · {c.reviewed ? 'reviewed' : 'unreviewed'}</option>)}</select> : row.candidates.length === 1 ? <>{row.candidates[0].gene} · {row.candidates[0].id}<UniProtProtein accession={row.candidates[0].id} /></> : row.error || 'No match in the selected species'}</td></tr>)}</tbody></table></div>
            <button className="collection-primary" type="button" onClick={run} disabled={pending || undecided}>Run {job.mode} analysis</button>
        </div>}
        {job?.status === 'completed' && <CollectionResultsBoundary jobId={job.job_id}><CollectionResults job={job} /></CollectionResultsBoundary>}
    </section>
}
