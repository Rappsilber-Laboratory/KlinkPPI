import { useState } from 'react'

const scoreInfo = [
    {label:'combined_score',info: "Overall confidence score combining all evidence channels"},
    {label:'gene_neighbourhood_score',info: "Score based on genomic proximity of genes"},
    {label:'gene_fusion_score',info: "Score based on gene fusion events across genomes"},
    {label:'phylogenetic_profile_score',info: "Score based on co-occurrence across species"},
    {label:'experimental_score',info: "Score from experimental data (co-IP, Y2H etc.)"},
    {label:'coexpression_score',info: "Score based on similar expression patterns"},
    {label:'textmining_score',info: "Score from co-mentions in scientific literature"},
    {label:'database_score',info: "Score from curated biological databases"}
]

const StringResults = ({ data }) => {
    const info = data.String[0].info
    const DirectInteractions = data.String[1].Direct_Interactions
    const IndirectInteractions = data.String[2].Indirect_Interactions
    const [showIndirect, setshowIndirect] = useState(false)




    const InfoButton = ({ column }) => {
        const [visible, setVisible] = useState(false);
    
        const description = scoreInfo.find(
            item=>item.label === column
        )?.info;
    
        return (
            <span className="relative inline-flex items-center">
                <button
                    onMouseEnter={() => setVisible(true)}
                    onMouseLeave={() => setVisible(false)}
                    className="w-5 h-5 rounded-full bg-blue-100 text-blue-600 border border-blue-300 text-xs font-bold flex items-center justify-center"
                >
                    i
                </button>
    
                {visible && (
                    <div
                        className="
                        absolute
                        top-8
                        left-1/2
                        -translate-x-1/2
                        z-50
                        max-w-sm
                        p-4
                        rounded-lg
                        bg-white
                        border
                        border-gray-200
                        shadow-xl
                        text-xs
                        font-normal
                        normal-case
                        text-gray-600
                        whitespace-normal
                        break-words
                        leading-relaxed
                        "
                    >
                        {description}
                    </div>
                )}
            </span>
        );
    };

    const InteractorTable = ({ interactions, type }) => (
        <div className="overflow-x-auto  border border-gray-200">
            <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
                    <tr>
                        {type === 'direct' ? (
                            <>
                                <th className="px-4 py-3">Rank</th>
                                <th className="px-4 py-3">Interactor</th>
                                <th className="px-4 py-3">Organism</th>
                                <th className="px-4 py-3">
                                    Combined Score
                                    <InfoButton column="combined_score" />
                                </th>
                                <th className="px-4 py-3">
                                    Experimental
                                    <InfoButton column="experimental_score" />
                                </th>
                                <th className="px-4 py-3">
                                    Coexpression
                                    <InfoButton column="coexpression_score" />
                                </th>
                                <th className="px-4 py-3">
                                    Textmining
                                    <InfoButton column="textmining_score" />
                                </th>
                                <th className="px-4 py-3">
                                    Database
                                    <InfoButton column="database_score" />
                                </th>
                                <th className="px-4 py-3">Link</th>
                            </>
                        ) : (
                            <>
                                <th className="px-4 py-3">Rank</th>
                                <th className="px-4 py-3">Interactor A</th>
                                <th className="px-4 py-3">Interactor B</th>
                                <th className="px-4 py-3">Organism</th>
                                <th className="px-4 py-3">
                                    Combined Score
                                    <InfoButton column="combined_score" />
                                </th>
                                <th className="px-4 py-3">
                                    Experimental
                                    <InfoButton column="experimental_score" />
                                </th>
                                <th className="px-4 py-3">
                                    Textmining
                                    <InfoButton column="textmining_score" />
                                </th>
                                <th className="px-4 py-3">Link A</th>
                                <th className="px-4 py-3">Link B</th>
                            </>
                        )}
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {interactions.map((interaction, index) => (
                        <tr key={index} className="hover:bg-indigo-50 transition">
                            {type === 'direct' ? (
                                <>
                                    <td className="px-4 py-3 text-gray-400 font-medium">{index + 1}</td>
                                    <td className="px-4 py-3 font-semibold text-indigo-700">{interaction.Interactor_A}</td>
                                    <td className="px-4 py-3 text-gray-500 italic">{interaction.Organism}</td>
                                    <td className="px-4 py-3">
                                        <span className={`font-bold ${interaction.combined_score >= 0.9 ? 'text-green-600' : interaction.combined_score >= 0.7 ? 'text-yellow-600' : 'text-gray-600'}`}>
                                            {interaction.combined_score}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-gray-600">{interaction.experimental_score}</td>
                                    <td className="px-4 py-3 text-gray-600">{interaction.coexpression_score}</td>
                                    <td className="px-4 py-3 text-gray-600">{interaction.textmining_score}</td>
                                    <td className="px-4 py-3 text-gray-600">{interaction.database_score}</td>
                                    <td className="px-4 py-3">
                                        <a href={interaction.Interactor_Link} target="_blank" rel="noreferrer"
                                            className="text-indigo-600 hover:underline font-medium">
                                            View ↗
                                        </a>
                                    </td>
                                </>
                            ) : (
                                <>
                                    <td className="px-4 py-3 text-gray-400 font-medium">{index + 1}</td>
                                    <td className="px-4 py-3 font-semibold text-indigo-700">{interaction.Interactor_A}</td>
                                    <td className="px-4 py-3 font-semibold text-indigo-700">{interaction.Interactor_B}</td>
                                    <td className="px-4 py-3 text-gray-500 italic">{interaction.Organism}</td>
                                    <td className="px-4 py-3">
                                        <span className={`font-bold ${interaction.combined_score >= 0.9 ? 'text-green-600' : interaction.combined_score >= 0.7 ? 'text-yellow-600' : 'text-gray-600'}`}>
                                            {interaction.combined_score}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-gray-600">{interaction.experimental_score}</td>
                                    <td className="px-4 py-3 text-gray-600">{interaction.textmining_score}</td>
                                    <td className="px-4 py-3">
                                        <a href={interaction.Interactor_Link_A} target="_blank" rel="noreferrer"
                                            className="text-indigo-600 hover:underline font-medium">
                                            View ↗
                                        </a>
                                    </td>
                                    <td className="px-4 py-3">
                                        <a href={interaction.Interactor_Link_B} target="_blank" rel="noreferrer"
                                            className="text-indigo-600 hover:underline font-medium">
                                            View ↗
                                        </a>
                                    </td>
                                </>
                            )}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )

    return (
        <div className="bg-white  shadow-md mb-8 overflow-hidden">

            {/* Header */}
            <div className="bg-sky-700 px-6 py-4 flex justify-between items-center">
                <div>
                    <h2 className="text-white text-xl font-bold">
                        {info.Database_Link ? (
                            <a
                                href={info.Database_Link}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 hover:underline focus:outline-none focus:ring-2 focus:ring-white/80"
                                aria-label="Open STRING for the searched protein"
                            >
                                STRING <span aria-hidden="true">↗</span>
                            </a>
                        ) : 'STRING'}
                    </h2>
                    <p className="text-white/80 text-sm">Functional protein interaction network</p>
                </div>
                <span className="bg-white text-sky-700 text-xs font-bold px-3 py-1 ">
                    {DirectInteractions.length} direct · {IndirectInteractions.length} indirect
                </span>
            </div>

            <div className="p-6 flex flex-col gap-8">

                {/* Direct interactions */}
                <div>
                    <h3 className="text-gray-700 font-semibold text-base mb-3">
                        Direct Interactions
                        <span className="ml-2 text-xs text-gray-400 font-normal">
                            Proteins that directly interact with your query
                        </span>
                    </h3>
                    {DirectInteractions.length > 0 ? (
                        <InteractorTable
                            interactions={DirectInteractions}
                            type="direct"
                            />
                        ) : (
                            <div className="bg-gray-50 border border-dashed border-gray-300  p-6 text-center text-gray-500">
                                No direct interactions found.
                            </div>
                    )}
                </div>

                {/* Indirect interactions — collapsible */}
                <div>
                    <button
                        onClick={() => setshowIndirect(!showIndirect)}
                        className="flex items-center gap-2 text-gray-700 font-semibold text-base mb-3 hover:text-indigo-600 transition"
                    >
                        {showIndirect ? '▼' : '▶'} Indirect Interactions
                        <span className="text-xs text-gray-400 font-normal">
                            Interactions between partners of your query
                        </span>
                    </button>
                    {showIndirect && (
                        IndirectInteractions.length > 0 ? (
                    <InteractorTable
                        interactions={IndirectInteractions}
                        type="indirect"
                    />
                        ) : (
                        <div className="bg-gray-50 border border-dashed border-gray-300  p-6 text-center text-gray-500">
                            No indirect interactions found.
                        </div>
                        )
                    )}
                </div>

            </div>
        </div>
    )
}

export default StringResults
