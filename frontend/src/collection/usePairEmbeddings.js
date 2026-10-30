import { useEffect, useRef, useState } from 'react'

const API = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`

export function usePairEmbeddings(jobId) {
    const [models, setModels] = useState([])
    const [selected, setSelected] = useState(['esm2-8m'])
    const [catalogError, setCatalogError] = useState('')
    const [tasks, setTasks] = useState({})
    const [active, setActive] = useState(null)
    const [open, setOpen] = useState({})
    const posting = useRef(null)
    useEffect(() => {
        const abort = new AbortController()
        fetch(`${API}/collection/embedding-models`, { signal: abort.signal }).then(async response => {
            const data = await response.json()
            if (!response.ok) throw new Error('Could not load embedding models. Reload to retry.')
            setModels(data.models)
        }).catch(error => { if (error.name !== 'AbortError') setCatalogError(error.message) })
        return () => { abort.abort(); posting.current?.abort() }
    }, [])
    useEffect(() => {
        if (!active?.embedding_id) return
        const abort = new AbortController()
        const timer = setTimeout(async () => {
            try {
                const response = await fetch(`${API}/collection/jobs/${encodeURIComponent(jobId)}/embeddings/${encodeURIComponent(active.embedding_id)}`, { signal: abort.signal })
                const data = await response.json()
                if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not refresh embedding progress.')
                setTasks(current => ({ ...current, [active.key]: data }))
                setActive(['completed', 'failed'].includes(data.status) ? null : { ...data, key: active.key })
            } catch (error) {
                if (error.name !== 'AbortError') {
                    setTasks(current => ({ ...current, [active.key]: { status: 'failed', error: error.message } }))
                    setActive(null)
                }
            }
        }, 1000)
        return () => { clearTimeout(timer); abort.abort() }
    }, [active, jobId])
    const compute = async pair => {
        if (posting.current || active || selected.length !== 1 || !models.length) return
        const abort = new AbortController()
        posting.current = abort
        const selection = [...selected]
        setActive({ key: pair.key })
        setOpen(current => ({ ...current, [pair.key]: true }))
        setTasks(current => ({ ...current, [pair.key]: { status: 'queued', models: selection, progress: 'Starting comparison…' } }))
        try {
            const response = await fetch(`${API}/collection/jobs/${encodeURIComponent(jobId)}/embeddings`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: abort.signal,
                body: JSON.stringify({ source: pair.source.id, target: pair.target.id, models: selection }),
            })
            const data = await response.json()
            if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not start embedding comparison.')
            setTasks(current => ({ ...current, [pair.key]: data }))
            setActive(['completed', 'failed'].includes(data.status) ? null : { ...data, key: pair.key })
        } catch (error) {
            if (error.name !== 'AbortError') {
                setTasks(current => ({ ...current, [pair.key]: { status: 'failed', error: error.message } }))
                setActive(null)
            }
        } finally { posting.current = null }
    }
    return { models, selected, setSelected, catalogError, tasks, active, open, compute,
        toggle: key => setOpen(current => ({ ...current, [key]: !current[key] })) }
}

