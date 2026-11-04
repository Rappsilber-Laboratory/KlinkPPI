import './pages.css'

export function PageShell({ title, lead, children }) {
    return <article className="doc-page app-frame mx-auto">
        <header className="doc-header">
            <h1>{title}</h1>
            {lead && <p className="doc-lead">{lead}</p>}
        </header>
        {children}
    </article>
}

export function Toc({ sections }) {
    return <nav className="doc-toc" aria-label="On this page">
        <strong>On this page</strong>
        <ol>{sections.map(([id, label]) => <li key={id}><a href={`#${id}`}>{label}</a></li>)}</ol>
    </nav>
}
