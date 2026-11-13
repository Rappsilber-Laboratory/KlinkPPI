import { useState } from 'react'
import { postBlast } from '../collection/proteinActions'

export default function CollectionProteinActions({ protein, species, getSequence }) {
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [message, setMessage] = useState('')
    const [fasta, setFasta] = useState('')
    const act = async action => {
        setError('')
        setMessage('')
        // Reserve the tab during the click, before waiting for UniProt.
        const target = `klinkppi-blast-${crypto.randomUUID()}`
        const tab = action === 'blast' ? window.open('about:blank', target) : null
        if (action === 'blast' && !tab) {
            setError('The BLAST tab was blocked. Allow popups for this site and click Search BLASTP again, or Copy FASTA and paste it into NCBI Protein BLAST.')
            return
        }
        if (tab) {
            tab.opener = null
            tab.document.title = 'Loading UniProt sequence…'
            tab.document.body.textContent = `Fetching the UniProt sequence for ${protein.id}…`
        }
        setLoading(true)
        try {
            const data = await getSequence(protein.id)
            if (action === 'blast') {
                if (tab.closed) throw new Error('The BLAST tab was closed. Click Search BLASTP to retry.')
                postBlast(target, data, species)
                setMessage('Opened Protein BLAST. Choose settings and start the search there.')
            } else {
                try {
                    await navigator.clipboard.writeText(data.fasta)
                    setFasta('')
                    setMessage('FASTA copied.')
                } catch {
                    setFasta(data.fasta)
                    setMessage('Clipboard unavailable. Select and copy the FASTA below.')
                }
            }
        } catch (err) {
            tab?.close()
            setError(`${err.message} Click the action again to retry.`)
        } finally { setLoading(false) }
    }
    return <div className="protein-actions">
        <div className="protein-action-buttons">
            <button type="button" disabled={loading} onClick={() => act('blast')}>Search BLASTP ↗</button>
            <button type="button" disabled={loading} onClick={() => act('copy')}>Copy FASTA</button>
            <a href={`https://www.alphafold.ebi.ac.uk/entry/${encodeURIComponent(protein.id)}`} target="_blank" rel="noopener noreferrer">Find similar structures ↗</a>
        </div>
        <div aria-live="polite">{loading && <p role="status">Fetching UniProt sequence…</p>}{message && <p role="status">{message}</p>}</div>
        {error && <p className="collection-error" role="alert">{error}</p>}
        {fasta && <label>FASTA for {protein.gene} ({protein.id})<textarea readOnly rows={5} value={fasta} onFocus={event => event.target.select()} onClick={event => event.target.select()} /></label>}
    </div>
}
