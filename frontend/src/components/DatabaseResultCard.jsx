import { useState } from 'react'
import DBHeader from './DBHeader'

export default function DatabaseResultCard({ className = '', children, ...header }) {
    const [hidden, setHidden] = useState(false)
    return <section className={`database-result-card bg-white shadow-md mb-8 overflow-hidden ${className}`}>
        <DBHeader {...header} hidden={hidden} onToggle={() => setHidden(value => !value)} />
        {!hidden && <div className="database-result-body">{children}</div>}
    </section>
}
