def flatten_results(results, selected_databases):
    rows = []
    for data in results[1]['output']:

        if "BioGrid" in data and "BioGrid" in selected_databases:
            biogrid_interactions=data["BioGrid"][1]['Interactors']
            for interaction in biogrid_interactions:
                temp={}
                temp["Database"] = "BioGrid"
                temp["Interactor_A"]=interaction.get("Interactor_A",'-')
                temp["Interactor_B"]=interaction.get("Interactor_B",'-')
                temp["organism"]=interaction.get("organism",'-')
                temp["Interaction_Detection_Method"]=interaction.get("Interaction_Detection_Method",'-')
                temp["Interaction_Type"]=interaction.get("Interaction_Type",'-')
                temp["Confidence_Score"]=interaction.get("Confidence_Score",'-')
                rows.append(temp)
        
        if "Corum" in data and "Corum" in selected_databases:
            corum_interactions=data["Corum"][1]['Interactors']
            corum_info=data['Corum'][0]['info']
            for interaction in corum_interactions:
                temp={}
                temp["Database"] = "Corum"
                temp["complex_name"]=corum_info.get("complex_name",'-')
                temp["cell_line"]=corum_info.get("cell_line",'-')
                temp["Purification_Method"]=corum_info.get("Purification_Method",'-')
                temp["Interactor_A"]=interaction.get("Interactor_A",'-')
                temp["Interactor_B"]=interaction.get("Interactor_B",'-')
                temp["Organism"]=interaction.get("Organism",'-')
                rows.append(temp)
        
        if "Predictomes" in data and "Predictomes" in selected_databases:
            predictomes_interactions=data["Predictomes"][1]['Interactors']
            for interaction in predictomes_interactions:
                temp={}
                temp["Database"] = "Predictomes"
                temp["Interactor_A"]=interaction.get("Interactor_A",'-')
                temp["Interactor_B"]=interaction.get("Interactor_B",'-')
                temp["spoc_score"]=interaction.get("spoc_score",'-')
                temp["kirc_score"]=interaction.get("kirc_score",'-')
                temp["num_unique_contacts"]=interaction.get("num_unique_contacts",'-')
                rows.append(temp)

        if "String" in data and "String" in selected_databases:
            string_direct_interactions=data["String"][1]['Direct_Interactions']
            for interactions in string_direct_interactions:
                temp={}
                temp["Database"] = "String"
                temp["Interactor_A"]=interactions.get("Interactor_A",'-')
                temp["Interactor_B"]=interactions.get("Interactor_B",'-')
                temp["spoc_score"]=interactions.get("spoc_score",'-')
                temp["kirc_score"]=interactions.get("kirc_score",'-')
                temp["Organism"]=interactions.get("Organism",'-')
                temp["combined_score"]=interactions.get("combined_score",'-')
                temp["gene_neighbourhood_score"]=interactions.get("gene_neighbourhood_score",'-')
                temp["gene_fusion_score"]=interactions.get("gene_fusion_score",'-')
                temp["phylogenetic_profile_score"]=interactions.get("phylogenetic_profile_score",'-')
                temp["gene_fusion_score"]=interactions.get("gene_fusion_score",'-')
                temp["experimental_score"]=interactions.get("experimental_score",'-')
                temp["coexpression_score"]=interactions.get("coexpression_score",'-')
                temp["textmining_score"]=interactions.get("textmining_score",'-')
                temp["database_score"]=interactions.get("database_score",'-')
                rows.append(temp)

            string_indirect_interactions=data["String"][2]['Indirect_Interactions']
            for interactions in string_indirect_interactions:
                temp={}
                temp["Database"] = "String"
                temp["Interactor_A"]=interactions.get("Interactor_A",'-')
                temp["Interactor_B"]=interactions.get("Interactor_B",'-')
                temp["Organism"]=interactions.get("Organism",'-')
                temp["combined_score"]=interactions.get("combined_score",'-')
                temp["gene_neighbourhood_score"]=interactions.get("gene_neighbourhood_score",'-')
                temp["gene_fusion_score"]=interactions.get("gene_fusion_score",'-')
                temp["phylogenetic_profile_score"]=interactions.get("phylogenetic_profile_score",'-')
                temp["gene_fusion_score"]=interactions.get("gene_fusion_score",'-')
                temp["experimental_score"]=interactions.get("experimental_score",'-')
                temp["coexpression_score"]=interactions.get("coexpression_score",'-')
                temp["textmining_score"]=interactions.get("textmining_score",'-')
                temp["database_score"]=interactions.get("database_score",'-')
                rows.append(temp)

        if "IntAct" in data and "IntAct" in selected_databases:
            interactions=data["IntAct"][1]['Interactions']
            for interaction in interactions:
                temp={}
                temp["Database"] = "IntAct"
                temp["Interactor_A"]=interaction.get("Interactor_A",'-')
                temp["Interactor_B"]=interaction.get("Interactor_B",'-')
                temp["Num_Interaction_IntAct"]=interaction.get("Num_Interaction_IntAct",'-')
                temp["Minimum_feature_count"]=interaction.get("Minimum_feature_count",'-')
                temp["Maximum_feature_count"]=interaction.get("Maximum_feature_count",'-')
                temp["Interaction_Score_Intact"]=interaction.get("Interaction_Score_Intact",'-')
                temp["Unique_Identification_Methods"]=interaction.get("Unique_Identification_Methods",'-')
                temp["PubMed_Ids"]=interaction.get("PubMed_Ids",'-')
                rows.append(temp)

        if "HuRI" in data and "HuRI" in selected_databases:
            interactions=data["HuRI"][1].get('Interactors', data["HuRI"][1].get('Interactions', []))
            for interaction in interactions:
                temp={}
                temp["Database"] = "HuRI"
                temp["Interactor_A"]=interaction.get("Interactor_A",'-')
                temp["Interactor_B"]=interaction.get("Interactor_B",'-')
                temp["Interactor_A_UniProt"]=interaction.get("Interactor_A_UniProt",'-')
                temp["Interactor_B_UniProt"]=interaction.get("Interactor_B_UniProt",'-')
                temp["Interactor_A_Ensembl"]=interaction.get("Interactor_A_Ensembl",'-')
                temp["Interactor_B_Ensembl"]=interaction.get("Interactor_B_Ensembl",'-')
                temp["Interactor_Gene_Name"]=interaction.get("Interactor_Gene_Name",'-')
                temp["Interactor_Gene_Name_A"]=interaction.get("Interactor_Gene_Name_A",'-')
                temp["Interactor_Gene_Name_B"]=interaction.get("Interactor_Gene_Name_B",'-')
                rows.append(temp)
    return rows
