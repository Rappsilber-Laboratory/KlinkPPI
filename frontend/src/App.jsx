import { useState } from 'react'
import './App.css'
import Navbar from './components/Navbar'
import OrganismCoveragePlots from './components/OrganismCoveragePlots'
import SearchSection from './components/SearchSection'
import InputSummary from './components/InputSummary'
import InteractionOverlapLog from './components/InteractionOverlapLog'
import StringResults from './components/StringResults'
import PredictomesResults from './components/PredictomesResults'
import BioGridResults from './components/BioGridResults'
import CorumResults from './components/CorumResults'
import IntactResults from './components/IntaActResults'
import HuRiResults from './components/HuRiResults'
import DownloadPanel from './components/DownloadPanel'

const DATABASE_HEADER_COLORS = {
    STRING: 'bg-sky-700',
    BioGRID: 'bg-emerald-700',
    IntAct: 'bg-fuchsia-700',
    Predictomes: 'bg-indigo-700',
    CORUM: 'bg-amber-700',
    HuRI: 'bg-rose-700',
}

const getDBStatus = (dbData, key, interactorKey) => {
    if (!dbData) return 'not_selected'
    const value = dbData[key]
    if (typeof value === 'string') return 'not_supported'
    if (!value) return 'not_supported'
    const interactors = value[1]?.[interactorKey]
    if (!interactors || interactors.length === 0) return 'no_data'
    return 'valid'
}

const NoResults = ({ dbName, reason }) => (
    <div className="bg-white rounded-2xl shadow-md mb-8 overflow-hidden">
        <div className={`${DATABASE_HEADER_COLORS[dbName] || 'bg-slate-600'} px-6 py-4 flex justify-between items-center`}>
            <div>
                <h2 className="text-white text-lg font-semibold tracking-wide">{dbName}</h2>
                <p className="text-white/80 text-xs mt-0.5">
                    {reason === 'not_supported' ? 'Organism not supported' : 'No data found'}
                </p>
            </div>
        </div>
        <div className="px-6 py-8 text-center">
            {reason === 'not_supported' ? (
                <>
                    <p className="text-2xl mb-2"></p>
                    <p className="font-medium text-gray-500">
                        {dbName} does not support the selected organism
                    </p>
                    <p className="text-sm text-gray-400 mt-1">
                        Try a different taxonomy ID or deselect this database
                    </p>
                </>
            ) : (
                <>
                    <p className="text-2xl mb-2"></p>
                    <p className="font-medium text-gray-500">
                        No interactions found for this protein in {dbName}
                    </p>
                    <p className="text-sm text-gray-400 mt-1">
                        The protein may not be present in the {dbName} database
                    </p>
                </>
            )}
        </div>
    </div>
)



function App() {
    const [results, setresults] = useState(null)

    const stringData = results?.[1]?.output?.find(db => db.String)
    const intactData = results?.[1]?.output?.find(db => db.IntAct)
    const corumData = results?.[1]?.output?.find(db => db.Corum)
    const predictomesData = results?.[1]?.output?.find(db => db.Predictomes)
    const huriData = results?.[1]?.output?.find(db => db.HuRI)
    const biogridData = results?.[1]?.output?.find(db => db.BioGrid)

    const stringStatus = getDBStatus(stringData, 'String', 'Direct_Interactions')
    const intactStatus = getDBStatus(intactData, 'IntAct', 'Interactions')
    const biogridStatus = getDBStatus(biogridData, 'BioGrid', 'Interactors')
    const corumStatus = getDBStatus(corumData, 'Corum', 'Interactors')
    const predictomesStatus = getDBStatus(predictomesData, 'Predictomes', 'Interactors')
    const huriStatus = getDBStatus(huriData, 'HuRI', 'Interactors')

    return (
        <div className="min-h-screen flex flex-col">
            <Navbar />
            <main className="flex-1">
                <OrganismCoveragePlots />
                <SearchSection setresults={setresults} />

                {results && (
                    <div className="w-full max-w-[110rem] mx-auto px-4 py-10 sm:px-6">
                        <InteractionOverlapLog results={results} />

                        <InputSummary input={results[0].Input} />

                        <DownloadPanel
                            results={results}
                            uniprot_id={results[0].Input.UniProtId}
                            tax_id={results[0].Input.TaxonomyId}
                        />

                        {stringData && (stringStatus === 'valid'
                            ? <StringResults data={stringData} />
                            : <NoResults dbName="STRING" reason={stringStatus} />)}     


                        {biogridData && (biogridStatus === 'valid'
                            ? <BioGridResults data={biogridData} />
                            : <NoResults dbName="BioGRID" reason={biogridStatus} />)}

                        {intactData && (intactStatus === 'valid'
                            ? <IntactResults data={intactData} />
                            : <NoResults dbName="IntAct" reason={intactStatus} />)}

                        {predictomesData && (predictomesStatus === 'valid'
                            ? <PredictomesResults data={predictomesData} />
                            : <NoResults dbName="Predictomes" reason={predictomesStatus} />)}

                        {corumData && (corumStatus === 'valid'
                            ? <CorumResults data={corumData} />
                            : <NoResults dbName="CORUM" reason={corumStatus} />)}

                        {huriData && (huriStatus === 'valid'
                            ? <HuRiResults data={huriData} />
                            : <NoResults dbName="HuRI" reason={huriStatus} />)}
                    </div>
                )}
            </main>

            <footer className="border-t border-slate-300 bg-slate-100 px-4 py-6 text-sm text-slate-700 sm:px-6">
                <div className="mx-auto flex w-full max-w-[110rem] flex-col gap-2">
                    <p className="font-medium text-slate-900">Free access statement</p>
                    <p>
                        KlinkPPI is provided as a free-access resource. Lab information:{' '}
                        <a
                            href="https://www.rappsilberlab.org/"
                            target="_blank"
                            rel="noreferrer"
                            className="font-medium text-slate-900 underline decoration-slate-400 underline-offset-2 hover:decoration-slate-900"
                        >
                            Rappsilber Lab
                        </a>
                    </p>
                </div>
            </footer>
        </div>
    )
}

export default App
