import { useState } from 'react'

const DATABASE_STYLES = {
  String: {
    chip: 'bg-sky-100 text-sky-800 border-sky-200',
  },
  IntAct: {
    chip: 'bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200',
  },
  BioGrid: {
    chip: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  },
  Corum: {
    chip: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  HuRI: {
    chip: 'bg-rose-100 text-rose-800 border-rose-200',
  },
  Predictomes: {
    chip: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  },
}

const getDbEntries = (dbName, dbValue) => {
  if (!dbValue || typeof dbValue === 'string') {
    return []
  }

  if (dbName === 'String') {
    return dbValue?.[1]?.Direct_Interactions || []
  }

  if (dbName === 'IntAct') {
    return dbValue?.[1]?.Interactions || []
  }

  return dbValue?.[1]?.Interactors || []
}

const normalizeKey = (value) => String(value || '').trim().toUpperCase()

const formatCount = (value) => new Intl.NumberFormat().format(value || 0)

const getInteractorGeneName = (entry) => (
  entry.Interactor_Gene_Name ||
  entry.Interactor_Gene_Name_A ||
  entry.Interactor_A ||
  null
)

const getInteractorId = (entry) => (
  entry.Interactor_A_UniProt ||
  entry.Interactor_A ||
  null
)

const buildOverlapGroups = (overlapEntries, searchedDatabases) => {
  const groups = new Map()

  for (const entry of overlapEntries) {
    const databaseNames = entry.databases.map(database => database.name)
    const key = databaseNames.join('|')

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        databases: databaseNames,
        count: 0,
      })
    }

    groups.get(key).count += 1
  }

  return Array.from(groups.values())
    .sort((a, b) => (
      b.count - a.count ||
      b.databases.length - a.databases.length ||
      a.databases.join('|').localeCompare(b.databases.join('|'))
    ))
    .map(group => ({
      ...group,
      databases: searchedDatabases.filter(database => group.databases.includes(database)),
    }))
}

const buildOverlapEntries = (results) => {
  const output = results?.[1]?.output || []
  const searchedDatabases = Array.from(
    new Set(output.map(item => Object.keys(item)[0]).filter(Boolean))
  )
  const overlapMap = new Map()

  for (const item of output) {
    const dbName = Object.keys(item)[0]
    const dbValue = item[dbName]
    const entries = getDbEntries(dbName, dbValue)

    for (const entry of entries) {
      const geneName = getInteractorGeneName(entry)
      const interactorId = getInteractorId(entry)
      const key = normalizeKey(geneName || interactorId)
      if (!key) {
        continue
      }

      if (!overlapMap.has(key)) {
        overlapMap.set(key, {
          geneNames: new Set(),
          ids: new Set(),
          databases: new Map(),
        })
      }

      const aggregate = overlapMap.get(key)
      if (geneName) {
        aggregate.geneNames.add(geneName)
      }
      if (interactorId) {
        aggregate.ids.add(interactorId)
      }
      const existingDatabase = aggregate.databases.get(dbName)
      const interactionLink = entry.Interactor_Link || null
      if (!existingDatabase || (!existingDatabase.interactionLink && interactionLink)) {
        aggregate.databases.set(dbName, { name: dbName, interactionLink })
      }
    }
  }

  const overlapEntries = Array.from(overlapMap.values())
    .filter(item => item.databases.size >= 1)
    .map(item => {
      const databases = searchedDatabases
        .filter(dbName => item.databases.has(dbName))
        .map(dbName => item.databases.get(dbName))

      return {
        geneName: Array.from(item.geneNames)[0] || Array.from(item.ids)[0] || '-',
        interactorId: Array.from(item.ids)[0] || '-',
        databases,
        count: databases.length,
      }
    })
    .sort((a, b) => b.count - a.count || a.geneName.localeCompare(b.geneName))

  return {
    searchedDatabases,
    overlapEntries,
    overlapGroups: buildOverlapGroups(overlapEntries, searchedDatabases),
  }
}

