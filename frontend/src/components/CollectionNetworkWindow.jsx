import { useEffect, useRef, useState } from 'react'
import { download } from '../collection/exports'
import CollectionNetworkCanvas from './CollectionNetworkCanvas'

export default function CollectionNetworkWindow({ graph, title, appearance, onAppearanceChange, onClose, initialPositions }) {
    const dialog = useRef(null)
    const network = useRef(null)
    const [error, setError] = useState('')
    const [exporting, setExporting] = useState(false)
    const [detail, setDetail] = useState(null)
    const [search, setSearch] = useState('')
    const [separated, setSeparated] = useState(false)

    useEffect(() => {
        const element = dialog.current
        const previousFocus = document.activeElement
        const previousOverflow = document.body.style.overflow
        element.showModal()
        document.body.style.overflow = 'hidden'
        return () => {
            element.close()
            document.body.style.overflow = previousOverflow
            previousFocus?.focus()
        }
    }, [])

    const exportImage = async format => {
        setError('')
        setExporting(true)
        try {
            if (format === 'svg') download(network.current.svg(), 'klinkppi-network.svg', 'image/svg+xml')
            else download(await network.current.png(), 'klinkppi-network.png', 'image/png')
        } catch (err) { setError(`Image export failed: ${err.message}`) }
        finally { setExporting(false) }
    }
    const focus = event => {
        event.preventDefault()
        setError(network.current.focus(search) ? '' : `No visible node matches '${search}'.`)
    }

    return <dialog ref={dialog} className="collection-shell network-image-dialog" aria-labelledby="network-window-title" onCancel={onClose} onClose={event => { if (!event.currentTarget.open) onClose() }}>
        <header className="network-window-heading"><div><span className="collection-eyebrow">NETWORK IMAGE STUDIO</span><h2 id="network-window-title">{title}</h2></div><button type="button" onClick={onClose} autoFocus>Close full window</button></header>
        <div className="network-window-workspace">
            <aside className="network-controls network-window-controls" aria-label="Network image appearance">
                <h3>Appearance</h3>
                <label>Background color<input type="color" value={appearance.backgroundColor || '#10231d'} onChange={event => onAppearanceChange('backgroundColor', event.target.value)} /></label>
                <label>Font color<input type="color" value={appearance.labelColor || '#ffffff'} onChange={event => onAppearanceChange('labelColor', event.target.value)} /></label>
                <label>Node size <output>{Math.round(appearance.nodeScale * 100)}%</output><input type="range" min="0.5" max="2.5" step="0.1" value={appearance.nodeScale} onChange={event => onAppearanceChange('nodeScale', Number(event.target.value))} /></label>
                <label className="source-toggle"><input type="checkbox" checked={appearance.labels} onChange={event => onAppearanceChange('labels', event.target.checked)} />Gene labels</label>
                <label className="source-toggle"><input type="checkbox" checked={appearance.colors} onChange={event => onAppearanceChange('colors', event.target.checked)} />Database edge colors</label>
                <label>Edge width<select value={appearance.widthMode} onChange={event => onAppearanceChange('widthMode', event.target.value)}><option value="consensus">Database consensus count</option><option value="score">Relative source scores</option><option value="off">Uniform width</option></select></label>
                <h3>Save image</h3>
                <div className="collection-actions"><button type="button" disabled={exporting || !graph.nodes.length} onClick={() => exportImage('png')}>Download PNG</button><button type="button" disabled={exporting || !graph.nodes.length} onClick={() => exportImage('svg')}>Download SVG</button></div>
                <p className="collection-note">PNG saves the current view. SVG includes the whole network. Appearance changes also apply to the results page.</p>
                {error && <p className="collection-error" role="alert">{error}</p>}
            </aside>
            <div className="network-window-main">
                <div className="network-toolbar"><form onSubmit={focus}><input aria-label="Find protein in full window" placeholder="Find gene / UniProt…" value={search} onChange={event => setSearch(event.target.value)} /><button type="submit" disabled={!graph.nodes.length}>Find</button></form><div><button type="button" onClick={() => network.current.fit()}>Fit whole network</button><button type="button" onClick={() => network.current.rearrange()}>Rearrange</button><button type="button" onClick={() => setSeparated(network.current.separate())}>{separated ? 'Compact communities' : 'Separate communities'}</button></div></div>
                <div className="network-meta"><span>{graph.nodes.length.toLocaleString()} nodes</span><span>{graph.edges.length.toLocaleString()} edges</span><span>Drag nodes · Scroll to zoom</span></div>
                <div className="network-canvas"><CollectionNetworkCanvas ref={network} graph={graph} {...appearance} initialPositions={initialPositions} onPick={setDetail} /></div>
                <p className="network-window-detail" aria-live="polite">{detail ? detail.kind === 'node' ? `${detail.data.gene} · ${detail.data.id}` : `${detail.data.source} ↔ ${detail.data.target} · ${detail.data.databases.join(', ')}` : 'Click a protein or interaction to inspect it.'}</p>
            </div>
        </div>
    </dialog>
}
