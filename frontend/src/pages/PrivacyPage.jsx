import { useLimits } from '../lib/routing'
import { PageShell } from './PageShell'

export default function PrivacyPage() {
    const limits = useLimits()
    return <PageShell title="Privacy & cookies" lead="No login, no registration, no e-mail address, no cookies and no tracking.">
        <section>
            <h2>Cookies and tracking</h2>
            <p>KlinkPPI sets <strong>no cookies</strong>, neither permanent nor session cookies, and uses no analytics, advertising or tracking. It loads no third-party scripts, fonts or images: everything is served from this server. Because no cookies are used, no cookie consent form is needed.</p>
        </section>
        <section>
            <h2>Your submitted data</h2>
            <ul>
                <li>Submitted identifiers and results are stored only on this server, in a job database, and are deleted automatically <strong>{limits.result_retention_days} days</strong> after submission. The read-only tutorial example is kept permanently.</li>
                <li>Each result is reachable only through its private link, which contains a random 128-bit identifier. KlinkPPI never lists or publishes jobs; only you and the people you share the link with can open a result.</li>
                <li>Single searches are not stored; their results exist only in your browser tab.</li>
                <li>Your IP address is kept briefly in memory to enforce fair-use limits. It is never written to the job database.</li>
            </ul>
        </section>
        <section>
            <h2>External services</h2>
            <p>To answer a query, the KlinkPPI <em>server</em> sends protein identifiers (never anything about you) to the public APIs of UniProt, Ensembl, STRING, IntAct/PSICQUIC (IntAct, MINT, Reactome), SIGNOR and HIPPIE. Optional actions open third-party sites only when you click them: <em>Search BLASTP</em> sends the protein sequence to NCBI BLAST, and <em>Find similar structures</em> opens the AlphaFold database.</p>
        </section>
        <section>
            <h2>Contact</h2>
            <p>Questions, bug reports or requests to delete a result before it expires: <a href="https://www.rappsilberlab.org/" target="_blank" rel="noreferrer">Rappsilber Lab</a>.</p>
        </section>
    </PageShell>
}
