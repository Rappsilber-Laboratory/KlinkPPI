const DBHeader = ({ name, subtitle, count, color, databaseLink }) => (
    <div className={`${color} px-6 py-4 flex justify-between items-center`}>
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
        <span className="bg-white/10 text-white/80 text-xs font-medium px-3 py-1  border-white/20">
            {count} interactors
        </span>
    </div>
)

export default DBHeader
