import { useState } from 'react'

const DB_OPTIONAL_COLUMNS = {
  String: [
    { key: 'combined_score', label: 'Combined Score' },
    { key: 'experimental_score', label: 'Experimental Score' },
    { key: 'coexpression_score', label: 'Co-expression Score' },
    { key: 'textmining_score', label: 'Textmining Score' },
    { key: 'database_score', label: 'Database Score' },
    { key: 'gene_neighbourhood_score', label: 'Gene Neighbourhood Score' },
    { key: 'gene_fusion_score', label: 'Gene Fusion Score' },
    { key: 'phylogenetic_profile_score', label: 'Phylogenetic Profile Score' },
  ],
  IntAct: [
    { key: 'PubMed_Ids', label: 'PubMed IDs' },
    { key: 'Unique_Identification_Methods', label: 'Detection Methods' },
    { key: 'Interaction_Score_Intact', label: 'MI Score' },
    { key: 'Num_Interaction_IntAct', label: 'Interaction Count' },
    { key: 'Minimum_feature_count', label: 'Min Feature Count' },
    { key: 'Maximum_feature_count', label: 'Max Feature Count' },
  ],
  BioGrid: [
    { key: 'Interaction_Type', label: 'Interaction Type' },
    { key: 'Interaction_Detection_Method', label: 'Detection Method' },
    { key: 'Confidence_Score', label: 'Confidence Score' },
  ],
  Predictomes: [
    { key: 'spoc_score', label: 'SPOC Score' },
    { key: 'kirc_score', label: 'KIRC Score' },
    { key: 'num_unique_contacts', label: 'Unique Contacts' },
  ],
  Corum: [
    { key: 'complex_name', label: 'Complex Name' },
    { key: 'cell_line', label: 'Cell Line' },
    { key: 'Purification_Method', label: 'Purification Method' },
  ],
  HuRI: [],
}

