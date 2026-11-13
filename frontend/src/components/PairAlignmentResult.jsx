export default function PairAlignmentResult({ alignment, isOpen, onToggle, detailsId }) {
    const result = alignment.result
    if (alignment.status === 'failed') return <p className="collection-error" role="alert">{alignment.error || 'Alignment failed. Please retry.'}</p>
    if (!result) return <div className="pair-alignment-progress" role="status" aria-live="polite">
        <progress max={3} value={alignment.completed_steps || 0} aria-label="Sequence fetching and alignment progress" />
        <small>{alignment.progress}</small>
        <small>{alignment.completed_steps || 0}/3 steps complete</small>
    </div>
    return <div className="pair-alignment-result">
        <strong>Score: {result.score.toFixed(1)}</strong>
        <small>Identity: {result.identity_percent.toFixed(1)}% ({result.identities}/{result.alignment_length} columns)</small>
        <button type="button" aria-expanded={Boolean(isOpen)} aria-controls={detailsId} onClick={onToggle}>{isOpen ? 'Hide alignment' : 'View alignment'}</button>
    </div>
}
