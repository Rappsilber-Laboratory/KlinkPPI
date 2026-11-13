import { useId, useRef } from 'react'
import { download } from '../collection/exports'

export function EmbeddingModelPicker({ models, selected, onChange, error }) {
    const dialog = useRef(null)
    const dialogId = useId()
    const label = selected[0] || 'Select model'
    return <div className="embedding-model-picker">
        <span>Embedding</span>
        <button type="button" className="embedding-model-trigger" aria-haspopup="dialog" aria-controls={dialogId} aria-label={`Select model: ${selected.length ? label : 'none selected'}`} title={label} disabled={!models.length} onClick={() => dialog.current.showModal()}>{label}</button>
        <dialog ref={dialog} id={dialogId} className="embedding-model-dialog" aria-labelledby={`${dialogId}-title`} onClick={event => {
            if (event.target !== event.currentTarget) return
            const bounds = event.currentTarget.getBoundingClientRect()
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.current.close()
        }}>
            <h3 id={`${dialogId}-title`}>Select model</h3>
            <p>Choose one model for the pair comparisons.</p>
            <fieldset><legend>Embedding model</legend>{models.map(model => <label key={model}>
                <input type="radio" name={`${dialogId}-model`} checked={selected[0] === model} onChange={() => onChange([model])} />{model}
            </label>)}</fieldset>
            <div className="collection-actions"><button type="button" onClick={() => dialog.current.close()}>Done</button></div>
        </dialog>
        {error && <small role="alert">{error}</small>}
    </div>
}

export function PairEmbeddingCell({ pair, state, detailsId }) {
    const task = state.tasks[pair.key]
    const busy = task && ['queued', 'running'].includes(task.status)
    const matches = task?.models?.length === state.selected.length && task.models.every(model => state.selected.includes(model))
    return <div className="pair-embedding-cell">
        {busy && <div role="status"><progress max={task.total_steps || 1} value={task.completed_steps || 0} />
            <small>{task.progress}</small><small>{(task.runtime_seconds || 0).toFixed(1)} s runtime</small></div>}
        {task?.status === 'failed' && <small className="collection-error" role="alert">{task.error}</small>}
        {task?.result && <button type="button" aria-expanded={Boolean(state.open[pair.key])} aria-controls={detailsId} onClick={() => state.toggle(pair.key)}>{state.open[pair.key] ? 'Hide' : 'Show'} scores · {task.runtime_seconds.toFixed(1)} s</button>}
        {!busy && <button type="button" disabled={Boolean(state.active) || state.selected.length !== 1 || !state.models.length} onClick={() => state.compute(pair)} aria-label={`Compute embedding distances for ${pair.source.gene} and ${pair.target.gene}`}>{task?.status === 'failed' ? 'Retry distances' : task?.result && !matches ? 'Compute selected model' : 'Compute distances'}</button>}
    </div>
}

export function PairEmbeddingDetails({ id, task, source, target }) {
    const result = task.result
    const downloadScores = () => {
        const pairName = [source, target].map(protein => String(protein.gene || protein.id).replace(/[^a-zA-Z0-9._-]+/g, '_')).join('_')
        const tsv = 'metric\tvalue\n' + Object.entries(result.scores).map(([metric, value]) => `${metric}\t${value}`).join('\n') + '\n'
        download(tsv, `${pairName}_plm_scores.tsv`, 'text/tab-separated-values;charset=utf-8')
    }
    return <div id={id} className="pair-embedding-details">
        <h3>Embedding scores: {source.gene} ↔ {target.gene}</h3>
        <div className="collection-actions"><button type="button" onClick={downloadScores}>Download PLM scores (TSV)</button></div>
        <p>{result.interpretation}</p>
        <p className="collection-note">{result.source_length} and {result.target_length} residues · Runtime: {task.runtime_seconds.toFixed(2)} s, including sequence fetching, model loading/downloads and scoring; queue time excluded.</p>
        <p className="collection-note">{Object.entries(result.model_runtime_seconds).map(([model, seconds]) => `${model}: ${seconds.toFixed(2)} s`).join(' · ')}</p>
        <div className="collection-table-wrap"><table><thead><tr><th>Score</th><th>Value</th><th>Meaning</th></tr></thead><tbody>
            {Object.entries(result.scores).map(([name, value]) => <tr key={name}><td>{name}</td><td>{Number(value).toPrecision(6)}</td><td>{result.descriptions[name]}</td></tr>)}
        </tbody></table></div>
    </div>
}
