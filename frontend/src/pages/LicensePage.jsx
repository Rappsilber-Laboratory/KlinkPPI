import { PageShell } from './PageShell'
import { GITHUB_URL } from '../lib/site'

// Verify each source's current terms before publication; links point to the
// sources' own licence / terms pages.
const SOURCES = [
    ['STRING', 'https://string-db.org/cgi/access'],
    ['IntAct', 'https://www.ebi.ac.uk/intact/'],
    ['BioGRID', 'https://wiki.thebiogrid.org/doku.php/terms_and_conditions'],
    ['CORUM', 'https://mips.helmholtz-muenchen.de/corum/'],
    ['HuRI', 'http://www.interactome-atlas.org/'],
    ['Predictomes', 'https://predictomes.org/'],
    ['Complex Portal', 'https://www.ebi.ac.uk/complexportal/'],
    ['Reactome', 'https://reactome.org/license'],
    ['SIGNOR', 'https://signor.uniroma2.it/'],
    ['HIPPIE', 'https://cbdm-01.zdv.uni-mainz.de/~mschaefer/hippie/'],
    ['hu.MAP 3.0', 'https://humap3.proteincomplexes.org/'],
    ['MINT', 'https://mint.bio.uniroma2.it/'],
    ['UniProt (ID mapping, sequences, GO annotations)', 'https://www.uniprot.org/help/license'],
]

export default function LicensePage() {
    return <PageShell title="License" lead="KlinkPPI is free and open to all users, including commercial users, without registration.">
        <section>
            <h2>Web server and software</h2>
            <p>The KlinkPPI web server, its source code, the Python template script and the client library are released under the <strong>MIT License</strong>. You may use, copy, modify and redistribute them, provided the copyright notice is kept. The source code is available on <a href={GITHUB_URL} target="_blank" rel="noreferrer">GitHub</a>.</p>
            <pre className="doc-license">{`MIT License — Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following
conditions: The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.`}</pre>
        </section>
        <section>
            <h2>Results and source data</h2>
            <p>KlinkPPI’s own analyses (networks, statistics, alignments and embedding scores) can be used freely. Interaction records keep the licence and citation requirements of the database they come from. Every record in KlinkPPI is labelled with its source, so please cite the sources you use together with KlinkPPI.</p>
            <table><thead><tr><th>Source</th><th>Licence / terms of use</th></tr></thead>
                <tbody>{SOURCES.map(([name, url]) => <tr key={name}><td>{name}</td><td><a href={url} target="_blank" rel="noreferrer">{url.replace(/^https?:\/\//, '')}</a></td></tr>)}</tbody></table>
        </section>
        <section>
            <h2>No warranty</h2>
            <p>KlinkPPI is a research tool. It is not intended for clinical diagnosis or therapy decisions.</p>
        </section>
    </PageShell>
}
