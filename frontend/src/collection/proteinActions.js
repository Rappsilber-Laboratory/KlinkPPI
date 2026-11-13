export function blastFields(protein, species) {
    return {
        PAGE: 'Proteins', PROGRAM: 'blastp', CMD: 'Web', PAGE_TYPE: 'BlastSearch',
        QUERY: protein.fasta,
        JOB_TITLE: `KlinkPPI: ${protein.gene} (${protein.accession}) — ${species}`,
    }
}

export function postBlast(target, protein, species) {
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = 'https://blast.ncbi.nlm.nih.gov/Blast.cgi'
    form.target = target
    form.hidden = true
    for (const [name, value] of Object.entries(blastFields(protein, species))) {
        const input = document.createElement('input')
        input.type = 'hidden'
        input.name = name
        input.value = value
        form.append(input)
    }
    document.body.append(form)
    try { form.submit() } finally { form.remove() }
}
