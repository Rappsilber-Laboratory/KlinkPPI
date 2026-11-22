import { useLimits } from '../lib/routing'
import Link from '../components/Link'
import { PageShell, Toc } from './PageShell'

const SECTIONS = [
    ['overview', 'What KlinkPPI does'],
    ['input-formats', 'Input formats'],
    ['single-results', 'Single entry search results'],
    ['mapping-review', 'Batch and PPI search: identifier review'],
    ['collection-results', 'Batch and PPI search: network and statistics'],
    ['ppi-results', 'PPI search: your requested pairs'],
    ['uniprot', 'UniProt links and protein function'],
    ['evidence-types', 'Evidence categories'],
    ['unknown-pairs', 'Pairs with no interaction found'],
    ['scores', 'Source scores'],
    ['exports', 'Downloads and file formats'],
    ['limits', 'Limits, result links and fair use'],
    ['faq', 'Troubleshooting'],
]

const SCORES = [
    ['STRING', 'Combined score and channel scores (experiments, databases, co-expression, text mining, neighbourhood, fusion, phylogenetic profile)', '0–1', 'Confidence that two proteins are functionally associated, which is not the same as physical binding. ≥0.7 is STRING’s “high confidence”.'],
    ['IntAct / MINT', 'MI score', '0–1', 'Combines the number of publications, detection methods and interaction types. Higher means better-supported experimental evidence.'],
    ['BioGRID', 'Confidence score', 'study-specific', 'Reported only by some high-throughput studies, on that study’s own scale. Missing values are shown as “–”.'],
    ['HIPPIE', 'HIPPIE score', '0–1', 'Reliability derived from the number of studies, methods and organisms. ≥0.73 is HIPPIE’s high-confidence threshold.'],
    ['SIGNOR', 'SIGNOR score', '0–1', 'Curated confidence for a causal (regulator → target) relationship, with effect and mechanism.'],
    ['hu.MAP 3.0', 'ML probability', '0–1', 'Machine-learning probability that the pair co-complexes, predicted from mass-spectrometry data.'],
    ['Predictomes', 'SPOC score, KIRC score, unique contacts', 'model-specific', 'AlphaFold-multimer based structural predictions; higher SPOC means a more confident predicted interface.'],
    ['CORUM / Complex Portal', 'complex membership', '–', 'Both proteins are subunits of the same curated complex. Co-membership does not prove direct contact.'],
    ['HuRI', 'binary yeast two-hybrid pair', '–', 'Systematic binary screen; presence of a pair is the evidence. Absence is common because screens are incomplete.'],
    ['Reactome', 'pathway / reaction context', '–', 'Proteins share a curated reaction or complex in a pathway (functional evidence).'],
]