const DatabaseChip = ({ name }) => (
  <span
    className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${DATABASE_STYLES[name]?.chip || 'border-slate-200 bg-white text-slate-700'}`}
  >
    {name}
  </span>
)

const OverlapSummary = ({ searchedDatabases, overlapEntries, overlapGroups }) => {
  const setSizes = searchedDatabases.map(database => ({
    database,
    count: overlapEntries.filter(entry => entry.databases.some(item => item.name === database)).length,
  }))
  const exactGroups = [...overlapGroups].sort((a, b) => (
    b.databases.length - a.databases.length ||
    b.count - a.count ||
    a.databases.join('|').localeCompare(b.databases.join('|'))
  ))
  const maxSetSize = Math.max(...setSizes.map(item => item.count), 1)
  const maxGroupCount = Math.max(...exactGroups.map(group => group.count), 1)
  const sharedCount = overlapEntries.filter(entry => entry.count > 1).length
  const uniqueCount = overlapEntries.length - sharedCount
  const allSelectedCount = overlapGroups.find(group => group.databases.length === searchedDatabases.length)?.count || 0
  const databaseOnlyCounts = searchedDatabases.map(database => ({
    database,
    count: overlapGroups.find(group => group.databases.length === 1 && group.databases[0] === database)?.count || 0,
  }))

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Database overlap summary</h3>
          <p className="text-sm text-slate-500">How interaction pairs are distributed across the selected databases</p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md bg-slate-100 px-3 py-2">
            <p className="text-base font-semibold text-slate-900">{formatCount(overlapEntries.length)}</p>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Total</p>
          </div>
          <div className="rounded-md bg-slate-100 px-3 py-2">
            <p className="text-base font-semibold text-slate-900">{formatCount(sharedCount)}</p>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Shared</p>
          </div>
          <div className="rounded-md bg-slate-100 px-3 py-2">
            <p className="text-base font-semibold text-slate-900">{formatCount(uniqueCount)}</p>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Unique</p>
          </div>
        </div>
      </div>

      <div className="mb-5">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-slate-900">Key exact intersections</h4>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {searchedDatabases.map(database => (
                <DatabaseChip key={`all-${database}`} name={database} />
              ))}
            </div>
            <div className="flex items-end justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">All selected databases</p>
              <p className="text-lg font-semibold text-slate-900">{formatCount(allSelectedCount)}</p>
            </div>
          </div>

          {databaseOnlyCounts.map(item => (
            <div key={`only-${item.database}`} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="mb-2 flex flex-wrap gap-1.5">
                <DatabaseChip name={item.database} />
                <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-500">
                  only
                </span>
              </div>
              <div className="flex items-end justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Database-only pairs</p>
                <p className="text-lg font-semibold text-slate-900">{formatCount(item.count)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900">Pairs per database</h4>
            <span className="text-xs text-slate-500">set size</span>
          </div>
          <div className="space-y-3">
            {setSizes.map(item => (
              <div key={item.database}>
                <div className="mb-1.5 flex items-center justify-between gap-3">
                  <DatabaseChip name={item.database} />
                  <span className="text-sm font-semibold text-slate-900">{formatCount(item.count)}</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-slate-700"
                    style={{ width: `${Math.max((item.count / maxSetSize) * 100, item.count > 0 ? 4 : 0)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900">All exact overlap combinations</h4>
            <span className="text-xs text-slate-500">{formatCount(exactGroups.length)} groups</span>
          </div>
          <div className="max-h-[30rem] space-y-3 overflow-y-auto pr-1">
            {exactGroups.map(group => {
              const isUnique = group.databases.length === 1
              return (
                <div key={group.key} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-wrap gap-1.5">
                      {group.databases.map(database => (
                        <DatabaseChip key={`${group.key}-${database}`} name={database} />
                      ))}
                      {isUnique ? (
                        <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-500">
                          only
                        </span>
                      ) : null}
                    </div>
                    <span className="shrink-0 text-sm font-semibold text-slate-900">
                      {formatCount(group.count)}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white">
                    <div
                      className="h-full rounded-full bg-slate-800"
                      style={{ width: `${Math.max((group.count / maxGroupCount) * 100, 4)}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

const InteractionOverlapLog = ({ results }) => {
  const [open, setOpen] = useState(true)
  const input = results?.[0]?.Input || {}
  const { searchedDatabases, overlapEntries, overlapGroups } = buildOverlapEntries(results)
  const queryLabel = input.OriginalInput || input.UniProtId || '-'
  const queryType = input.OriginalInputType || 'UniProtKB'

  return (
    <div className="mb-8 rounded-2xl border border-slate-200 bg-slate-50 p-6 shadow-sm">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-start justify-between gap-4 text-left"
      >
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Shared Interaction Log</h2>
          <p className="text-sm text-slate-600">
            Query: <span className="font-semibold text-slate-800">{queryLabel}</span>
            {' '}<span className="text-slate-500">({queryType})</span>
          </p>
        </div>
        <div className="flex items-center gap-4">
          <p className="text-sm text-slate-600">
            {overlapEntries.length} interactors in log
          </p>
          <span className="text-2xl leading-none text-slate-500">{open ? '−' : '+'}</span>
        </div>
      </button>

      <div className="mt-4 flex flex-wrap gap-2">
        {searchedDatabases.length > 0 ? (
          searchedDatabases.map((dbName) => (
            <span
              key={dbName}
              className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${DATABASE_STYLES[dbName]?.chip || 'border-slate-200 bg-white text-slate-700'}`}
            >
              {dbName}
            </span>
          ))
        ) : (
          <span className="text-sm text-slate-500">No databases selected</span>
        )}
      </div>

      {open && (
        <div>
          {overlapEntries.length > 0 ? (
            <div className="mt-5 space-y-5">
              <OverlapSummary
                searchedDatabases={searchedDatabases}
                overlapEntries={overlapEntries}
                overlapGroups={overlapGroups}
              />

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-3">Interactor</th>
                      <th className="px-3 py-3">ID</th>
                      <th className="px-3 py-3">Found In</th>
                      <th className="px-3 py-3">Databases</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {overlapEntries.map((entry) => (
                      <tr key={`${entry.geneName}-${entry.interactorId}`} className="align-top">
                        <td className="px-3 py-3 font-semibold text-slate-900">{entry.geneName}</td>
                        <td className="px-3 py-3 text-slate-600">{entry.interactorId}</td>
                        <td className="px-3 py-3 text-slate-700">
                          {entry.count} {entry.count === 1 ? 'database' : 'databases'}
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            {entry.databases.map(({ name, interactionLink }) => {
                              const className = `inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${DATABASE_STYLES[name]?.chip || 'border-slate-200 bg-white text-slate-700'}`

                              return interactionLink ? (
                                <a
                                  key={name}
                                  href={interactionLink}
                                  target="_blank"
                                  rel="noreferrer"
                                  className={`${className} hover:brightness-95 hover:underline`}
                                  aria-label={`Open this interaction in ${name}`}
                                >
                                  {name} <span aria-hidden="true" className="ml-1">↗</span>
                                </a>
                              ) : (
                                <span key={name} className={className}>
                                  {name}
                                </span>
                              )
                            })}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="mt-5 rounded-xl border border-dashed border-slate-300 bg-white px-4 py-5 text-sm text-slate-500">
              No interactors were found in the searched databases for this query.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default InteractionOverlapLog
