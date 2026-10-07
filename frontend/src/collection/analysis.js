export const DATABASES = ['String', 'IntAct', 'BioGrid', 'Corum', 'HuRI', 'Predictomes', 'ComplexPortal', 'Reactome', 'Signor', 'Hippie', 'HuMap', 'Mint']
export const COLORS = { String: '#0284c7', IntAct: '#c026d3', BioGrid: '#059669', Corum: '#d97706', HuRI: '#e11d48', Predictomes: '#4f46e5', ComplexPortal: '#0891b2', Reactome: '#65a30d', Signor: '#dc2626', Hippie: '#0d9488', HuMap: '#7c3aed', Mint: '#db2777' }
export const LABELS = { String: 'STRING', BioGrid: 'BioGRID', Corum: 'CORUM', Signor: 'SIGNOR', Hippie: 'HIPPIE', HuMap: 'hu.MAP', ComplexPortal: 'Complex Portal' }

// Flat, headerless lists; reject multi-column input instead of guessing a column.
export function parseIdentifiers(text) {
    const result = []
    for (const line of text.replace(/^\uFEFF/, '').split(/\r?\n/)) {
        if (!line.trim()) continue
        let cells = line.includes('\t') ? line.split('\t') : line.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/)
        cells = cells.map(value => value.trim().replace(/^"(.*)"$/, '$1').replace(/""/g, '"')).filter(Boolean)
        if (cells.length > 1) throw new Error('Use one identifier per line, without a header or extra columns.')
        if (cells[0]) result.push(cells[0])
    }
    const ids = [...new Set(result)]
    if (!ids.length) throw new Error('Paste or upload at least one identifier.')
    if (ids.length > 200) throw new Error('Use up to 200 distinct identifiers per collection.')
    return { ids, duplicates: result.length - ids.length }
}

export function filterGraph(graph, filters) {
    const edges = []
    const activeNodes = new Set(graph.nodes.filter(n => n.input).map(n => n.id))
    for (const edge of graph.edges) {
        const evidence = edge.evidence.filter(ev => {
            if (!filters.databases.includes(ev.database)) return false
            if (filters.type !== 'all' && filters.type !== ev.type) return false
            if (filters.method && !ev.methods.some(method => method.toLowerCase().includes(filters.method.toLowerCase()))) return false
            // Raw thresholds are applied only within a chosen database's scale.
            if (filters.scoreDatabase && ev.database === filters.scoreDatabase && filters.minScore !== '' && (ev.score == null || ev.score < Number(filters.minScore))) return false
            return true
        })
        const publications = [...new Set(evidence.flatMap(ev => ev.publications))]
        if (!evidence.length || publications.length < Number(filters.minPublications || 0)) continue
        activeNodes.add(edge.source)
        activeNodes.add(edge.target)
        edges.push({ ...edge, evidence, publications, databases: [...new Set(evidence.map(ev => ev.database))] })
    }
    return { ...graph, nodes: graph.nodes.filter(n => activeNodes.has(n.id)), edges }
}

export function computeStatistics(graph, databases) {
    const adj = new Map(graph.nodes.map(n => [n.id, new Set()]))
    const nodeDBs = new Map(graph.nodes.map(n => [n.id, new Set()]))
    const dbEdges = Object.fromEntries(databases.map(db => [db, new Set()]))
    const distributions = Object.fromEntries(databases.map(db => [db, {}]))
    for (const edge of graph.edges) {
        adj.get(edge.source).add(edge.target)
        adj.get(edge.target).add(edge.source)
        for (const db of edge.databases) {
            dbEdges[db]?.add(edge.id)
            nodeDBs.get(edge.source).add(db)
            nodeDBs.get(edge.target).add(db)
        }
        for (const ev of edge.evidence) {
            const sourceScores = ev.scores || (ev.score == null ? {} : { [ev.score_name || 'score']: ev.score })
            for (const [name, score] of Object.entries(sourceScores)) {
                const series = distributions[ev.database][name] ||= []
                series.push(score)
            }
        }
    }
    const visited = new Set(), components = []
    for (const id of adj.keys()) {
        if (visited.has(id)) continue
        const stack = [id]
        visited.add(id)
        let size = 0
        while (stack.length) {
            const current = stack.pop()
            size++
            for (const neighbor of adj.get(current)) if (!visited.has(neighbor)) { visited.add(neighbor); stack.push(neighbor) }
        }
        components.push(size)
    }
    // Orient by degree, then ID: enumerate each triangle once, using sparse sets.
    const before = (a, b) => adj.get(a).size < adj.get(b).size || (adj.get(a).size === adj.get(b).size && a < b)
    const forward = new Map([...adj].map(([id, ns]) => [id, new Set([...ns].filter(n => before(id, n)))]))
    const triangles = new Map([...adj.keys()].map(id => [id, 0]))
    for (const [a, neighbors] of forward) for (const b of neighbors) {
        for (const c of forward.get(b)) if (neighbors.has(c)) {
            for (const id of [a, b, c]) triangles.set(id, triangles.get(id) + 1)
        }
    }
    const degrees = graph.nodes.map(node => {
        const degree = adj.get(node.id).size
        return { ...node, degree, clustering: degree < 2 ? 0 : 2 * triangles.get(node.id) / (degree * (degree - 1)), databases: [...nodeDBs.get(node.id)] }
    }).sort((a, b) => b.degree - a.degree || a.id.localeCompare(b.id))
    const byDatabase = databases.map(database => ({ database, edges: dbEdges[database].size,
        unique: graph.edges.filter(edge => edge.databases.length === 1 && edge.databases[0] === database).length,
        shared: graph.edges.filter(edge => edge.databases.length > 1 && edge.databases.includes(database)).length }))
    const jaccard = []
    databases.forEach((a, index) => databases.slice(index + 1).forEach(b => {
        let intersection = 0
        for (const id of dbEdges[a]) if (dbEdges[b].has(id)) intersection++
        const union = dbEdges[a].size + dbEdges[b].size - intersection
        jaccard.push({ a, b, intersection, union, value: union ? intersection / union : null })
    }))
    const scores = []
    for (const [database, series] of Object.entries(distributions)) for (const [name, values] of Object.entries(series)) {
        values.sort((a, b) => a - b)
        const min = values[0], max = values.at(-1), bins = Array(8).fill(0)
        for (const value of values) bins[max === min ? 0 : Math.min(7, Math.floor((value - min) / (max - min) * 8))]++
        scores.push({ database, name, count: values.length, min, max,
            median: (values[Math.floor((values.length - 1) / 2)] + values[Math.floor(values.length / 2)]) / 2,
            mean: values.reduce((sum, value) => sum + value, 0) / values.length, bins })
    }
    return { nodes: graph.nodes.length, edges: graph.edges.length, components: components.sort((a, b) => b - a),
        clustering: degrees.length ? degrees.reduce((sum, n) => sum + n.clustering, 0) / degrees.length : 0,
        degrees, hubs: degrees.filter(n => n.degree).slice(0, 10), byDatabase, jaccard, scores,
        sharedInteractors: degrees.filter(n => n.databases.length > 1).slice(0, 10),
        databaseOnlyInteractors: Object.fromEntries(databases.map(db => [db, degrees.filter(n => n.databases.length === 1 && n.databases[0] === db).slice(0, 10)])) }
}
