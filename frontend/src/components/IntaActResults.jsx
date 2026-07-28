import DBHeader from './DBHeader'
import DBTable from './DBTable'

const IntActResults = ({ data }) => {
    const info = data.IntAct[0].info
    const Interactions = data.IntAct[1].Interactions

    const headers = [
        { label: 'Interactor' },
        { label: 'Gene Name' },
        { label: 'Organism' },
        { label: '# Interactions', info: 'Total number of interactions recorded in IntAct' },
        { label: 'Interaction Score', info: 'MIscore — confidence score based on experimental evidence' },
        { label: 'Detection Methods', info: 'Unique experimental methods used to detect this interaction' },
        { label: 'PubMed IDs' },
        { label: 'Link' }
    ]

    const rows = Interactions.map((i) => (
        <>
            <td className="px-4 py-3 font-semibold text-indigo-700">{i.Interactor_A}</td>
            <td className="px-4 py-3 text-gray-700">{i.Interactor_Gene_Name || '-'}</td>
            <td className="px-4 py-3 text-gray-500 italic">{i.organism}</td>
            <td className="px-4 py-3 text-gray-600">{i.Num_Interaction_IntAct}</td>
            <td className="px-4 py-3">
                <span className={`font-bold ${i.Interaction_Score_Intact >= 0.7 ? 'text-green-600' : i.Interaction_Score_Intact >= 0.4 ? 'text-yellow-600' : 'text-gray-600'}`}>
                    {i.Interaction_Score_Intact}
                </span>
            </td>
            <td className="px-4 py-3 text-gray-600 text-xs">{i.Unique_Identification_Methods}</td>
            <td className="px-4 py-3 text-gray-600 text-xs">{i.PubMed_Ids}</td>
            <td className="px-4 py-3">
                <a href={i.Interactor_Link} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline font-medium">View ↗</a>
            </td>
        </>
    ))

    return (
        <div className="bg-white  shadow-md mb-8 overflow-hidden">
            <DBHeader name="IntAct" subtitle="Experimentally verified molecular interactions" count={Interactions.length} color="bg-fuchsia-700" databaseLink={info.Database_Link} />
            <div className="p-6">
    {Interactions.length > 0 ? (
        <DBTable headers={headers} rows={rows} />
    ) : (
        <div className="bg-gray-50 border border-dashed border-gray-300  p-6 text-center text-gray-500">
            No interactions found in IntAct.
        </div>
    )}
</div>
        </div>
    )
}

export default IntActResults
