import { useMemo } from 'react'
import { alignmentBlocks, RESIDUE_GROUPS, residueGroup } from '../collection/alignment'

function SequenceRow({ protein, sequence, start, end }) {
    let position = start == null ? 0 : start - 1
    return <div className="alignment-sequence-row">
        <span className="alignment-protein-label">{protein.gene}<small>{protein.id}</small></span>
        <span className="alignment-position">{start ?? '—'}</span>
        <code className="alignment-residues" aria-label={`${protein.gene} sequence ${start ?? 'gap'} to ${end ?? 'gap'}`}>
            {[...sequence].map((residue, index) => {
                const group = residueGroup(residue)
                if (residue !== '-') position++
                return <span key={index} className={`aa-residue aa-${group.key}`} title={residue === '-' ? 'Gap' : `${protein.id} · residue ${position}: ${residue} · ${group.label}`}>{residue}</span>
            })}
        </code>
        <span className="alignment-position">{end ?? '—'}</span>
    </div>
}

export default function PairAlignmentDetails({ result, source, target, id }) {
    const blocks = useMemo(() => alignmentBlocks(result.aligned_source, result.aligned_target), [result.aligned_source, result.aligned_target])
    return <section id={id} className="pair-alignment-details" aria-label={`Sequence alignment for ${source.gene} and ${target.gene}`}>
        <div className="alignment-detail-heading"><div><span className="collection-eyebrow">PAIRWISE SEQUENCE ALIGNMENT</span><h3>{source.gene} ↔ {target.gene}</h3><p className="collection-note">{source.id} ({result.source_length} aa) · {target.id} ({result.target_length} aa)</p></div><div className="alignment-summary"><span><strong>{result.score.toFixed(1)}</strong> raw score</span><span><strong>{result.identity_percent.toFixed(1)}%</strong> identity</span><span><strong>{result.gap_columns}</strong> gap columns</span></div></div>
        <div className="alignment-color-legend" aria-label="Amino acid color legend">{RESIDUE_GROUPS.map(group => <span key={group.key}><i className={`aa-${group.key}`} />{group.label}<small>{group.residues}</small></span>)}</div>
        <p className="collection-note">Colors show amino-acid properties. <strong>|</strong> marks an identical residue; <strong>·</strong> marks a substitution; a blank marker indicates a gap. Numbers are positions in each original sequence.</p>
        <div className="alignment-sequence-scroll" tabIndex={0} aria-label="Colored aligned sequences; scroll to view all residues">
            {blocks.map(block => <div className="alignment-block" key={block.offset}>
                <div className="alignment-column-label">Alignment columns {block.offset + 1}–{block.offset + block.source.length}</div>
                <SequenceRow protein={source} sequence={block.source} start={block.sourceStart} end={block.sourceEnd} />
                <div className="alignment-sequence-row alignment-marker-row" aria-label="Identity markers"><span /><span /><code className="alignment-residues">{[...block.markers].map((marker, index) => <span key={index} className={`aa-residue ${marker === '|' ? 'alignment-identity' : ''}`}>{marker}</span>)}</code><span /></div>
                <SequenceRow protein={target} sequence={block.target} start={block.targetStart} end={block.targetEnd} />
            </div>)}
        </div>
        <p className="collection-note">{result.parameters.algorithm}; {result.parameters.matrix}; gap open {result.parameters.gap_open}, extend {result.parameters.gap_extend}; terminal gaps {result.parameters.terminal_gaps}. Identity: {result.identities}/{result.alignment_length} alignment columns, including gaps.</p>
    </section>
}
