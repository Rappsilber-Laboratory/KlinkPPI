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

const buildOverlapEntries = (results) => {
  const output = results?.[1]?.output || []
  const searchedDatabases = output.map(item => Object.keys(item)[0]).filter(Boolean)
  const overlapMap = new Map()

  for (const item of output) {
    const dbName = Object.keys(item)[0]
    const dbValue = item[dbName]
    const entries = getDbEntries(dbName, dbValue)

    for (const entry of entries) {
      const geneName = entry.Interactor_Gene_Name || entry.Interactor_A || null
      const interactorId = entry.Interactor_A || null
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
      const databases = Array.from(item.databases.values())
        .sort((a, b) => a.name.localeCompare(b.name))

      return {
        geneName: Array.from(item.geneNames)[0] || Array.from(item.ids)[0] || '-',
        interactorId: Array.from(item.ids)[0] || '-',
        databases,
        count: databases.length,
      }
    })
    .sort((a, b) => b.count - a.count || a.geneName.localeCompare(b.geneName))

  return { searchedDatabases, overlapEntries }
}

const InteractionOverlapLog = ({ results }) => {
  const [open, setOpen] = useState(true)
  const input = results?.[0]?.Input || {}
  const { searchedDatabases, overlapEntries } = buildOverlapEntries(results)
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
            <div className="mt-5 overflow-x-auto">
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
                      <td className="px-3 py-3 text-slate-700">{entry.count} databases</td>
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