const DEFAULT_COLUMNS = [
  '#ID(s) interactor A',
  'ID(s) interactor B',
  'Alias(es) interactor A',
  'Alias(es) interactor B',
  'Taxid interactor A',
  'Taxid interactor B',
  'Interaction detection method(s)',
  'Interaction type(s)',
  'Publication Identifier(s)',
  'Source database(s)',
  'Confidence value(s)',
]

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`

const SpeciesDownloadPanel = ({ job }) => {
  const [open, setOpen] = useState(false)
  const [format, setFormat] = useState('mitab')
  const [selectedDbs, setSelectedDbs] = useState([])
  const [selectedColumns, setSelectedColumns] = useState([])
  const [loading, setLoading] = useState(false)

  const availableDbs = job?.available_databases || []
  if (!job || availableDbs.length === 0) {
    return null
  }

  const handleDbToggle = (db) => {
    if (selectedDbs.includes(db)) {
      setSelectedDbs(prev => prev.filter(item => item !== db))
      const dbCols = (DB_OPTIONAL_COLUMNS[db] || []).map(col => col.key)
      setSelectedColumns(prev => prev.filter(col => !dbCols.includes(col)))
    } else {
      setSelectedDbs(prev => [...prev, db])
    }
  }

  const handleColumnToggle = (col) => {
    setSelectedColumns(prev =>
      prev.includes(col) ? prev.filter(item => item !== col) : [...prev, col]
    )
  }

  const handleFormatChange = (newFormat) => {
    setFormat(newFormat)
    setSelectedDbs([])
    setSelectedColumns([])
  }

  const handleDownload = async () => {
    if (selectedDbs.length === 0) {
      alert('Please select at least one database')
      return
    }

    setLoading(true)
    try {
      const endpoint = format === 'mitab' ? 'mitab' : 'parquet'
      const response = await fetch(`${API_BASE_URL}/species-ppi/jobs/${job.job_id}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selected_databases: selectedDbs,
          selected_columns: format === 'mitab' ? selectedColumns : [],
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Download failed')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = response.headers.get('Content-Disposition')?.split('filename=')[1]?.replaceAll('"', '') ||
        `${job.species_name.replaceAll(' ', '_')}_${job.tax_id}_ppi.${format === 'mitab' ? 'mitab.txt' : 'parquet'}`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      alert(error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-black/40" onClick={() => setOpen(false)} />
      )}

      {open && (
        <div className="fixed left-1/2 top-1/2 z-50 flex max-h-[80vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col gap-6 overflow-y-auto rounded-2xl bg-white p-8 shadow-2xl">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-800">Download Species PPI Results</h2>
              <p className="mt-0.5 text-xs text-gray-400">Choose format and customise your export</p>
            </div>
            <button onClick={() => setOpen(false)} className="text-xl text-gray-400 hover:text-gray-600">✕</button>
          </div>

          <div>
            <p className="mb-3 text-xs uppercase tracking-wider text-gray-400">Export Format</p>
            <div className="flex gap-4">
              <label className="flex flex-1 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition" style={{ borderColor: format === 'mitab' ? '#1e293b' : '#e5e7eb', background: format === 'mitab' ? '#f8fafc' : 'white' }}>
                <input type="radio" name="species-format" checked={format === 'mitab'} onChange={() => handleFormatChange('mitab')} className="accent-slate-700" />
                <div>
                  <p className="text-sm font-semibold text-gray-700">PSI-MiTab 2.8</p>
                  <p className="text-xs text-gray-400">Standard tab-separated format with column selection</p>
                </div>
              </label>
              <label className="flex flex-1 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition" style={{ borderColor: format === 'parquet' ? '#1e293b' : '#e5e7eb', background: format === 'parquet' ? '#f8fafc' : 'white' }}>
                <input type="radio" name="species-format" checked={format === 'parquet'} onChange={() => handleFormatChange('parquet')} className="accent-slate-700" />
                <div>
                  <p className="text-sm font-semibold text-gray-700">Parquet</p>
                  <p className="text-xs text-gray-400">Columnar format, all fields included</p>
                </div>
              </label>
            </div>
          </div>

          {format === 'mitab' && (
            <div>
              <p className="mb-2 text-xs uppercase tracking-wider text-gray-400">Default Columns (always included)</p>
              <div className="flex flex-wrap gap-2">
                {DEFAULT_COLUMNS.map(col => (
                  <span key={col} className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-500">{col}</span>
                ))}
              </div>
            </div>
          )}

          {format === 'parquet' && (
            <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-500">
              All available fields for each selected database will be included automatically.
            </div>
          )}

          <div>
            <p className="mb-2 text-xs uppercase tracking-wider text-gray-400">Select Databases</p>
            <div className="grid grid-cols-3 gap-2">
              {availableDbs.map(db => (
                <label key={db} className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={selectedDbs.includes(db)} onChange={() => handleDbToggle(db)} className="h-4 w-4 accent-slate-700" />
                  {db}
                </label>
              ))}
            </div>
          </div>

          {format === 'mitab' && selectedDbs.map(db => {
            const cols = DB_OPTIONAL_COLUMNS[db] || []
            if (cols.length === 0) return null
            return (
              <div key={db}>
                <p className="mb-2 text-xs uppercase tracking-wider text-gray-400">{db} — Optional Columns</p>
                <div className="grid grid-cols-2 gap-2">
                  {cols.map(col => (
                    <label key={col.key} className="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
                      <input type="checkbox" checked={selectedColumns.includes(col.key)} onChange={() => handleColumnToggle(col.key)} className="h-4 w-4 accent-slate-700" />
                      {col.label}
                    </label>
                  ))}
                </div>
              </div>
            )
          })}

          <button onClick={handleDownload} disabled={loading || selectedDbs.length === 0} className="rounded-lg bg-slate-800 py-3 font-semibold text-white transition hover:bg-slate-900 disabled:opacity-50">
            {loading ? 'Preparing download...' : `Download as ${format === 'mitab' ? 'MiTab 2.8' : 'Parquet'}`}
          </button>
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <button
          onClick={() => {
            setSelectedDbs(availableDbs)
            setOpen(true)
          }}
          className="flex items-center gap-2 rounded-lg bg-slate-800 px-6 py-3 font-semibold text-white transition hover:bg-slate-900"
        >
          ↓ Download Species PPIs
        </button>
      </div>
    </>
  )
}

export default SpeciesDownloadPanel
