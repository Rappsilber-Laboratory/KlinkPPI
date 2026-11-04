// Minimal client-side routing (History API) and shared server limits.
// The <Link> component lives in components/Link.jsx.
import { useEffect, useState } from 'react'

export const API = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`
const BASE = import.meta.env.BASE_URL.replace(/\/+$/, '')
const EVENT = 'klinkppi:navigate'

export const appPath = path => `${BASE}${path}`

export function currentPath() {
    const path = window.location.pathname
    return (BASE && path.startsWith(BASE) ? path.slice(BASE.length) : path) || '/'
}

export function navigate(path, { replace = false } = {}) {
    const target = appPath(path)
    if (target === window.location.pathname + window.location.search + window.location.hash) return
    window.history[replace ? 'replaceState' : 'pushState']({}, '', target)
    window.dispatchEvent(new Event(EVENT))
    if (!replace && !path.includes('#')) window.scrollTo(0, 0)
}

export function usePath() {
    const [path, setPath] = useState(currentPath)
    useEffect(() => {
        const update = () => setPath(currentPath())
        window.addEventListener('popstate', update)
        window.addEventListener(EVENT, update)
        return () => { window.removeEventListener('popstate', update); window.removeEventListener(EVENT, update) }
    }, [])
    return path
}

export const DEFAULT_LIMITS = { collection_max_identifiers: 50, result_retention_days: 14, max_active_collection_jobs_per_client: 3, max_models_per_embedding: 3, example_job_id: 'example' }
let limitsPromise = null

export function useLimits() {
    const [limits, setLimits] = useState(DEFAULT_LIMITS)
    useEffect(() => {
        let active = true
        limitsPromise ||= fetch(`${API}/limits`).then(response => response.ok ? response.json() : DEFAULT_LIMITS).catch(() => DEFAULT_LIMITS)
        limitsPromise.then(value => { if (active) setLimits({ ...DEFAULT_LIMITS, ...value }) })
        return () => { active = false }
    }, [])
    return limits
}

export const resultUrl = jobId => `${window.location.origin}${appPath(`/results/${encodeURIComponent(jobId)}`)}`
