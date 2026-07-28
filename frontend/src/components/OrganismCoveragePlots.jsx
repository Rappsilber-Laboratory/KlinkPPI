import { useEffect, useMemo, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`

const DATABASE_STYLES = {
  String: { label: 'STRING', color: '#0284c7' },
  BioGrid: { label: 'BioGRID', color: '#059669' },
  IntAct: { label: 'IntAct', color: '#c026d3' },
  Corum: { label: 'CORUM', color: '#d97706' },
  Predictomes: { label: 'Predictomes', color: '#4f46e5' },
  HuRI: { label: 'HuRI', color: '#e11d48' },
}

const formatCount = (value) => new Intl.NumberFormat().format(value || 0)

const getDatabaseLabel = (database) => DATABASE_STYLES[database]?.label || database

const OrganismCoveragePlots = () => {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [retryToken, setRetryToken] = useState(0)

  useEffect(() => {
    let ignore = false
    let retryTimeout = null

    const loadSummary = async (attempt = 1) => {
      try {
        const response = await fetch(`${API_BASE_URL}/supported-organisms/summary`)
        if (!response.ok) {
          throw new Error(`Backend returned HTTP ${response.status}`)
        }
        const data = await response.json()
        if (!ignore) {
          setSummary(data)
          setError('')
        }
      } catch (loadError) {
        if (!ignore) {
          if (attempt < 30) {
            retryTimeout = window.setTimeout(() => loadSummary(attempt + 1), 1000)
            return
          }

          setError(loadError instanceof Error ? loadError.message : 'Could not reach the backend')
        }
      }
    }

    loadSummary()

    return () => {
      ignore = true
      if (retryTimeout) {
        window.clearTimeout(retryTimeout)
      }
    }
  }, [retryToken])

  const databaseCounts = summary?.database_counts || []
  const topOverlapGroups = useMemo(() => {
    return (summary?.exact_overlap_counts || [])
      .filter((item) => item.databases.length > 1 && item.count > 0)
      .slice(0, 6)
  }, [summary])

  const maxCount = Math.max(...databaseCounts.map((item) => item.count), 1)
  const chartWidth = 520
  const chartHeight = 260
  const plotTop = 28
  const plotBottom = 42
  const plotLeft = 48
  const plotRight = 20
  const plotHeight = chartHeight - plotTop - plotBottom
  const barSlot = (chartWidth - plotLeft - plotRight) / Math.max(databaseCounts.length, 1)
  const barWidth = Math.min(48, barSlot * 0.58)

  return (
    <section className="bg-slate-100 px-4 pb-8 sm:px-6">
      {error ? (
        <div className="mx-auto w-full max-w-[110rem] rounded-lg border border-amber-200 bg-amber-50 p-5 text-amber-900 shadow-sm">
          <h2 className="text-base font-semibold">Supported organism plots could not load</h2>
          <p className="mt-1 text-sm">
            The app could not reach <span className="font-mono">{API_BASE_URL}/supported-organisms/summary</span>.
            {error ? <span> Last error: <span className="font-mono">{error}</span>.</span> : null}
          </p>
          <button
            type="button"
            onClick={() => {
              setSummary(null)
              setError('')
              setRetryToken((value) => value + 1)
            }}
            className="mt-3 rounded-md bg-amber-900 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-800"
          >
            Retry loading plots
          </button>
        </div>
      ) : null}

      {!error ? (
      <div className="mx-auto grid w-full max-w-[110rem] gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-slate-900">Supported Taxon IDs by database</h2>
            <p className="text-sm text-slate-500">Count of unique organisms listed in each source file</p>
          </div>

          {summary ? (
            <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label="Histogram of supported Taxon IDs by database" className="h-[20rem] w-full">
              <line x1={plotLeft} y1={plotTop} x2={plotLeft} y2={chartHeight - plotBottom} stroke="#cbd5e1" />
              <line x1={plotLeft} y1={chartHeight - plotBottom} x2={chartWidth - plotRight} y2={chartHeight - plotBottom} stroke="#cbd5e1" />
              <text x={plotLeft - 8} y={plotTop + 4} textAnchor="end" className="fill-slate-400 text-[11px]">
                {formatCount(maxCount)}
              </text>
              <text x={plotLeft - 8} y={chartHeight - plotBottom + 4} textAnchor="end" className="fill-slate-400 text-[11px]">
                0
              </text>

              {databaseCounts.map((item, index) => {
                const style = DATABASE_STYLES[item.database]
                const barHeight = item.count > 0 ? Math.max((item.count / maxCount) * plotHeight, 5) : 0
                const x = plotLeft + index * barSlot + (barSlot - barWidth) / 2
                const y = chartHeight - plotBottom - barHeight

                return (
                  <g key={item.database}>
                    <rect
                      x={x}
                      y={y}
                      width={barWidth}
                      height={barHeight}
                      rx="5"
                      fill={style.color}
                    />
                    <text x={x + barWidth / 2} y={Math.max(y - 8, 14)} textAnchor="middle" className="fill-slate-800 text-[12px] font-semibold">
                      {formatCount(item.count)}
                    </text>
                    <text
                      x={x + barWidth / 2}
                      y={chartHeight - 18}
                      textAnchor="middle"
                      className="fill-slate-600 text-[11px]"
                    >
                      {style.label}
                    </text>
                  </g>
                )
              })}
            </svg>
          ) : (
            <div className="flex h-[20rem] items-center justify-center text-sm text-slate-500">
              Loading database counts...
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Exact overlaps</h2>
              <p className="text-sm text-slate-500">Taxon IDs that appear in the same exact database combination</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-slate-400">Union</p>
              <p className="text-lg font-semibold text-slate-900">{formatCount(summary?.union_count)}</p>
            </div>
          </div>

          <div className="space-y-3">
            {summary && topOverlapGroups.length > 0 ? (
              topOverlapGroups.map((item) => (
                <div key={item.databases.join('|')} className="rounded-md border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm leading-5 text-slate-600">
                      {item.databases.map(getDatabaseLabel).join(' + ')}
                    </p>
                    <p className="shrink-0 text-sm font-semibold text-slate-900">
                      {formatCount(item.count)}
                      <span className="ml-1 font-normal text-slate-500">Taxon IDs</span>
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex h-[20rem] items-center justify-center text-sm text-slate-500">
                Loading overlaps...
              </div>
            )}
          </div>
        </div>
      </div>
      ) : null}
    </section>
  )
}

export default OrganismCoveragePlots
