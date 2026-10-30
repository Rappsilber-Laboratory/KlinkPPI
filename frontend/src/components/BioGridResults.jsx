import DBTable from './DBTable'
import DatabaseResultCard from './DatabaseResultCard'

const BioGridResults = ({ data }) => {
    const info = data.BioGrid[0].info
    const Interactions = data.BioGrid[1].Interactors

    const headers = [
        { label: 'Interactor' },
        { label: 'Gene Name' },
        { label: 'Organism' },
        { label: 'Detection Method', info: 'Experimental method used to detect the interaction' },
        { label: 'Interaction Type', info: 'Type of molecular interaction (physical, genetic etc.)' },
        { label: 'Confidence Score', info: 'BioGRID confidence score for this interaction' },
        { label: 'Link' }
    ]

    const rows = Interactions.map((i) => (
        <>
            <td className="px-4 py-3 font-semibold text-indigo-700">{i.Interactor_A}</td>
            <td className="px-4 py-3 text-gray-700">{i.Interactor_Gene_Name || '-'}</td>
            <td className="px-4 py-3 text-gray-500 italic">{i.organism}</td>
            <td className="px-4 py-3 text-gray-600 text-xs">{i.Interaction_Detection_Method}</td>
            <td className="px-4 py-3">
                <span className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full">{i.Interaction_Type}</span>
            </td>
            <td className="px-4 py-3 text-gray-600">{i.Confidence_Score}</td>
            <td className="px-4 py-3">
                <a href={i.Interactor_Link} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline font-medium">View ↗</a>
            </td>
        </>
    ))

    return (
        <DatabaseResultCard className="rounded-2xl" name="BioGRID" subtitle="Biological general repository for interaction datasets" count={Interactions.length} color="bg-emerald-700" databaseLink={info.Database_Link}>
            <div className="p-6">
    {Interactions.length > 0 ? (
        <DBTable headers={headers} rows={rows} />
    ) : (
        <div className="bg-gray-50 border border-dashed border-gray-300 rounded-lg p-6 text-center text-gray-500">
            No interactions found in BioGrid.
        </div>
    )}
            </div>
        </DatabaseResultCard>
    )
}

export default BioGridResults
