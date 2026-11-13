import { appPath, navigate } from '../lib/routing'

export default function Link({ to, children, onClick, ...props }) {
    const handle = event => {
        onClick?.(event)
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
        event.preventDefault()
        navigate(to)
        const hash = to.split('#')[1]
        if (hash) window.setTimeout(() => document.getElementById(hash)?.scrollIntoView({ behavior: 'smooth' }), 0)
    }
    return <a href={appPath(to)} onClick={handle} {...props}>{children}</a>
}
