import { appPath, useLimits } from '../lib/routing'
import { SINGLE_EXAMPLE } from '../lib/examples'
import Link from '../components/Link'
import { PageShell, Toc } from './PageShell'

const SECTIONS = [
    ['example-outputs', 'Sample outputs'],
    ['tutorial-single', '1. One protein: single search'],
    ['tutorial-collection', '2. Your protein list: collection analysis'],
    ['tutorial-unknown', '3. Follow up pairs without evidence'],
    ['tutorial-own', '4. Run your own analysis'],
    ['tutorial-api', '5. Automate it with the Python template'],
]

const singleExampleLink = () => {
    const params = new URLSearchParams({ id: SINGLE_EXAMPLE.id, type: SINGLE_EXAMPLE.type, species: SINGLE_EXAMPLE.species, tax: SINGLE_EXAMPLE.taxId, run: '1' })
    SINGLE_EXAMPLE.databases.forEach(db => params.append('db', db))
    return appPath(`/?${params}`)
}

export default function TutorialPage() {
    const limits = useLimits()
    const exampleResult = `/results/${limits.example_job_id}`
    return <PageShell title="Tutorial" lead="A 10-minute walk-through with the example data. Every sample output below is a live result page that behaves exactly like your own results.">
        <Toc sections={SECTIONS} />

        <section id="example-outputs">
            <h2>Sample outputs</h2>
            <div className="doc-cards">
                <Link className="doc-card" to={exampleResult}><strong>Example collection result →</strong><span>10 human proteins, induced network from 8 sources: network, filters, statistics, exports and unknown-pair follow-ups. Always available and read-only.</span></Link>
                <a className="doc-card" href={singleExampleLink()}><strong>Example single search →</strong><span>Human TP53 (P04637) searched live in 8 sources, with the overlap log, per-source evidence and MITAB/Parquet downloads.</span></a>
                <a className="doc-card" href={`${import.meta.env.BASE_URL}examples/collection_example.txt`} download><strong>Example input file ↓</strong><span>The identifier list used for the example collection, in the accepted file format.</span></a>
            </div>
        </section>

        <section id="tutorial-single">
            <h2>1. One protein: single search</h2>
            <ol>
                <li>On the <Link to="/">search page</Link>, stay on <em>Single searches</em> and click <strong>Load example</strong>. This fills in UniProtKB <code>P04637</code> (TP53), <em>Homo sapiens</em> (taxonomy 9606) and eight sources.</li>
                <li>Click <strong>Search</strong>. All sources are queried in parallel; the status dot next to each source shows when it has finished or failed.</li>
                <li>Read the <strong>Input summary</strong> to confirm the protein, then the <strong>Shared Interaction Log</strong>: partners reported by several sources are better supported (<Link to="/help#single-results">how to interpret this</Link>).</li>
                <li>Scroll through the source cards. Publications link to PubMed, and scores are explained in the <Link to="/help#scores">score table</Link>.</li>
                <li>In <strong>Download Results</strong>, choose sources and columns and download PSI-MI TAB or Parquet.</li>
            </ol>
            <p>Or skip the form: <a href={singleExampleLink()}>open the live single-search example</a>.</p>
        </section>

        <section id="tutorial-collection">
            <h2>2. Your protein list: collection analysis</h2>
            <p>Open the <Link to={exampleResult}>example collection result</Link> and follow along:</p>
            <ol>
                <li><strong>Result link</strong> — the box at the top is the bookmarkable link of the result. Your own analyses get one as soon as you submit them, so you can close the page and come back.</li>
                <li><strong>Your interaction network</strong> — drag nodes, zoom, search for a gene, and click an edge to see every source, method, publication and score behind it. Switch <em>edge width</em> to <em>consensus</em> to see which pairs several sources agree on.</li>
                <li><strong>Filters</strong> — keep only <em>direct</em> physical evidence, or require at least one publication, and watch the network and statistics update. <Link to="/help#evidence-types">What the evidence categories mean</Link>.</li>
                <li><strong>Evidence, overlap and topology</strong> — compare sources (pairs per database, Jaccard overlap), find hubs and components, and read the coverage notes. <Link to="/help#collection-results">How to interpret the statistics</Link>.</li>
                <li><strong>Downloads</strong> — export SVG/PNG, GraphML, SIF, Cytoscape CX, JSON or the analysis PDF.</li>
            </ol>
        </section>

        <section id="tutorial-unknown">
            <h2>3. Follow up pairs without evidence</h2>
            <ol>
                <li>In the example result, scroll to <strong>Pairs with no interaction found</strong>. These are pairs of your proteins that no selected source connects.</li>
                <li>Click <strong>Check GO</strong> on a pair to list Gene Ontology terms that both proteins share.</li>
                <li>Click <strong>Align seqs</strong> for a global alignment with score and percent identity, then expand it to see the residues.</li>
                <li>In the <strong>Embedding</strong> column, choose a model (start with <em>esm2-8m</em> for speed) and click <strong>Compute distances</strong>. Expand the scores to read what each metric means, and download them as TSV.</li>
            </ol>
            <p>None of these similarities proves an interaction; use them to rank candidate pairs (<Link to="/help#unknown-pairs">details</Link>).</p>
        </section>

        <section id="tutorial-own">
            <h2>4. Run your own analysis</h2>
            <ol>
                <li>Open <Link to="/">Collection search</Link>, choose a species from the suggestions and paste up to {limits.collection_max_identifiers} identifiers, or upload a one-column file. <strong>Load example</strong> fills in the tutorial data.</li>
                <li>Pick the sources and the network mode (<em>induced</em> = only among your proteins; <em>expanded</em> = plus their first neighbours).</li>
                <li>Click <strong>Resolve collection IDs</strong>, review ambiguous mappings, then <strong>Run</strong>. Copy the result link shown at the top; results are kept for {limits.result_retention_days} days.</li>
            </ol>
        </section>

        <section id="tutorial-api">
            <h2>5. Automate it with the Python template</h2>
            <p>The <Link to="/web-services#template">template script</Link> runs the same single search, collection analysis, statistics and follow-ups from Python and writes the results as TSV files:</p>
            <pre>{'pip install requests\npython klinkppi_template.py                    # runs the example data\npython klinkppi_template.py --ids TP53 MDM2 BRCA1 --species "Homo sapiens"'}</pre>
        </section>
    </PageShell>
}
