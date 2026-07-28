import DBHeader from './DBHeader'
import DBTable from './DBTable'
import MetadataCard from './MetaDataCard'

const CorumResults = ({ data }) => {
    const info = data.Corum[0].info
    const Interactions = data.Corum[1].Interactors

    const headers = [
        { label: 'Interactor' },
        { label: 'Gene Name' },
        { label: 'Organism' },
        { label: 'Link' }
    ]

    const rows = Interactions.map((i) => (
        <>
            <td className="px-4 py-3 font-semibold text-indigo-700">{i.Interactor_A}</td>
            <td className="px-4 py-3 text-gray-700">{i.Interactor_Gene_Name || '-'}</td>
            <td className="px-4 py-3 text-gray-500 italic">{i.Organism}</td>
            <td className="px-4 py-3">
                <a href={i.Interactor_Link} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline font-medium">View ↗</a>
            </td>
        </>
    ))

    return (
        <div className="bg-white  shadow-md mb-8 overflow-hidden">
            <DBHeader name="CORUM" subtitle="Curated mammalian protein complex database" count={Interactions.length} color="bg-amber-700" databaseLink={info.Database_Link} />
            <MetadataCard fields={[
                { label: 'Complex Name', value: info.complex_name },
                { label: 'Cell Line', value: info.cell_line },
                { label: 'Purification Methods', value: info.Purification_Method },
            ]} />
            <div className="p-6">
    {Interactions.length > 0 ? (
        <DBTable headers={headers} rows={rows} />
    ) : (
        <div className="bg-gray-50 border border-dashed border-gray-300  p-6 text-center text-gray-500">
            No interactions found in Corum.
        </div>
    )}
</div>
        </div>
    )
}

export default CorumResults
