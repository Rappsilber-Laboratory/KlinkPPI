import { useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`

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
    "#ID(s) interactor A",
    "ID(s) interactor B",
    "Taxid interactor A",
    "Taxid interactor B",
    "Interaction detection method(s)",
    "Interaction type(s)",
    "Publication Identifier(s)",
    "Source database(s)",
    "Confidence value(s)",
]

const DownloadPanel = ({ results, uniprot_id, tax_id }) => {
    const [open, setopen] = useState(false)
    const [format, setformat] = useState('mitab')
    const [selectedDbs, setselectedDbs] = useState([])
    const [selectedColumns, setselectedColumns] = useState([])
    const [loading, setloading] = useState(false)

    if (!results) return null

    const availableDbs = results[1]?.output
        ?.filter(db => typeof Object.values(db)[0] !== 'string')
        .map(db => Object.keys(db)[0]) || []

    const handleDbToggle = (db) => {
        if (selectedDbs.includes(db)) {
            setselectedDbs(prev => prev.filter(d => d !== db))
            const dbCols = (DB_OPTIONAL_COLUMNS[db] || []).map(c => c.key)
            setselectedColumns(prev => prev.filter(c => !dbCols.includes(c)))
        } else {
            setselectedDbs(prev => [...prev, db])
        }
    }

    const handleColumnToggle = (col) => {
        setselectedColumns(prev =>
            prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
        )
    }

    const handleFormatChange = (newFormat) => {
        setformat(newFormat)
        setselectedDbs([])
        setselectedColumns([])
    }

    const handleDownload = async () => {
        if (selectedDbs.length === 0) {
            alert('Please select at least one database')
            return
        }
        setloading(true)
        try {
            const endpoint = format === 'mitab' ? '/mitab' : '/parquet'
            const body = format === 'mitab'
                ? { results, selected_databases: selectedDbs, selected_columns: selectedColumns, uniprot_id, tax_id }
                : { results, selected_databases: selectedDbs, selected_columns: [], uniprot_id, tax_id }

            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
            const blob = await response.blob()
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = format === 'mitab'
                ? `${uniprot_id}_interactions.mitab.txt`
                : `${uniprot_id}_interactions.parquet`
            a.click()
            window.URL.revokeObjectURL(url)
        } catch (error) {
            alert(`Download failed: ${error.message}`)
        } finally {
            setloading(false)
        }
    }

    return (
        <>
            {open && (
                <div
                    className="fixed inset-0 bg-black/40 z-40"
                    onClick={() => setopen(false)}
                />
            )}

            {open && (
                <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl bg-white rounded-2xl shadow-2xl p-8 flex flex-col gap-6 max-h-[80vh] overflow-y-auto">

                    <div className="flex justify-between items-center">
                        <div>
                            <h2 className="text-lg font-semibold text-gray-800">Download Results</h2>
                            <p className="text-xs text-gray-400 mt-0.5">Choose format and customise your export</p>
                        </div>
                        <button onClick={() => setopen(false)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
                    </div>

                    {/* Format selection */}
                    <div>
                        <p className="text-xs text-gray-400 uppercase tracking-wider mb-3">Export Format</p>
                        <div className="flex gap-4">
                            <label className="flex items-center gap-3 cursor-pointer border rounded-xl px-4 py-3 flex-1 transition"
                                style={{ borderColor: format === 'mitab' ? '#1e293b' : '#e5e7eb', background: format === 'mitab' ? '#f8fafc' : 'white' }}>
                                <input
                                    type="radio"
                                    name="format"
                                    value="mitab"
                                    checked={format === 'mitab'}
                                    onChange={() => handleFormatChange('mitab')}
                                    className="accent-slate-700"
                                />
                                <div>
                                    <p className="text-sm font-semibold text-gray-700">PSI-MiTab 2.8</p>
                                    <p className="text-xs text-gray-400">Standard tab-separated format with column selection</p>
                                </div>
                            </label>

                            <label className="flex items-center gap-3 cursor-pointer border rounded-xl px-4 py-3 flex-1 transition"
                                style={{ borderColor: format === 'parquet' ? '#1e293b' : '#e5e7eb', background: format === 'parquet' ? '#f8fafc' : 'white' }}>
                                <input
                                    type="radio"
                                    name="format"
                                    value="parquet"
                                    checked={format === 'parquet'}
                                    onChange={() => handleFormatChange('parquet')}
                                    className="accent-slate-700"
                                />
                                <div>
                                    <p className="text-sm font-semibold text-gray-700">Parquet</p>
                                    <p className="text-xs text-gray-400">Columnar format, all fields included</p>
                                </div>
                            </label>
                        </div>
                    </div>

                    {/* MiTab default columns info */}
                    {format === 'mitab' && (
                        <div>
                            <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Default Columns (always included)</p>
                            <div className="flex flex-wrap gap-2">
                                {DEFAULT_COLUMNS.map(col => (
                                    <span key={col} className="bg-gray-100 text-gray-500 text-xs px-3 py-1 rounded-full">{col}</span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Parquet info */}
                    {format === 'parquet' && (
                        <div className="bg-gray-50 rounded-xl px-4 py-3 text-sm text-gray-500">
                            All available fields for each selected database will be included automatically.
                        </div>
                    )}

                    {/* DB selection */}
                    <div>
                        <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Select Databases</p>
                        <div className="grid grid-cols-3 gap-2">
                            {availableDbs.map(db => (
                                <label key={db} className="flex items-center gap-2 text-gray-700 text-sm cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={selectedDbs.includes(db)}
                                        onChange={() => handleDbToggle(db)}
                                        className="accent-slate-700 w-4 h-4"
                                    />
                                    {db}
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Optional columns — MiTab only */}
                    {format === 'mitab' && selectedDbs.map(db => {
                        const cols = DB_OPTIONAL_COLUMNS[db] || []
                        if (cols.length === 0) return null
                        return (
                            <div key={db}>
                                <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">{db} — Optional Columns</p>
                                <div className="grid grid-cols-2 gap-2">
                                    {cols.map(col => (
                                        <label key={col.key} className="flex items-center gap-2 text-gray-700 text-sm cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={selectedColumns.includes(col.key)}
                                                onChange={() => handleColumnToggle(col.key)}
                                                className="accent-slate-700 w-4 h-4"
                                            />
                                            {col.label}
                                        </label>
                                    ))}
                                </div>
                            </div>
                        )
                    })}

                    <button
                        onClick={handleDownload}
                        disabled={loading || selectedDbs.length === 0}
                        className="bg-slate-800 text-white py-3 rounded-lg font-semibold hover:bg-slate-900 transition disabled:opacity-50"
                    >
                        {loading
                            ? 'Preparing download...'
                            : `Download as ${format === 'mitab' ? 'MiTab 2.8' : 'Parquet'}`}
                    </button>
                </div>
            )}

            <div className="flex justify-end mb-4">
                <button
                    onClick={() => setopen(true)}
                    className="bg-slate-800 text-white px-6 py-3 rounded-lg font-semibold hover:bg-slate-900 transition flex items-center gap-2"
                >
                    ↓ Download Results
                </button>
            </div>
        </>
    )
}

export default DownloadPanel
