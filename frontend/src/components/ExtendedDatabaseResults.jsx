import DatabaseResultCard from './DatabaseResultCard'

const CONFIG = {
  ComplexPortal: {
    label: 'Complex Portal', subtitle: 'Curated and human predicted complex co-membership', color: 'bg-cyan-700',
    columns: [['Interactor_A', 'UniProt'], ['complex_name', 'Complex'], ['complex_id', 'Complex ID'], ['Complex_Type', 'Complex source']],
  },
  Reactome: {
    label: 'Reactome', subtitle: 'Reactome interactor overlay (IntAct evidence)', color: 'bg-lime-700',
    columns: [['Interactor_Gene_Name', 'Gene'], ['Interactor_A', 'UniProt'], ['Evidence_Record_Count', 'Evidence count'], ['Confidence_Score', 'Score'], ['Evidence_Source', 'Evidence source']],
  },
  Signor: {
    label: 'SIGNOR', subtitle: 'Directed causal signalling relationships', color: 'bg-red-700',
    columns: [['Regulator_Gene_Name', 'Regulator'], ['Target_Gene_Name', 'Target'], ['Effect', 'Effect'], ['Mechanism', 'Mechanism'], ['Confidence_Score', 'Score'], ['PubMed_Ids', 'PubMed']],
  },
  Hippie: {
    label: 'HIPPIE', subtitle: 'Human integrated PPI confidence layer', color: 'bg-teal-700',
    columns: [['Interactor_Gene_Name', 'Gene'], ['Interactor_A', 'UniProt'], ['Confidence_Score', 'Score'], ['Source_Count', 'Sources'], ['Experiment_Count', 'Experiments']],
  },
  HuMap: {
    label: 'hu.MAP 3.0', subtitle: 'Machine-learning predicted human interactions', color: 'bg-violet-700',
    columns: [['Interactor_A', 'UniProt'], ['Confidence_Score', 'ML probability'], ['Evidence_Class', 'Evidence class']],
  },
  Mint: {
    label: 'MINT', subtitle: 'Experimentally curated interactions via PSICQUIC', color: 'bg-pink-700',
    columns: [['Interactor_Gene_Name', 'Gene'], ['Interactor_A', 'UniProt'], ['Interaction_Detection_Method', 'Method'], ['PubMed_Ids', 'PubMed'], ['Confidence_Score', 'Score']],
  },
}

const displayValue = (value) => {
  if (Array.isArray(value)) return value.length > 0 ? value.join(', ') : '–'
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  return value === null || value === undefined || value === '' || value === '-' ? '–' : String(value)
}

const ExtendedDatabaseResults = ({ dbKey, data }) => {
  const config = CONFIG[dbKey]
  const payload = data?.[dbKey]
  const info = payload?.[0]?.info || {}
  const interactions = payload?.[1]?.Interactors || []
  if (!config) return null

  return (
    <DatabaseResultCard className="rounded-2xl"
        name={config.label}
        subtitle={config.subtitle}
        count={interactions.length}
        color={config.color}
        databaseLink={info.Database_Link}
      >
      {info.Overlap_Warning ? (
        <p className="border-b border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-900">{info.Overlap_Warning}</p>
      ) : null}
      {info.Error ? (
        <p className="border-b border-rose-200 bg-rose-50 px-6 py-3 text-sm text-rose-900">{info.Error}</p>
      ) : null}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Rank</th>
              {config.columns.map(([, label]) => <th key={label} className="px-4 py-3">{label}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {interactions.slice(0, 200).map((interaction, index) => (
              <tr key={`${interaction.SIGNOR_ID || interaction.complex_id || interaction.Interactor_A}-${index}`} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-slate-400">{index + 1}</td>
                {config.columns.map(([field]) => (
                  <td key={field} className="max-w-sm px-4 py-3 text-slate-700">{displayValue(interaction[field])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {interactions.length > 200 ? (
        <p className="border-t border-slate-100 px-6 py-3 text-sm text-slate-500">Showing the first 200 of {interactions.length} rows. Downloads include every row.</p>
      ) : null}
    </DatabaseResultCard>
  )
}

export default ExtendedDatabaseResults
