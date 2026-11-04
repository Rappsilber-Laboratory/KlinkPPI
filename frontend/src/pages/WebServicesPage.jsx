import { API, useLimits } from '../lib/routing'
import Link from '../components/Link'
import { GITHUB_URL } from '../lib/site'
import { PageShell, Toc } from './PageShell'

const GROUPS = [
    ['General', [
        ['GET', '/health', 'Service status. Add ?details=true for data readiness.', '/health'],
        ['GET', '/limits', 'Input limits, result retention, queue and fair-use limits.', '/limits'],
        ['GET', '/species/search', 'Supported species matching q, with the sources covering each (q, limit ≤ 10).', '/species/search?q=human'],
        ['GET', '/supported-organisms/summary', 'Organism coverage of every source (used by the coverage plots).', '/supported-organisms/summary'],
        ['GET', '/gene-name/search', 'UniProt candidates for a gene symbol in one species (query, tax_id or species_name).', '/gene-name/search?query=TP53&tax_id=9606'],
        ['GET', '/openapi.json', 'Machine-readable OpenAPI 3 description of every endpoint and schema.', '/openapi.json'],
        ['GET', '/downloads/klinkppi_template.py', 'The Python template script, preconfigured for this server.', '/downloads/klinkppi_template.py'],
        ['GET', '/downloads/klinkppi.py', 'Full Python client library (requests only).', '/downloads/klinkppi.py'],
    ]],
    ['Single-protein search', [
        ['GET', '/search', 'Interactions of one protein in the selected sources. Parameters: id_value, from_database (UniProtKB | GeneID | Ensembl | Gene_Name), tax_id or species_name (optional), selected_databases (repeatable). Returns [ {Input}, {output: [ {Source: [ {info}, {rows} ]} ]} ].', '/search?id_value=P04637&from_database=UniProtKB&tax_id=9606&selected_databases=IntAct&selected_databases=String'],
        ['POST', '/mitab', 'Convert a /search result to PSI-MI TAB 2.8-compatible text. Body: {results, selected_databases, selected_columns, uniprot_id, tax_id}.'],
        ['POST', '/parquet', 'Same body as /mitab; returns an Apache Parquet file with all source-specific columns.'],
    ]],
    ['Collection analysis (asynchronous jobs)', [
        ['POST', '/collection/jobs', 'Start a job: {identifiers (≤ MAX), species_name, tax_id, selected_databases, input_type: auto|UniProtKB|Gene_Name|Ensembl|GeneID, mode: induced|expanded}. Returns the job with job_id; status "resolving".'],
        ['GET', '/collection/jobs/{job_id}', 'Job status (resolving → awaiting_selection → running → completed | failed | cancelled), progress, per-source status, ID resolution, warnings, and the network graph when completed.', '/collection/jobs/example'],
        ['POST', '/collection/jobs/{job_id}/run', 'Confirm the mapping and start the analysis: {choices: {input: accession | null}} for every ambiguous input (null skips it).'],
        ['POST', '/collection/jobs/{job_id}/rerun', 'Query the sources again with the same inputs and mappings (completed jobs).'],
        ['POST', '/collection/jobs/{job_id}/cancel', 'Cancel a resolving, waiting or running job.'],
        ['GET', '/collection/jobs/{job_id}/analysis', 'Filtered network plus statistics. Filters: databases (repeatable), evidence_type (all|direct|functional|predicted), method, score_database, min_score, min_publications.', '/collection/jobs/example/analysis?evidence_type=direct'],
    ]],
    ['Follow-ups for pairs without interaction evidence (induced jobs)', [
        ['GET', '/collection/jobs/{job_id}/shared-go', 'GO terms annotated to both proteins: source, target (accessions).'],
        ['GET', '/collection/jobs/{job_id}/sequence', 'UniProt sequence and FASTA of one input protein: accession.'],
        ['POST', '/collection/jobs/{job_id}/alignments', 'Queue a global pairwise alignment: {source, target}. Returns alignment_id.'],
        ['GET', '/collection/jobs/{job_id}/alignments/{alignment_id}', 'Alignment progress and result (score, identity, aligned sequences, parameters).'],
        ['GET', '/collection/embedding-models', 'Available protein language models and the meaning of every score.', '/collection/embedding-models'],
        ['POST', '/collection/jobs/{job_id}/embeddings', 'Queue an embedding comparison: {source, target, models: [..]} (≤ 3 models).'],
        ['GET', '/collection/jobs/{job_id}/embeddings/{embedding_id}', 'Queue position, progress, runtime and scores with explanations.'],
    ]],
    ['Complete-species export (API only)', [
        ['POST', '/species-ppi/jobs', 'Start a whole-proteome export: {tax_id or species_name, selected_databases}.'],
        ['GET', '/species-ppi/jobs/{job_id}', 'Per-source progress and pair counts.'],
        ['POST', '/species-ppi/jobs/{job_id}/cancel', 'Cancel the export.'],
        ['POST', '/species-ppi/jobs/{job_id}/mitab', 'Download PSI-MI TAB: {selected_databases, selected_columns}.'],
        ['POST', '/species-ppi/jobs/{job_id}/parquet', 'Download Parquet: {selected_databases, selected_columns}.'],
    ]],
]

