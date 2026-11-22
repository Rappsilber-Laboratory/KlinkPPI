import { appPath, useLimits } from '../lib/routing'
import { singleExamplePath } from '../lib/examples'
import Link from '../components/Link'
import { PageShell, Toc } from './PageShell'

const SECTIONS = [
    ['example-outputs', 'Sample outputs'],
    ['tutorial-single', '1. One protein: single entry search'],
    ['tutorial-collection', '2. Your protein list: batch search'],
    ['tutorial-ppi', '3. Specific pairs: PPI search'],
    ['tutorial-unknown', '4. Follow up pairs without evidence'],
    ['tutorial-own', '5. Run your own analysis'],
    ['tutorial-api', '6. Automate it with Python'],
]

const singleExampleLink = () => appPath(singleExamplePath())

export default function TutorialPage() {
    const limits = useLimits()
    const exampleResult = `/results/${limits.example_job_id}`
    const ppiExampleResult = `/ppi-results/${limits.ppi_example_job_id}`
    return <PageShell title="Tutorial" lead="A 15-minute walk-through with the example data. Every sample output below is a live result page that behaves exactly like your own results.">
        <Toc sections={SECTIONS} />

        <section id="example-outputs">
            <h2>Sample outputs</h2>
            <div className="doc-cards">
                <Link className="doc-card" to={exampleResult}><strong>Example batch search result →</strong><span>14 human DNA-repair proteins (BRCA1/2, PALB2, RAD51 and its paralogues, Fanconi anaemia proteins) from all 12 sources: network, filters, statistics, exports and follow-ups of the 21 pairs without evidence. Always available and read-only.</span></Link>
                <Link className="doc-card" to={ppiExampleResult}><strong>Example PPI search result →</strong><span>Seven human protein pairs from the same module (e.g. BRCA1–BARD1, TP53–MDM2, RAD51C–DMC1) checked in all 12 sources: known pairs with their evidence, pairs without evidence with their follow-ups, and MITAB downloads. Always available and read-only.</span></Link>
                <a className="doc-card" href={singleExampleLink()}><strong>Example single entry search →</strong><span>Human TP53 (P04637) searched live in 8 sources, with its UniProt function, the overlap log, per-source evidence and MITAB/Parquet downloads.</span></a>
                <a className="doc-card" href={`${import.meta.env.BASE_URL}examples/collection_example.txt`} download><strong>Example batch input file ↓</strong><span>The identifier list used for the example batch search, in the accepted file format.</span></a>
                <a className="doc-card" href={`${import.meta.env.BASE_URL}examples/ppi_example.txt`} download><strong>Example PPI input file ↓</strong><span>The pair list used for the example PPI search: one pair per line, written as A-B.</span></a>
            </div>
        </section>

        <section id="tutorial-single">
            <h2>1. One protein: single entry search</h2>
            <ol>
                <li>On the <Link to="/">search page</Link>, stay on <em>Single entry search</em> and click <strong>Load example</strong>. This fills in UniProtKB <code>P04637</code> (TP53), <em>Homo sapiens</em> (taxonomy 9606) and eight sources.</li>
                <li>Click <strong>Search</strong>. All sources are queried in parallel; the status dot next to each source shows when it has finished or failed.</li>
                <li>Read the <strong>Search summary</strong> to confirm the protein. Its UniProt <strong>Function</strong> is shown directly below, with links to the cited PubMed articles; <strong>UniProt ↗</strong> opens the full entry.</li>
                <li>Read the <strong>Shared Interaction Log</strong>: partners reported by several sources are better supported (<Link to="/help#single-results">how to interpret this</Link>).</li>
                <li>Scroll through the source cards. Every interactor has a <strong>UniProt ↗</strong> link and a <strong>Show function</strong> button, so you can read what a partner does without leaving the page. Publications link to PubMed, and scores are explained in the <Link to="/help#scores">score table</Link>.</li>
                <li>In <strong>Download Results</strong>, choose sources and columns and download PSI-MI TAB (MITAB) or Parquet.</li>
            </ol>
            <p>Or skip the form: click <strong>View example result</strong> on the search page, or <a href={singleExampleLink()}>open the live single entry search example</a>. Single entry searches are not stored, so the example is searched live each time.</p>
        </section>

        <section id="tutorial-collection">
            <h2>2. Your protein list: batch search</h2>
            <p>Open the <Link to={exampleResult}>example batch search result</Link> and follow along:</p>
            <ol>
                <li><strong>Result link</strong> — the box at the top is the bookmarkable link of the result. Your own analyses get one as soon as you submit them, so you can close the page and come back.</li>
                <li><strong>Your interaction network</strong> — drag nodes, zoom, search for a gene, and click an edge to see every source, method, publication and score behind it. Switch <em>edge width</em> to <em>consensus</em> to see which pairs several sources agree on.</li>
                <li><strong>Protein inspector</strong> — click a protein to see its degree, open its UniProt entry or click <strong>Show function</strong> to read its UniProt function.</li>
                <li><strong>Filters</strong> — keep only <em>direct</em> physical evidence, or require at least one publication, and watch the network and statistics update. <Link to="/help#evidence-types">What the evidence categories mean</Link>.</li>
                <li><strong>Evidence, overlap and topology</strong> — compare sources (pairs per database, Jaccard overlap), find hubs and components, and read the coverage notes. <Link to="/help#collection-results">How to interpret the statistics</Link>.</li>
                <li><strong>Downloads</strong> — export <strong>MITAB</strong> (PSI-MI TAB, one row per evidence record, with the current filters), SVG/PNG, GraphML, SIF, Cytoscape CX, JSON or the analysis PDF.</li>
            </ol>
        </section>

        <section id="tutorial-ppi">
            <h2>3. Specific pairs: PPI search</h2>
            <p>Use PPI search when you already know which pairs you want to check, for example hits from a screen or predicted complexes. Open the <Link to={ppiExampleResult}>example PPI search result</Link> and follow along:</p>
            <ol>
                <li><strong>Your PPIs</strong> — every requested pair is listed with its status: <em>Known</em> (with the sources, number of evidence records, evidence categories and PubMed links), <em>No evidence found</em>, <em>Hidden by filters</em> (known, but all of its evidence is filtered out) or <em>ID unresolved / skipped</em>. Each protein has a UniProt link and <strong>Show function</strong>.</li>
                <li><strong>Network</strong> — the induced network connects all proteins of your pairs; your requested pairs are drawn as thicker edges. Filters, statistics and image exports work as in batch search.</li>
                <li><strong>MITAB downloads</strong> — <strong>Download MITAB (requested pairs)</strong> exports only the evidence of your pairs; the <strong>MITAB</strong> button under the network exports the whole filtered network.</li>
                <li><strong>Pairs with no interaction found</strong> — the requested pairs without evidence (in the example RAD51C–DMC1 and BARD1–XRCC3) get the same follow-ups as in batch search; see the next step.</li>
            </ol>
            <p>To try it yourself, open <Link to="/">PPI search</Link> and click <strong>Load example</strong>. Write one pair per line as <code>TP53-MDM2</code>, or separate the two IDs with a tab, comma or space when an ID contains a hyphen (<Link to="/help#input-formats">PPI input format</Link>).</p>
        </section>

        <section id="tutorial-unknown">
            <h2>4. Follow up pairs without evidence</h2>
            <ol>
                <li>In the example batch or PPI result, scroll to <strong>Pairs with no interaction found</strong>. In batch search these are all pairs of your proteins that no selected source connects (most involve DMC1, the meiosis-specific RAD51 paralogue); in PPI search they are your requested pairs without evidence.</li>
                <li>Click <strong>Check GO</strong> on a pair to list Gene Ontology terms that both proteins share.</li>
                <li>Click <strong>Align seqs</strong> for a global alignment with score and percent identity, then expand it to see the residues. Compare RAD51C–DMC1 (paralogues: score 241, 25.6% identity) with BARD1–XRCC3 (score −115).</li>
                <li>In the <strong>Embedding</strong> column, choose a model (start with <em>esm2-8m</em> for speed) and click <strong>Compute distances</strong>. Expand the scores to read what each metric means, and download them as TSV.</li>
                <li>Each protein also offers <strong>Search BLASTP ↗</strong>, <strong>Copy FASTA</strong>, <strong>Find similar structures ↗</strong>, <strong>UniProt ↗</strong> and <strong>Show function</strong>.</li>
            </ol>
            <p>None of these similarities proves an interaction; use them to rank candidate pairs (<Link to="/help#unknown-pairs">details</Link>).</p>
        </section>

        <section id="tutorial-own">
            <h2>5. Run your own analysis</h2>
            <ol>
                <li>Open <Link to="/">Batch search</Link> and paste up to {limits.collection_max_identifiers} identifiers, or open <Link to="/">PPI search</Link> and paste up to {limits.ppi_max_pairs} pairs. You can also upload a file. Choose a species from the suggestions. <strong>Load example</strong> fills in the tutorial data.</li>
                <li>Pick the sources and the network mode: <em>induced</em> shows interactions only among your proteins; <em>expanded</em> adds their first neighbours. In expanded mode, enter how many neighbours to show (default {limits.default_neighbor_limit}, up to {limits.max_neighbor_limit}) per protein, or in PPI search per PPI. The best-supported neighbours are kept (<Link to="/help#input-formats">ranking</Link>).</li>
                <li>Click <strong>Resolve collection IDs</strong>, review ambiguous mappings, then <strong>Run</strong>. Copy the result link shown at the top; results are kept for {limits.result_retention_days} days.</li>
            </ol>
        </section>

        <section id="tutorial-api">
            <h2>6. Automate it with Python</h2>
            <p>The <Link to="/web-services#template">template script</Link> runs the same single entry search, batch search, PPI search, statistics, MITAB export and follow-ups from Python and writes the results as TSV files:</p>
            <pre>{'pip install requests\npython klinkppi_template.py                    # runs the example data\npython klinkppi_template.py --ids TP53 MDM2 BRCA1 --species "Homo sapiens"\npython klinkppi_template.py --steps ppi --pairs TP53-MDM2 BRCA1-BARD1 --species "Homo sapiens"'}</pre>
            <p>All web services, including <code>POST /collection/ppi-jobs</code>, MITAB export and the UniProt function lookup, are listed on the <Link to="/web-services">Web services</Link> page.</p>
        </section>
    </PageShell>
}
