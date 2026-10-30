export const RESIDUE_GROUPS = [
    { key: 'hydrophobic', label: 'Hydrophobic', residues: 'AVILMFWY' },
    { key: 'polar', label: 'Polar, uncharged', residues: 'STNQC' },
    { key: 'acidic', label: 'Acidic', residues: 'DE' },
    { key: 'basic', label: 'Basic', residues: 'KRH' },
    { key: 'glycine', label: 'Glycine', residues: 'G' },
    { key: 'proline', label: 'Proline', residues: 'P' },
    { key: 'other', label: 'Other / ambiguous', residues: 'BZXUO*' },
    { key: 'gap', label: 'Gap', residues: '-' },
]

export function residueGroup(residue) {
    return RESIDUE_GROUPS.find(group => group.residues.includes(residue)) || RESIDUE_GROUPS.find(group => group.key === 'other')
}

export function alignmentBlocks(source, target, size = 60) {
    const blocks = []
    let sourcePosition = 0, targetPosition = 0
    for (let offset = 0; offset < source.length; offset += size) {
        const left = source.slice(offset, offset + size)
        const right = target.slice(offset, offset + size)
        const leftCount = left.replaceAll('-', '').length, rightCount = right.replaceAll('-', '').length
        blocks.push({
            offset, source: left, target: right,
            sourceStart: leftCount ? sourcePosition + 1 : null, sourceEnd: leftCount ? sourcePosition + leftCount : null,
            targetStart: rightCount ? targetPosition + 1 : null, targetEnd: rightCount ? targetPosition + rightCount : null,
            markers: [...left].map((residue, index) => residue === '-' || right[index] === '-' ? ' ' : residue === right[index] ? '|' : '·').join(''),
        })
        sourcePosition += leftCount
        targetPosition += rightCount
    }
    return blocks
}
