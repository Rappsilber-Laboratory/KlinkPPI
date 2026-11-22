// Example inputs shared by the search form and the tutorial.
// Human TP53: a well-studied hub with evidence in every source.
export const SINGLE_EXAMPLE = {
    id: 'P04637',
    type: 'UniProtKB',
    species: 'Homo sapiens',
    taxId: '9606',
    databases: ['String', 'IntAct', 'BioGrid', 'Corum', 'HuRI', 'Reactome', 'Signor', 'ComplexPortal'],
}

// Shareable link that fills in the single example and runs it (see SearchSection's inputsFromUrl).
export function singleExamplePath() {
    const params = new URLSearchParams({ id: SINGLE_EXAMPLE.id, type: SINGLE_EXAMPLE.type, species: SINGLE_EXAMPLE.species, tax: SINGLE_EXAMPLE.taxId, run: '1' })
    SINGLE_EXAMPLE.databases.forEach(db => params.append('db', db))
    return `/?${params}`
}
