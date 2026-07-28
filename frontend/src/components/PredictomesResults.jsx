import DBHeader from './DBHeader'
import DBTable from './DBTable'

const PredictomesResults = ({ data }) => {
    const info = data.Predictomes[0].info
    const Interactions = data.Predictomes[1].Interactors

    const headers = [
        { label: 'Interactor' },
        { label: 'Gene Name' },
        { label: 'SPOC Score', info: 'Structural prediction of co-complexed proteins score' },
        { label: 'KIRC Score', info: 'Kinase-substrate relationship confidence score' },
        { label: 'Unique Contacts', info: 'Number of unique residue contacts predicted' },
        { label: 'Link' }
    ]

    const rows = Interactions.map((i) => (
        <>
            <td className="px-4 py-3 font-semibold text-indigo-700">{i.Interactor_A}</td>
            <td className="px-4 py-3 text-gray-700">{i.Interactor_Gene_Name || '-'}</td>
            <td className="px-4 py-3">
                <span className={`font-bold ${i.spoc_score >= 0.7 ? 'text-green-600' : i.spoc_score >= 0.5 ? 'text-yellow-600' : 'text-gray-600'}`}>
                    {i.spoc_score}
                </span>
            </td>
            <td className="px-4 py-3 text-gray-600">{i.kirc_score}</td>
            <td className="px-4 py-3 text-gray-600">{i.num_unique_contacts}</td>
            <td className="px-4 py-3">
                <a href={i.Interactor_Link} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline font-medium">View ↗</a>
            </td>
        </>
    ))

    return (
        <div className="bg-white  shadow-md mb-8 overflow-hidden">
            <DBHeader name="Predictomes" subtitle="Structural proteome-wide interaction predictions" count={Interactions.length} color="bg-indigo-700" databaseLink={info.Database_Link} />
            <div className="p-6">
    {Interactions.length > 0 ? (
        <DBTable headers={headers} rows={rows} />
    ) : (
        <div className="bg-gray-50 border border-dashed border-gray-300  p-6 text-center text-gray-500">
            No interactions found in Predictomes.
        </div>
    )}
</div>
        </div>
    )
}

export default PredictomesResults
