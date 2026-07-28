import React, { useEffect, useState } from 'react'
import SpeciesDownloadPanel from './SpeciesDownloadPanel'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/api`

const STATUS_STYLES = {
    pending: 'bg-slate-100 text-slate-700',
    running: 'bg-amber-100 text-amber-800',
    completed: 'bg-emerald-100 text-emerald-800',
    unsupported: 'bg-slate-200 text-slate-700',
    not_supported: 'bg-slate-200 text-slate-700',
    not_available: 'bg-violet-100 text-violet-800',
    cancelled: 'bg-rose-100 text-rose-800',
    failed: 'bg-red-100 text-red-800',
}

const DATABASE_STYLES = {
    String: {
        chip: 'bg-sky-100 text-sky-800 border-sky-200',
        accent: 'bg-sky-500',
        label: 'text-sky-800',
        surface: 'bg-sky-50 border-sky-200',
    },
    IntAct: {
        chip: 'bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200',
        accent: 'bg-fuchsia-500',
        label: 'text-fuchsia-800',
        surface: 'bg-fuchsia-50 border-fuchsia-200',
    },
    BioGrid: {
        chip: 'bg-emerald-100 text-emerald-800 border-emerald-200',
        accent: 'bg-emerald-500',
        label: 'text-emerald-800',
        surface: 'bg-emerald-50 border-emerald-200',
    },
    Corum: {
        chip: 'bg-orange-100 text-orange-800 border-orange-200',
        accent: 'bg-orange-500',
        label: 'text-orange-800',
        surface: 'bg-orange-50 border-orange-200',
    },
    HuRI: {
        chip: 'bg-rose-100 text-rose-800 border-rose-200',
        accent: 'bg-rose-500',
        label: 'text-rose-800',
        surface: 'bg-rose-50 border-rose-200',
    },
    Predictomes: {
        chip: 'bg-indigo-100 text-indigo-800 border-indigo-200',
        accent: 'bg-indigo-500',
        label: 'text-indigo-800',
        surface: 'bg-indigo-50 border-indigo-200',
    },
}

const SearchSection = ({setresults}) => {
    const [search_type, setsearch_type] = useState('single_search');
    const [from_database,setfrom_database]=useState('UniProtKB');
    const[protein_id,setprotein_id]=useState('');
    const [tax_id,settax_id]=useState('');
    const [species_name,setspecies_name]=useState('');
    const [speciesSuggestions,setspeciesSuggestions]=useState([])
    const [showSpeciesSuggestions,setshowSpeciesSuggestions]=useState(false)
    const [geneCandidates,setgeneCandidates]=useState([])
    const [selectedGeneCandidate,setselectedGeneCandidate]=useState(null)
    const [speciesJob,setspeciesJob]=useState(null)
    const [speciesLogOpen,setspeciesLogOpen]=useState(true)
    const [selected_databases,setselected_databases]=useState([])
    const [loading,setloading]=useState(false)
    const [loadingMessage,setloadingMessage]=useState('Searching databases...')
    const abortController = React.useRef(null)
    const speciesAbortController = React.useRef(null)
    const speciesSearchTimeout = React.useRef(null)
    const speciesJobPollTimeout = React.useRef(null)

    useEffect(() => {
        const query = species_name.trim()

        if (!query) {
            if (speciesAbortController.current) {
                speciesAbortController.current.abort()
            }
            return
        }

        speciesSearchTimeout.current = window.setTimeout(async () => {
            if (speciesAbortController.current) {
                speciesAbortController.current.abort()
            }

            speciesAbortController.current = new AbortController()

            try {
                const response = await fetch(
                    `${API_BASE_URL}/species/search?q=${encodeURIComponent(query)}&limit=20`,
                    { signal: speciesAbortController.current.signal }
                )

                if (!response.ok) {
                    setspeciesSuggestions([])
                    return
                }

                const data = await response.json()
                setspeciesSuggestions(data.results || [])
            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.log(error)
                }
            }
        }, 150)

        return () => {
            if (speciesSearchTimeout.current) {
                clearTimeout(speciesSearchTimeout.current)
            }
        }
    }, [species_name])

    useEffect(() => {
        return () => {
            if (abortController.current) {
                abortController.current.abort()
            }
            if (speciesAbortController.current) {
                speciesAbortController.current.abort()
            }
            if (speciesSearchTimeout.current) {
                clearTimeout(speciesSearchTimeout.current)
            }
            if (speciesJobPollTimeout.current) {
                clearTimeout(speciesJobPollTimeout.current)
            }
        }
    }, [])

    const clearGeneCandidateState = () => {
        setgeneCandidates([])
        setselectedGeneCandidate(null)
    }

    useEffect(() => {
        if (!speciesJob || speciesJob.status !== 'running') {
            return
        }

        speciesJobPollTimeout.current = window.setTimeout(async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/species-ppi/jobs/${speciesJob.job_id}`)
                const data = await response.json()
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to refresh species job')
                }
                setspeciesJob(data)
            } catch (error) {
                console.log(error)
            }
        }, 1200)

        return () => {
            if (speciesJobPollTimeout.current) {
                clearTimeout(speciesJobPollTimeout.current)
            }
        }
    }, [speciesJob])

    const performMainSearch = async (idValue, sourceDatabase) => {
        const mappingLabels = {
            GeneID: 'NCBI GeneID',
            Ensembl: 'Ensembl ID',
            Gene_Name: 'gene name',
        }
        setloadingMessage(
            sourceDatabase === 'UniProtKB'
                ? 'Searching databases...'
                : `Mapping ${mappingLabels[sourceDatabase] || sourceDatabase} to UniProtKB, then searching databases...`
        )
        setloading(true)
        setresults(null)
        abortController.current = new AbortController()

        try{
            const params = new URLSearchParams({
                id_value: idValue,
                from_database: sourceDatabase
            })

            if (tax_id.trim()) {
                params.set('tax_id', tax_id.trim())
            }

            if (species_name.trim()) {
                params.set('species_name', species_name.trim())
            }

            if(selected_databases.length>0){
                selected_databases.forEach(value => params.append('selected_databases', value))
            }

            const response=await fetch(`${API_BASE_URL}/search?${params.toString()}`,{signal: abortController.current.signal});
            const data=await response.json();

            if(!response.ok){
                throw new Error(data.detail || 'Search failed')
            }

            if (data?.[0]?.Input) {
                data[0].Input.OriginalInput = protein_id
                data[0].Input.OriginalInputType = from_database
                data[0].Input.ResolvedSearchId = idValue
            }

            setresults(data)
            settax_id(data?.[0]?.Input?.TaxonomyId || '')
            setspecies_name(data?.[0]?.Input?.SpeciesName || species_name)
            setshowSpeciesSuggestions(false)
            console.log(data);
        }catch(error){
          if(error.name==='AbortError'){
            console.log('Search Cancelled')
          } else {
            alert(error.message)
          }
          console.log(error)
        }finally{
          setloading(false)
        }
    }

    const handleGeneNameLookup = async () => {
        if (!species_name.trim() && !tax_id.trim()) {
            alert('Gene Name search requires a species name or taxonomy ID')
            return
        }

        setloadingMessage('Finding matching UniProt entries...')
        setloading(true)
        abortController.current = new AbortController()

        try {
            const params = new URLSearchParams({
                query: protein_id
            })

            if (tax_id.trim()) {
                params.set('tax_id', tax_id.trim())
            }

            if (species_name.trim()) {
                params.set('species_name', species_name.trim())
            }

            const response = await fetch(
                `${API_BASE_URL}/gene-name/search?${params.toString()}`,
                { signal: abortController.current.signal }
            )
            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || 'Gene lookup failed')
            }

            const candidates = data.candidates || []
            setgeneCandidates(candidates)

            if (data.tax_id) {
                settax_id(data.tax_id)
            }

            if (data.species_name) {
                setspecies_name(data.species_name)
            }

            if (candidates.length === 0) {
                alert(`No UniProt matches found for gene name '${protein_id}'`)
                return
            }

            if (candidates.length === 1) {
                const [candidate] = candidates
                setselectedGeneCandidate(candidate)
                await performMainSearch(candidate.primary_accession, 'UniProtKB')
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Search Cancelled')
            } else {
                alert(error.message)
            }
            console.log(error)
        } finally {
            setloading(false)
        }
    }

    const handleSearch=async ()=>{
        if (search_type === 'complete_species') {
            await handleCompleteSpeciesSearch()
            return
        }

        if(!protein_id || !from_database){
            alert('please complete the required input parameters')
            return
        }

        if (from_database === 'Gene_Name') {
            if (selectedGeneCandidate) {
                await performMainSearch(selectedGeneCandidate.primary_accession, 'UniProtKB')
                return
            }
            await handleGeneNameLookup()
            return
        }

        await performMainSearch(protein_id, from_database)
    }

    const handleCompleteSpeciesSearch = async () => {
        if (!tax_id.trim() && !species_name.trim()) {
            alert('Complete species PPI search requires a species name or taxonomy ID')
            return
        }
        if (selected_databases.length === 0) {
            alert('Please select at least one database')
            return
        }

        setloading(true)
        setloadingMessage('Building complete species PPI search...')
        setresults(null)
        abortController.current = new AbortController()

        try {
            const response = await fetch(`${API_BASE_URL}/species-ppi/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: abortController.current.signal,
                body: JSON.stringify({
                    tax_id: tax_id.trim() || null,
                    species_name: species_name.trim() || null,
                    selected_databases,
                }),
            })
            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start complete species PPI job')
            }

            setspeciesJob(data)
            setspeciesLogOpen(true)
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Search Cancelled')
            } else {
                alert(error.message)
            }
            console.log(error)
        } finally {
            setloading(false)
        }
    }

    const handleCancel=async ()=>{
      if (search_type === 'complete_species' && speciesJob?.job_id && speciesJob?.status === 'running') {
          try {
              const response = await fetch(`${API_BASE_URL}/species-ppi/jobs/${speciesJob.job_id}/cancel`, {
                  method: 'POST',
              })
              const data = await response.json()
              if (!response.ok) {
                  throw new Error(data.detail || 'Failed to cancel complete species job')
              }
              setspeciesJob(data)
          } catch (error) {
              alert(error.message)
          }
      }
      if (abortController.current){
          abortController.current.abort()
      }
      if (speciesJobPollTimeout.current) {
          clearTimeout(speciesJobPollTimeout.current)
      }
      setloading(false)
    }
    const handleDatabaseChange=(db)=>{
        const value=db.target.value;
        if(db.target.checked){
            setselected_databases([...selected_databases,value])
        }else{
            const index=selected_databases.indexOf(value);
            const size=(selected_databases).length;
            const arr1=selected_databases.slice(0,index);
            const arr2=selected_databases.slice(index+1,size)
            setselected_databases([...arr1,...arr2])
        }
    }

    const handleSpeciesSelect=(species)=>{
        clearGeneCandidateState()
        setspecies_name(species.display_name)
        settax_id(species.tax_id)
        setspeciesSuggestions([])
        setshowSpeciesSuggestions(false)
    }

    const handleGeneCandidateSelect = async (candidate) => {
        setselectedGeneCandidate(candidate)
        await performMainSearch(candidate.primary_accession, 'UniProtKB')
    }


  return (
    <div>
      <section className="bg-slate-200 py-14 px-4 sm:px-6">
      <div className="w-full max-w-[110rem] mx-auto">
        <div className="bg-white shadow-md rounded-2xl p-8 grid gap-8 lg:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)] lg:items-start">
        <div className="flex flex-col gap-4">
        <label className='font-bold text-left'>Databases Selections:</label>

        <div className="space-y-2">
        <label className="flex items-center gap-2">
        <input
            type="checkbox"
            value="String"
            checked={selected_databases.includes('String')}
            onChange={handleDatabaseChange}
        />
        <span className="font-medium text-slate-900">STRING</span>
        </label>

        <label className="flex items-center gap-2">
        <input
            type="checkbox"
            value="IntAct"
            checked={selected_databases.includes('IntAct')}
            onChange={handleDatabaseChange}
        />
        <span className="font-medium text-slate-900">IntAct</span>
        </label>

        <label className="flex items-center gap-2">
        <input
            type="checkbox"
            value="BioGrid"
            checked={selected_databases.includes('BioGrid')}
            onChange={handleDatabaseChange}
        />
        <span className="font-medium text-slate-900">BioGRID</span>
        </label>

        <label className="flex items-center gap-2">
        <input
            type="checkbox"
            value="Corum"
            checked={selected_databases.includes('Corum')}
            onChange={handleDatabaseChange}
        />
        <span className="font-medium text-slate-900">CORUM</span>
        </label>

        <label className="flex items-center gap-2">
        <input
            type="checkbox"
            value="HuRI"
            checked={selected_databases.includes('HuRI')}
            onChange={handleDatabaseChange}
        />
        <span className="font-medium text-slate-900">HuRI</span>
        </label>

        <label className="flex items-center gap-2 mb-3">
        <input
            type="checkbox"
            value="Predictomes"
            checked={selected_databases.includes('Predictomes')}
            onChange={handleDatabaseChange}
        />
        <span className="font-medium text-slate-900">Predictomes</span>
        </label>
        </div>
        </div>
        
        <div className="flex flex-col gap-4">
    <label className='font-bold text-left'>Search Type</label>
        <select
            value={search_type}
            onChange={(e) => {
                const value = e.target.value
                setsearch_type(value)
                setloading(false)
                setresults(null)
                setspeciesJob(null)
                setspeciesLogOpen(true)
                clearGeneCandidateState()
            }}
            className="border border-gray-300 px-4 py-3 text-gray-700 focus:outline-none focus:ring-2"
          >
            <option value="single_search">Single Search</option>
            <option value="complete_species">Complete Species PPI</option>
          </select>

        {search_type === 'single_search' && (
          <>
    <label className='font-bold text-left'>Input Type</label>
        <select
            value={from_database}
            onChange={(e) => {
                clearGeneCandidateState()
                setfrom_database(e.target.value)
            }}
            className="border border-gray-300  px-4 py-3 text-gray-700 focus:outline-none focus:ring-2 mb-3"
          >
            <option value="UniProtKB">UniProtKB</option>
            <option value="GeneID">GeneID</option>
            <option value="Ensembl">Ensembl</option>
            <option value="Gene_Name">Gene Name</option>
          </select>
        
          <label className='font-bold text-left'> Protein/Gene ID</label>
          <input
            type="text"
            placeholder="Enter Protein ID (e.g. Q9NYP3)"
            value={protein_id}
            onChange={(e) => {
                clearGeneCandidateState()
                setprotein_id(e.target.value.toUpperCase())
            }}
            className="border border-gray-300  px-4 py-3 text-gray-700 focus:outline-none focus:ring-2 mb-3"
          />
          </>
        )}

        <label className='font-bold text-left'> Species Name (optional)</label>
          <div className="relative">
            <input
              type="text"
              placeholder="Type a species (e.g. human, mus musculus)"
              value={species_name}
              onChange={(e) => {
                clearGeneCandidateState()
                setspecies_name(e.target.value)
                if (e.target.value.trim()) {
                  setshowSpeciesSuggestions(true)
                } else {
                  setspeciesSuggestions([])
                  setshowSpeciesSuggestions(false)
                }
              }}
              onFocus={() => {
                if (speciesSuggestions.length > 0) {
                  setshowSpeciesSuggestions(true)
                }
              }}
              onBlur={() => {
                window.setTimeout(() => setshowSpeciesSuggestions(false), 150)
              }}
              className="border border-gray-300 px-4 py-3 text-gray-700 focus:outline-none focus:ring-2 w-full"
            />

            {showSpeciesSuggestions && speciesSuggestions.length > 0 && (
              <div className="absolute z-20 mt-2 max-h-72 w-full overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-lg">
                {speciesSuggestions.map(species => (
                  <button
                    key={species.tax_id}
                    type="button"
                    onMouseDown={(event) => {
                      event.preventDefault()
                      handleSpeciesSelect(species)
                    }}
                    className="flex w-full flex-col gap-1 border-b border-gray-100 px-4 py-3 text-left last:border-b-0 hover:bg-slate-50"
                  >
                    <span className="font-medium text-slate-800">{species.display_name}</span>
                    <span className="text-xs text-slate-500">
                      Taxonomy ID: {species.tax_id} • Databases: {species.supported_databases.join(', ')}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <p className="text-sm text-gray-500">
            {search_type === 'complete_species'
              ? 'Complete species PPI export requires a species name or taxonomy ID. The selected databases will be processed one by one and logged below.'
              : 'You can search with a taxonomy ID, a species name, both, or neither. Adding one improves organism matching.'}
          </p>

          {from_database === 'Gene_Name' && (
          search_type === 'single_search' && (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="font-semibold text-slate-800">Gene Name Search</p>
              <p className="mt-1 text-sm text-slate-600">
                Gene symbols are matched against UniProt candidates for the selected species before the interaction search runs.
              </p>
              {selectedGeneCandidate && (
                <p className="mt-3 text-sm text-slate-700">
                  Selected match: <strong>{selectedGeneCandidate.primary_accession}</strong>
                  {' '}({selectedGeneCandidate.gene_names.join(', ') || 'No gene symbol'})
                </p>
              )}
            </div>
          )
          )}

        <label className='font-bold text-left'> Taxonomy ID (optional)</label>
          <input
            type="number"
            placeholder="Enter Taxonomy ID (e.g. 9606 for Human)"
            value={tax_id}
            onChange={(e) => {
                clearGeneCandidateState()
                settax_id(e.target.value)
            }}
            className="border border-gray-300  px-4 py-3 text-gray-700 focus:outline-none focus:ring-2"
          />

          <div className="flex flex-col gap-3 pt-2 sm:flex-row">
            <button
              onClick={handleSearch}
              className="bg-blue-900 text-white py-3 px-6 font-semibold hover:bg-blue-600 transition sm:min-w-40"
            >
              {search_type === 'complete_species'
                ? 'Run Species PPI'
                : from_database === 'Gene_Name' && !selectedGeneCandidate
                  ? 'Find Matches'
                  : 'Search'}
            </button>

            <button
              onClick={handleCancel}
              className="bg-gray-800 text-white py-3 px-6 font-semibold hover:bg-gray-600 transition sm:min-w-40"
            >
              Cancel
            </button>
          </div>
          {loading && (
          <div className="text-center lg:text-left">
            <p className="text-blue-900 font-semibold mb-3">{loadingMessage}</p>
            <div className="flex flex-col gap-2">
              {(selected_databases.length > 0 ? selected_databases:['String', 'IntAct', 'BioGrid', 'Corum', 'Predictomes', 'HuRI']).map(db => (
                <div key={db} className="flex items-center gap-2 text-gray-600 justify-center lg:justify-start">
                    <div className="animate-pulse w-2 h-2  bg-blue-900"></div>
                    Searching {db}...
                </div>
              ))}
          </div>
        </div>
          )}
        </div>
        {search_type === 'single_search' && from_database === 'Gene_Name' && geneCandidates.length > 0 && (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-6 lg:col-span-2">
            <h3 className="text-lg font-semibold text-slate-900">Matched UniProt Entries</h3>
            <p className="mt-1 text-sm text-slate-600">
              Select the intended entry to continue the interaction search.
            </p>
            <div className="mt-4 flex flex-col gap-3">
              {geneCandidates.map(candidate => (
                <button
                  key={candidate.primary_accession}
                  type="button"
                  onClick={() => handleGeneCandidateSelect(candidate)}
                  className={`rounded-xl border px-4 py-4 text-left shadow-sm transition ${
                    selectedGeneCandidate?.primary_accession === candidate.primary_accession
                      ? 'border-blue-700 bg-blue-50 ring-2 ring-blue-200'
                      : 'border-slate-200 bg-white hover:border-slate-400 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex flex-col gap-1">
                    <span className="font-semibold text-slate-900">
                      {candidate.primary_accession} {candidate.reviewed ? '• Reviewed' : '• Unreviewed'}
                    </span>
                    <span className="text-sm text-slate-700">
                      {candidate.gene_names.length > 0 ? candidate.gene_names.join(', ') : 'No gene names returned'}
                    </span>
                    <span className="text-sm text-slate-600">
                      {candidate.protein_name || 'No protein name returned'}
                    </span>
                    <span className="text-xs text-slate-500">
                      {candidate.organism_name} • Taxonomy ID: {candidate.tax_id}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {search_type === 'complete_species' && speciesJob && (
        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-md">
          <div className="rounded-2xl bg-slate-50 p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Complete Species PPI Summary</h3>
                <p className="mt-1 text-sm text-slate-600">
                  Species: <span className="font-semibold text-slate-800">{speciesJob.species_name}</span>
                  {' '}• Taxonomy ID: <span className="font-semibold text-slate-800">{speciesJob.tax_id}</span>
                </p>
              </div>
              <p className="text-sm text-slate-600">
                Status:{' '}
                <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${STATUS_STYLES[speciesJob.status] || STATUS_STYLES.pending}`}>
                  {speciesJob.status}
                </span>
              </p>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {(speciesJob.selected_databases || []).map(dbName => (
                <span
                  key={dbName}
                  className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${DATABASE_STYLES[dbName]?.chip || 'bg-slate-100 text-slate-700 border-slate-200'}`}
                >
                  {dbName}
                </span>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={() => setspeciesLogOpen(!speciesLogOpen)}
            className="mt-5 flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-5 py-4 text-left transition hover:border-slate-300 hover:bg-slate-50"
          >
            <div>
              <p className="font-semibold text-slate-900">Job Log</p>
              <p className="text-sm text-slate-500">Open the database-by-database progress details</p>
            </div>
            <span className="text-2xl text-slate-500">{speciesLogOpen ? '−' : '+'}</span>
          </button>

          {speciesLogOpen && (
            <div className="mt-5 flex flex-col gap-3">
              {Object.entries(speciesJob.database_statuses || {}).map(([dbName, status]) => (
                <div
                  key={dbName}
                  className={`rounded-2xl border p-4 ${DATABASE_STYLES[dbName]?.surface || 'border-slate-200 bg-slate-50'}`}
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`h-3 w-3 rounded-full ${DATABASE_STYLES[dbName]?.accent || 'bg-slate-400'}`}></div>
                      <span className={`font-semibold ${DATABASE_STYLES[dbName]?.label || 'text-slate-800'}`}>{dbName}</span>
                    </div>
                    <span className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${STATUS_STYLES[status.status] || STATUS_STYLES.pending}`}>
                      {status.status}
                    </span>
                  </div>

                  <div className="mt-3 grid gap-3 text-sm text-slate-700 md:grid-cols-2 xl:grid-cols-3">
                    <div>
                      <span className="font-semibold text-slate-900">Pairs:</span> {status.pair_count}
                    </div>
                    <div className="md:col-span-1 xl:col-span-2">
                      <span className="font-semibold text-slate-900">Log:</span> {status.message}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {speciesJob.error && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {speciesJob.error}
            </div>
          )}

          {speciesJob.status === 'completed' && <SpeciesDownloadPanel job={speciesJob} />}
        </div>
      )}
      </div>
    </section>
    </div>
  )
}

export default SearchSection