export default function HelpPage() {
    const limits = useLimits()
    return <PageShell title="Help" lead="How to prepare your input, run each analysis and interpret every result KlinkPPI returns.">
        <Toc sections={SECTIONS} />

        <section id="overview">
            <h2>What KlinkPPI does</h2>
            <p>KlinkPPI analyses <strong>your own proteins</strong>. You submit one protein or a list of genes/proteins; KlinkPPI maps the identifiers to UniProt, collects interaction evidence for exactly those proteins from twelve resources (STRING, IntAct, BioGRID, CORUM, HuRI, Predictomes, Complex Portal, Reactome, SIGNOR, HIPPIE, hu.MAP 3.0 and MINT), and then analyses it: it builds an evidence network, compares how the sources agree, computes network statistics and, for protein pairs without any reported interaction, offers sequence, Gene Ontology and protein-language-model comparisons.</p>
            <ul>
                <li><strong>Single entry search</strong> — every interaction of one protein, source by source, with an overlap summary and standard exports.</li>
                <li><strong>Batch search</strong> — a network for 2–{limits.collection_max_identifiers} proteins, with identifier review, filters, statistics and follow-up analyses of unconnected pairs.</li>
                <li><strong>PPI search</strong> — up to {limits.ppi_max_pairs} specific protein pairs (e.g. <code>TP53-MDM2</code>): known pairs show their evidence; pairs without evidence get the same follow-up analyses as in batch search.</li>
                <li><strong>UniProt</strong> — every protein links to its UniProt entry; <em>Show function</em> displays the entry's Function section with its PubMed citations.</li>
                <li><strong>Web services</strong> — every analysis is also available over HTTP; see <Link to="/web-services">Web services &amp; Python API</Link>.</li>
            </ul>
            <p>No registration is needed and nothing has to be installed. New users should start with the <Link to="/tutorial">tutorial</Link>.</p>
        </section>

        <section id="input-formats">
            <h2>Input formats</h2>
            <h3>Identifiers</h3>
            <table><thead><tr><th>Type</th><th>Example</th><th>Notes</th></tr></thead><tbody>
                <tr><td>UniProtKB accession / entry name</td><td><code>P04637</code>, <code>P53_HUMAN</code></td><td>Isoforms (<code>P04637-2</code>) are analysed as their canonical entry.</td></tr>
                <tr><td>Gene symbol</td><td><code>TP53</code></td><td>Matched against UniProt within the chosen species; several matches are shown for you to choose from.</td></tr>
                <tr><td>Ensembl gene / transcript / protein</td><td><code>ENSG00000141510</code></td><td>Version suffixes such as <code>.20</code> are ignored.</td></tr>
                <tr><td>NCBI GeneID</td><td><code>7157</code></td><td>Plain numbers are read as GeneIDs in “Detect each ID” mode.</td></tr>
            </tbody></table>
            <h3>Species</h3>
            <p>Batch and PPI searches need a species, chosen from the suggestions; single entry searches work without one, but adding it improves gene-name matching. Each source covers different organisms, and sources that do not cover the chosen species are disabled.</p>
            <h3>Batch search lists and files</h3>
            <p>Paste identifiers, one per line, or upload a <code>.txt</code>, <code>.csv</code> or <code>.tsv</code> file (UTF-8, under 1 MB) with <strong>one identifier per line, no header and no extra columns</strong>. Duplicates are merged, and up to {limits.collection_max_identifiers} distinct identifiers are accepted. <a href={`${import.meta.env.BASE_URL}examples/collection_example.txt`} download>Download the example file</a> to check the format.</p>
            <pre>{'P04217\nP00751\nTP53\nENSG00000012048\n7157'}</pre>
            <p>Use an explicit identifier type when a gene symbol looks like another format (for example, a symbol that is all digits).</p>
            <h3>PPI search lists and files</h3>
            <p>One protein pair per line, no header: <code>A-B</code>, or the two identifiers separated by a tab, comma, semicolon or space. Use a separator other than a hyphen when an identifier contains a hyphen (isoforms such as <code>P04637-2</code>, or symbols such as <code>HLA-A</code>); a hyphen-only line is accepted only when exactly one split gives two identifiers. <code>A-B</code> and <code>B-A</code> are merged and self-pairs are skipped. Up to {limits.ppi_max_pairs} distinct pairs over {limits.ppi_max_proteins} distinct proteins.</p>
            <pre>{'TP53-MDM2\nBRCA1\tBARD1\nP04637-2,Q00987'}</pre>
            <h3>Expanded networks</h3>
            <p>Batch and PPI searches can add first neighbors of your proteins. Choose how many neighbors to show per protein (default {limits.default_neighbor_limit}, up to {limits.max_neighbor_limit}); PPI searches can also count neighbors per PPI, putting neighbors shared by both proteins first. Neighbors are ranked by the number of supporting databases, then publications, then evidence records. Induced networks are unchanged.</p>
        </section>

        <section id="single-results">
            <h2>Single entry search results</h2>
            <p>To see an example, click <strong>View example result</strong> on the search page: it searches human TP53 (P04637) in eight sources. <strong>Load example</strong> only fills in the form.</p>
            <ol>
                <li><strong>Search summary</strong> — the UniProt accession, taxonomy ID and species that were searched, followed by the protein’s UniProt function (see <a href="#uniprot">UniProt links</a>). Check this first if you entered a gene name or another ID type.</li>
                <li><strong>Shared Interaction Log</strong> — how many partners each source reports, and the exact overlaps between sources. A partner reported by several independent sources is better supported than one reported by a single source. Some sources integrate others (HIPPIE includes BioGRID, IntAct and MINT; STRING imports curated databases), so agreement between them is not independent evidence.</li>
                <li><strong>One card per source</strong> — each partner with that source’s evidence: detection method, interaction type, publications (linked to PubMed), scores (see <a href="#scores">source scores</a>) and a link to the source record. Every partner has a <strong>UniProt ↗</strong> link and a <strong>Show function</strong> button. A card that says “No data found” means the source has no interaction for this protein. It does <em>not</em> show that the proteins do not interact. “Organism not supported” means the source does not cover the species.</li>
                <li><strong>Download Results</strong> — export the selected sources and columns as PSI-MI TAB 2.8-compatible text or Parquet (see <a href="#exports">downloads</a>).</li>
            </ol>
            <p>Scores from different sources measure different things and are on different scales, so do not compare them directly or add them up.</p>
        </section>

        <section id="mapping-review">
            <h2>Batch and PPI search: identifier review</h2>
            <p>Before any interaction is queried, KlinkPPI shows how every input maps to UniProt in the chosen species:</p>
            <ul>
                <li><strong>resolved</strong> — exactly one entry; used automatically.</li>
                <li><strong>ambiguous</strong> — several entries (reviewed Swiss-Prot entries are listed first). Choose the intended one or <em>Skip this ID</em>; the analysis cannot start until you decide.</li>
                <li><strong>unresolved</strong> — no entry in this species. It is kept as an isolated, highlighted (yellow-green) node so that missing inputs stay visible. No interactions are invented for it.</li>
            </ul>
            <p>If several inputs map to the same protein, they become one node; the mapping report keeps the original inputs. In PPI search, a pair with an unresolved or skipped protein is reported as <em>ID unresolved / skipped</em>, and a pair whose two inputs map to the same protein as <em>Same protein</em>.</p>
        </section>

        <section id="collection-results">
            <h2>Batch and PPI search: network and statistics</h2>
            <p>Batch and PPI search share the same network, filters, statistics and exports. In PPI search the network contains all proteins named in your pairs, and your requested pairs are drawn as thicker edges.</p>
            <h3>Network modes</h3>
            <ul>
                <li><strong>Induced</strong> — only interactions <em>between</em> your proteins. Use it to ask “how connected is my set?”. It also lists the pairs with no interaction evidence.</li>
                <li><strong>Expanded</strong> — adds the direct first neighbours of your proteins (gray edges). Neighbour–neighbour edges are not queried, so neighbours’ degrees are not meaningful. You choose how many neighbours to show: per protein (default {limits.default_neighbor_limit}, up to {limits.max_neighbor_limit}), or in PPI search per PPI. Neighbours are ranked by the number of supporting databases, then publications, then evidence records; per PPI, neighbours of both proteins come first. Lower-ranked neighbours are hidden, and the result says how many. Input proteins and the edges between them are always kept.</li>
            </ul>
            <h3>Reading the network</h3>
            <ul>
                <li>Nodes are proteins: input proteins are coral, first neighbours are coloured by network community, and unresolved inputs are yellow-green.</li>
                <li>Edge colour shows the source database (or a mix of sources). Edge width shows either <em>consensus</em> (the number of source databases reporting the pair, not the number of experiments) or a relative score cue.</li>
                <li>Click a node or edge to see every piece of evidence: source, category, methods, publications and raw scores, with links to the source records.</li>
                <li>Filters (source, evidence category, method, minimum publications, minimum score for one source) change the view and the statistics, but not the stored result. A score threshold applies only to evidence from the chosen source, so a pair can stay visible through other evidence.</li>
            </ul>
            <h3>Statistics (for the filtered network)</h3>
            <table><thead><tr><th>Statistic</th><th>Meaning</th></tr></thead><tbody>
                <tr><td>Nodes / edges</td><td>Proteins and distinct protein pairs currently shown.</td></tr>
                <tr><td>Pairs unique to a database vs shared</td><td>How many pairs only one source reports, and how many several sources report. A large unique share is typical: sources cover different experiment types.</td></tr>
                <tr><td>Jaccard overlap</td><td>Shared pairs divided by the union of pairs, for each pair of sources (0 = no overlap, 1 = identical). “N/A” means both sources are empty.</td></tr>
                <tr><td>Degree / hubs</td><td>Number of partners per protein in the shown network. In expanded mode, only input proteins have complete degrees.</td></tr>
                <tr><td>Connected components</td><td>Groups of proteins linked by any path. Many small components suggest your set is not one connected module.</td></tr>
                <tr><td>Mean local clustering</td><td>Average fraction of a protein’s partners that also interact with each other (isolated proteins count as 0). Higher values indicate complex-like modules.</td></tr>
                <tr><td>Score distributions</td><td>Histograms of each source’s raw scores. Compare within a source only.</td></tr>
                <tr><td>Shared / database-only interactors</td><td>Proteins supported by several sources, or by only one.</td></tr>
            </tbody></table>
            <h3>Protein inspector</h3>
            <p>Click a protein to see its UniProt accession, species and degree, with a UniProt link and <strong>Show function</strong>.</p>
            <h3>Coverage notes</h3>
            <p>Warnings report sources that failed or timed out, identifiers that could not be mapped, and whether a size limit made the result partial. Read them before drawing conclusions from missing edges.</p>
        </section>

        <section id="ppi-results">
            <h2>PPI search: your requested pairs</h2>
            <p>The <strong>Your PPIs</strong> table lists every requested pair in your input order, with one status:</p>
            <table><thead><tr><th>Status</th><th>Meaning</th></tr></thead><tbody>
                <tr><td>Known</td><td>At least one selected source reports the pair. The row shows the sources, the number of evidence records, the evidence categories and up to five PubMed links. Click a source to open its record of the pair: STRING, SIGNOR, HIPPIE, Complex Portal and CORUM link the pair or complex itself; BioGRID, IntAct, Predictomes, hu.MAP and Reactome link a protein page; MINT links its home page. <em>Show in network</em> opens every evidence record with its link in the inspector.</td></tr>
                <tr><td>Hidden by filters</td><td>The pair has evidence, but the current filters remove all of it.</td></tr>
                <tr><td>No evidence found</td><td>No selected source reports the pair. These pairs appear again under <a href="#unknown-pairs">Pairs with no interaction found</a> with GO, alignment and embedding comparisons. Missing evidence does not show that the proteins do not interact.</td></tr>
                <tr><td>ID unresolved / skipped</td><td>One of the two identifiers was not mapped to UniProt, or you skipped it.</td></tr>
                <tr><td>Same protein</td><td>Both identifiers map to the same UniProt entry; self-interactions are not analysed.</td></tr>
            </tbody></table>
            <p><strong>Download MITAB (requested pairs)</strong> exports only the evidence of your pairs, with the current filters. The <strong>MITAB</strong> button under the network exports every edge of the filtered network.</p>
        </section>

        <section id="uniprot">
            <h2>UniProt links and protein function</h2>
            <p>In every search, each protein has a <strong>UniProt ↗</strong> link to its entry and a <strong>Show function</strong> button. The function is the <em>Function</em> section shown first on a UniProt entry page, read from the entry’s JSON record, with the cited PubMed articles linked. The protein you searched in single entry search shows its function automatically.</p>
            <p>STRING reports gene names instead of UniProt accessions, so for STRING partners KlinkPPI shows the best match for that gene in the species (a reviewed Swiss-Prot entry when available) and says so. Function lookups are cached for an hour. An entry without a Function section shows “UniProt reports no function annotation”.</p>
        </section>

        <section id="evidence-types">
            <h2>Evidence categories</h2>
            <ul>
                <li><strong>Direct</strong> — experimentally detected physical interactions (IntAct, MINT, BioGRID physical, HuRI, HIPPIE, direct SIGNOR relations).</li>
                <li><strong>Functional</strong> — association without proof of contact: STRING associations, CORUM/Complex Portal co-membership, Reactome reactions, BioGRID genetic interactions and indirect SIGNOR relations.</li>
                <li><strong>Predicted</strong> — computational predictions (Predictomes, hu.MAP 3.0 and predicted complexes).</li>
            </ul>
            <p>SIGNOR relations are directed (regulator → target, with an effect such as up-regulation). This is shown in the evidence details, although the topology statistics treat the network as undirected.</p>
        </section>

        <section id="unknown-pairs">
            <h2>Pairs with no interaction found</h2>
            <p>In an induced batch search, KlinkPPI lists every pair of your resolved proteins that has no interaction evidence in the selected sources, before any display filter. In PPI search (induced or expanded), it lists your requested pairs that have no evidence. These pairs are candidates for further study. Missing evidence often reflects incomplete coverage and does not show that the proteins do not interact. The list offers four follow-ups:</p>
            <ul>
                <li><strong>Check GO</strong> — Gene Ontology terms annotated to <em>both</em> proteins in UniProt (exact term IDs, no ancestor expansion), with category and evidence code. Shared process or component terms suggest the proteins act in the same context.</li>
                <li><strong>Align seqs</strong> — global Needleman–Wunsch/Gotoh alignment (BLOSUM62, gap open 10, extend 0.5). <em>Percent identity</em> = identical residues / all alignment columns including gaps. High identity points to paralogues, which can share partners or form hetero-oligomers. The residue view colours amino acids by property.</li>
                <li><strong>Embedding</strong> — compares the two sequences with a protein language model (ESM-2, ESM-1b, ESM-1v or ESM-C). Each score has an explanation in the expanded panel. Cosine-type similarities are higher when the representations are closer, and distances are lower when they are closer. Use them to rank pairs within your set; there is no universal threshold.</li>
                <li><strong>BLAST / Foldseek / UniProt</strong> — send a protein to NCBI BLASTP, open its AlphaFold entry for a Foldseek structure search, or open its UniProt entry and read its function. External sites open only when you click.</li>
            </ul>
            <p><strong>Sequence, GO or embedding similarity does not show that two proteins interact.</strong> Use these results to prioritise pairs for experiments.</p>
        </section>

        <section id="scores">
            <h2>Source scores</h2>
            <table><thead><tr><th>Source</th><th>Score</th><th>Range</th><th>Interpretation</th></tr></thead>
                <tbody>{SCORES.map(([source, score, range, meaning]) => <tr key={source}><td>{source}</td><td>{score}</td><td>{range}</td><td>{meaning}</td></tr>)}</tbody></table>
        </section>

        <section id="exports">
            <h2>Downloads and file formats</h2>
            <table><thead><tr><th>Format</th><th>Where</th><th>Contents</th></tr></thead><tbody>
                <tr><td>PSI-MI TAB 2.8-compatible (.mitab.txt)</td><td>Single entry, batch and PPI search</td><td>Standard columns (interactors, taxa, methods, types, publications, source database, confidence). Source-specific scores are prefixed, e.g. <code>string-combined-score:0.99</code>. Batch and PPI exports contain one row per evidence record of the filtered network; PPI searches can also export only the requested pairs.</td></tr>
                <tr><td>Parquet</td><td>Single entry search</td><td>All source-specific columns; read with pandas, R arrow or Polars.</td></tr>
                <tr><td>GraphML, SIF, Cytoscape CX, JSON</td><td>Batch and PPI search</td><td>The filtered network for Cytoscape or Gephi. JSON keeps all evidence and analysis settings, while SIF keeps topology only.</td></tr>
                <tr><td>SVG / PNG</td><td>Batch and PPI search</td><td>Publication-ready network image; use <em>Open full window</em> to adjust its appearance.</td></tr>
                <tr><td>Analysis PDF</td><td>Batch and PPI search</td><td>Network image, settings, mapping report, coverage notes and statistics.</td></tr>
                <tr><td>PLM scores (TSV)</td><td>Pairs with no interaction</td><td>Columns <code>metric</code> and <code>value</code> for one protein pair.</td></tr>
            </tbody></table>
        </section>

        <section id="limits">
            <h2>Limits, result links and fair use</h2>
            <ul>
                <li>Batch searches accept up to {limits.collection_max_identifiers} distinct identifiers; PPI searches up to {limits.ppi_max_pairs} distinct pairs over {limits.ppi_max_proteins} distinct proteins. Networks are capped at {Number(limits.collection_max_edges || 50000).toLocaleString()} interacting pairs.</li>
                <li>Every batch result has a private link (<code>/results/&lt;id&gt;</code>), and every PPI result one at <code>/ppi-results/&lt;id&gt;</code>, that you get as soon as you submit. It shows whether the job is queued, running or finished, and you can bookmark it. Results are kept for <strong>{limits.result_retention_days} days</strong> and then deleted. The link contains a random 128-bit identifier, so only people you share it with can open it.</li>
                <li>Each visitor can run up to {limits.max_active_collection_jobs_per_client} batch or PPI analyses at the same time. Embedding comparisons use a shared model queue, and the web page shows your position in it. Too many requests in a short time return “Too many requests”; wait for the time shown, then retry.</li>
            </ul>
        </section>

        <section id="faq">
            <h2>Troubleshooting</h2>
            <dl>
                <dt>A source shows an error or “failed”.</dt><dd>The external source did not respond in time. The other sources are still valid. Use <em>Rerun</em> on the batch or PPI result, or search again later.</dd>
                <dt>My PPI line is rejected.</dt><dd>A line like <code>HLA-A-HLA-B</code> can be split in several ways. Separate the two IDs with a tab, comma or space instead of a hyphen.</dd>
                <dt>The expanded network shows fewer neighbours than the sources report.</dt><dd>Only the top neighbours per protein or per PPI are shown. Increase <em>Neighbors to show</em> and run the search again.</dd>
                <dt>My gene name returns several entries.</dt><dd>Choose the reviewed (Swiss-Prot) entry unless you need a specific unreviewed isoform or fragment.</dd>
                <dt>The result link says “expired”.</dt><dd>Results are deleted {limits.result_retention_days} days after submission. Submit the list again; the form keeps your previous inputs when you open an existing link.</dd>
                <dt>Embedding comparison is slow.</dt><dd>Larger models (650M parameters) take longer, and requests are queued fairly between users. ESM-2 8M or 35M give a fast first look.</dd>
            </dl>
        </section>
    </PageShell>
}
