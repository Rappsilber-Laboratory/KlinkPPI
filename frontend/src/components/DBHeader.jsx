const DBHeader = ({ name, subtitle, count, color, databaseLink, hidden, onToggle }) => (
    <div className={`${color} px-6 py-4 flex flex-wrap justify-between items-center gap-3`}>
        <div>
            <h2 className="text-white text-lg font-semibold tracking-wide">
                {databaseLink ? (
                    <a
                        href={databaseLink}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 hover:underline focus:outline-none focus:ring-2 focus:ring-white/80"
                        aria-label={`Open ${name} for the searched protein`}
                    >
                        {name} <span aria-hidden="true">↗</span>
                    </a>
                ) : name}
            </h2>
            <p className="text-white/50 text-xs mt-0.5">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
            <span className="bg-white/10 text-white/80 text-xs font-medium px-3 py-1 border border-white/20 rounded-full">{count} pairs found</span>
            {onToggle && <button type="button" onClick={onToggle} className="rounded-full border border-white/30 bg-white/10 px-3 py-1 text-xs font-semibold text-white hover:bg-white/20" aria-expanded={!hidden}>{hidden ? 'Show results' : 'Hide results'}</button>}
        </div>
    </div>
)

export default DBHeader
