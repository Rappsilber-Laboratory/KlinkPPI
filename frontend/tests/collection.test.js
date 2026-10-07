import test from 'node:test'
import assert from 'node:assert/strict'
import { computeStatistics, filterGraph, parseIdentifiers } from '../src/collection/analysis.js'
import { cx, graphML, sif, xml } from '../src/collection/exports.js'

const ev = (db, score = null, publications = [], methods = [], type = 'direct') => ({ database: db, score, score_name: score == null ? null : 'score', publications, methods, type })
const nodes = [
    { id: 'A', gene: 'Alpha', input: true, species: 'Homo sapiens' },
    { id: 'B', gene: 'Beta', input: true, species: 'Homo sapiens' },
    { id: 'C', gene: 'Gamma', input: false, species: 'Homo sapiens' },
    { id: 'unknown:0', gene: 'missing', input: true, unresolved: true, species: 'Homo sapiens' },
]
const rawGraph = { nodes, edges: [
    { id: 'e0', source: 'A', target: 'B', evidence: [ev('IntAct', .8, ['123', '456'], ['two hybrid']), ev('BioGrid', null, ['123'])] },
    { id: 'e1', source: 'A', target: 'C', expanded: true, evidence: [ev('IntAct', .5, ['789'], ['two hybrid'])] },
    { id: 'e2', source: 'B', target: 'C', expanded: true, evidence: [ev('BioGrid', null, [], ['affinity capture'])] },
] }
const defaults = { databases: ['IntAct', 'BioGrid'], type: 'all', method: '', scoreDatabase: '', minScore: '', minPublications: 0 }

test('headerless lists handle quotes, BOM, CRLF, duplicates and reject multi-column data', () => {
    assert.deepEqual(parseIdentifiers('\uFEFF"TP53"\r\nP04637\r\nTP53\r\n'), { ids: ['TP53', 'P04637'], duplicates: 1 })
    assert.throws(() => parseIdentifiers('gene,score\nTP53,0.8'), /one identifier per line/)
    assert.throws(() => parseIdentifiers(' \n'), /at least one/)
    assert.throws(() => parseIdentifiers(Array.from({ length: 201 }, (_, i) => `gene${i}`).join('\n')), /200/)
})

test('filters preserve isolated inputs and remove orphan neighbors', () => {
    const graph = filterGraph(rawGraph, { ...defaults, databases: [] })
    assert.equal(graph.edges.length, 0)
    assert.deepEqual(graph.nodes.map(n => n.id), ['A', 'B', 'unknown:0'])
})

test('score filtering respects source scales, retaining independent evidence', () => {
    const graph = filterGraph(rawGraph, { ...defaults, scoreDatabase: 'IntAct', minScore: .9 })
    assert.equal(graph.edges.length, 2)
    assert.deepEqual(graph.edges[0].databases, ['BioGrid'])
    assert.equal(graph.edges.some(e => e.id === 'e1'), false)
})

test('publication filter counts distinct IDs across evidence, methods filter evidence', () => {
    const graph = filterGraph(rawGraph, { ...defaults, minPublications: 2 })
    assert.equal(graph.edges.length, 1)
    assert.deepEqual(graph.edges[0].publications, ['123', '456'])
    const method = filterGraph(rawGraph, { ...defaults, method: 'hybrid' })
    assert.equal(method.edges.length, 2)
    assert.deepEqual(method.edges[0].databases, ['IntAct'])
})

test('triangle with an isolated input has exact degree, components, clustering, overlap and scores', () => {
    const graph = filterGraph(rawGraph, defaults)
    const stats = computeStatistics(graph, defaults.databases)
    assert.equal(stats.nodes, 4)
    assert.equal(stats.edges, 3)
    assert.deepEqual(stats.components, [3, 1])
    assert.equal(stats.clustering, .75)
    assert.deepEqual(stats.degrees.map(n => n.degree), [2, 2, 2, 0])
    assert.deepEqual(stats.jaccard[0], { a: 'IntAct', b: 'BioGrid', intersection: 1, union: 3, value: 1 / 3 })
    assert.deepEqual(stats.byDatabase.map(d => [d.unique, d.shared]), [[1, 1], [1, 1]])
    assert.equal(stats.scores[0].median, .65)
    assert.equal(stats.scores[0].bins.reduce((sum, n) => sum + n, 0), 2)
    assert.equal(stats.sharedInteractors.length, 3)
})

test('empty Jaccard denominator is unknown, not perfect overlap', () => {
    const stats = computeStatistics(filterGraph(rawGraph, { ...defaults, databases: [] }), defaults.databases)
    assert.equal(stats.jaccard[0].value, null)
    assert.equal(stats.clustering, 0)
})

test('GraphML escapes identifiers and preserves evidence; SIF retains isolated nodes', () => {
    const graph = filterGraph(rawGraph, defaults)
    const content = graphML({ ...graph, nodes: [{ ...graph.nodes[0], gene: 'A&B<"' }, ...graph.nodes.slice(1)] })
    assert.match(content, /A&amp;B&lt;&quot;/)
    assert.match(content, /<data key="evidence">/)
    assert.match(sif(graph), /unknown:0\n/)
    assert.equal(xml("<&'"), '&lt;&amp;&apos;')
})

test('CX has numeric node references, typed source lists, and valid framing', () => {
    const graph = filterGraph(rawGraph, defaults)
    const content = cx(graph, { species: 'Homo sapiens', mode: 'expanded', warnings: [] })
    assert.equal(content[0].numberVerification[0].longNumber, 281474976710655)
    const cxNodes = content.find(item => item.nodes).nodes
    const cxEdges = content.find(item => item.edges).edges
    const ids = new Set(cxNodes.map(n => n['@id']))
    for (const edge of cxEdges) { assert.ok(ids.has(edge.s)); assert.ok(ids.has(edge.t)) }
    assert.equal(content.at(-1).status[0].success, true)
    assert.equal(content.find(item => item.edgeAttributes).edgeAttributes[0].d, 'list_of_string')
})