const SECTIONS = [['template', 'Template script'], ['endpoints', 'All web services'], ['conventions', 'Conventions']]

export default function WebServicesPage() {
    const limits = useLimits()
    const base = `${window.location.origin}${API}`
    return <PageShell title="Web services & Python API" lead="Every analysis in the web interface is available as a REST web service with JSON output. No registration or API key is needed.">
        <Toc sections={SECTIONS} />

        <section id="template">
            <h2>Template script</h2>
            <p>The template is a single Python file that needs only <code>requests</code>. It calls the limits, species, single-search, MITAB, collection, statistics, shared-GO, alignment and (optionally) embedding services, parses their output and writes TSV files. Each service is a short function that is easy to adapt to your own pipeline.</p>
            <p className="doc-actions">
                <a className="doc-button" href={`${API}/downloads/klinkppi_template.py`} download>Download klinkppi_template.py</a>
                <a className="doc-button secondary" href={`${API}/downloads/klinkppi.py`} download>Download the full client library (klinkppi.py)</a>
                <a className="doc-button secondary" href={GITHUB_URL} target="_blank" rel="noreferrer">More examples on GitHub ↗</a>
            </p>
            <pre>{`pip install requests
python klinkppi_template.py                     # all steps with the example data
python klinkppi_template.py --steps collection --ids TP53 MDM2 CDKN1A --species "Homo sapiens"
python klinkppi_template.py --help`}</pre>
            <p>The downloaded script already points to <code>{base}</code>. Minimal example without the template:</p>
            <pre>{`import requests, time
API = "${base}"
job = requests.post(f"{API}/collection/jobs", json={
    "identifiers": ["TP53", "MDM2", "CDKN1A"], "species_name": "Homo sapiens",
    "selected_databases": ["IntAct", "BioGrid"], "mode": "induced"}).json()
while (job := requests.get(f"{API}/collection/jobs/{job['job_id']}").json())["status"] == "resolving":
    time.sleep(2)
requests.post(f"{API}/collection/jobs/{job['job_id']}/run", json={"choices": {}})
while (job := requests.get(f"{API}/collection/jobs/{job['job_id']}").json())["status"] == "running":
    time.sleep(2)
for edge in job["graph"]["edges"]:
    print(edge["source"], edge["target"], sorted({ev["database"] for ev in edge["evidence"]}))`}</pre>
        </section>

        <section id="endpoints">
            <h2>All web services</h2>
            <p>Base URL: <code>{base}</code>. Collections accept up to {limits.collection_max_identifiers} identifiers; job results are kept for {limits.result_retention_days} days. The permanent example job <code>{limits.example_job_id}</code> can be used for testing.</p>
            {GROUPS.map(([group, rows]) => <div key={group} className="doc-endpoint-group">
                <h3>{group}</h3>
                <table className="doc-endpoints"><thead><tr><th>Method</th><th>URL</th><th>Description</th></tr></thead>
                    <tbody>{rows.map(([method, path, description, example]) => <tr key={method + path}>
                        <td><span className={`doc-method ${method.toLowerCase()}`}>{method}</span></td>
                        <td><code>{base}{path}</code>{example && <div><a href={`${API}${example}`} target="_blank" rel="noreferrer">try it</a></div>}</td>
                        <td>{description.replace('≤ MAX', `≤ ${limits.collection_max_identifiers}`)}</td>
                    </tr>)}</tbody></table>
            </div>)}
        </section>

        <section id="conventions">
            <h2>Conventions</h2>
            <ul>
                <li>Requests and responses are JSON (UTF-8), except the file downloads.</li>
                <li>Long analyses are asynchronous: submit, keep the returned <code>job_id</code>, and poll the status URL every 1–5 seconds. The same job opens in the browser at <code>{window.location.origin}{import.meta.env.BASE_URL.replace(/\/+$/, '')}/results/&lt;job_id&gt;</code>.</li>
                <li>Errors use HTTP status codes with a <code>detail</code> message: 400 invalid input, 404 unknown or expired job, 429 queue full or fair-use limit (honour the <code>Retry-After</code> header), 502 an external source failed.</li>
                <li>Please run large batches sequentially. Contact us for bulk use (see <Link to="/privacy">contact</Link>).</li>
            </ul>
        </section>
    </PageShell>
}
