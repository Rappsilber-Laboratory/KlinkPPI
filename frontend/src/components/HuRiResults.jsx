import DBHeader from './DBHeader'
import DBTable from './DBTable'

const HuRiResults = ({ data }) => {
    const info = data.HuRI[0].info
    const Interactions = data.HuRI[1].Interactors

    const headers = [
        { label: 'Gene Name' },
        { label: 'Interactor UniProt' },
        { label: 'Interactor Ensembl' },
        { label: 'Link' }
    ]

    const rows = Interactions.map((i) => (
        <>
            <td className="px-4 py-3 text-gray-700">{i.Interactor_Gene_Name || '-'}</td>
            <td className="px-4 py-3 font-semibold text-indigo-700">{i.Interactor_A_UniProt || i.Interactor_A || '-'}</td>
            <td className="px-4 py-3 text-slate-600">{i.Interactor_A_Ensembl || '-'}</td>
            <td className="px-4 py-3">
                <a href={i.Interactor_Link} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline font-medium">View ↗</a>
            </td>
        </>
    ))

    return (
        <div className="bg-white  shadow-md mb-8 overflow-hidden">
            <DBHeader name="HuRI" subtitle="Human Reference Interactome — systematic Y2H screen" count={Interactions.length} color="bg-rose-700" databaseLink={info.Database_Link} />
            <div className="p-6">
    {Interactions.length > 0 ? (
        <DBTable headers={headers} rows={rows} />
    ) : (
        <div className="bg-gray-50 border border-dashed border-gray-300  p-6 text-center text-gray-500">
            No interactions found in HuRI.
        </div>
    )}
</div>
        </div>
    )
}

export default HuRiResults
