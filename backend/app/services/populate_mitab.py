COMMON_COLUMNS = [
    "#ID(s) interactor A",
    "ID(s) interactor B",
    "Alias(es) interactor A",
    "Alias(es) interactor B",
    "Taxid interactor A",
    "Taxid interactor B",
    "Interaction detection method(s)",
    "Interaction type(s)",
    "Publication Identifier(s)",
    "Source database(s)",
    "Confidence value(s)",
]


STRING_SCORE_FIELDS = [
    ("combined_score", "string-combined-score"),
    ("gene_neighbourhood_score", "string-gene-neighbourhood-score"),
    ("gene_fusion_score", "string-gene-fusion-score"),
    ("phylogenetic_profile_score", "string-phylogenetic-profile-score"),
    ("experimental_score", "string-experimental-score"),
    ("coexpression_score", "string-coexpression-score"),
    ("textmining_score", "string-textmining-score"),
    ("database_score", "string-database-score"),
]

PREDICTOMES_SCORE_FIELDS = [
    ("spoc_score", "predictomes-spoc-score"),
    ("kirc_score", "predictomes-kirc-score"),
    ("num_unique_contacts", "predictomes-unique-contacts"),
]

INTACT_SCORE_FIELDS = [
    ("Interaction_Score_Intact", "intact-miscore"),
    ("Num_Interaction_IntAct", "intact-record-count"),
    ("Minimum_feature_count", "intact-minimum-feature-count"),
    ("Maximum_feature_count", "intact-maximum-feature-count"),
]

BIOGRID_TYPE_CODES = {
    "physical association": 'psi-mi:"MI:0915"(physical association)',
    "direct interaction": 'psi-mi:"MI:0407"(direct interaction)',
    "association": 'psi-mi:"MI:0914"(association)',
    "colocalization": 'psi-mi:"MI:0403"(colocalization)',
    "genetic interference": 'psi-mi:"MI:0254"(genetic interference)',
    "synthetic lethality": 'psi-mi:"MI:0797"(synthetic lethality)',
}

METHOD_TO_MI = {
    "pull down": 'psi-mi:"MI:0096"(pull down)',
    "coimmunoprecipitation": 'psi-mi:"MI:0019"(coimmunoprecipitation)',
    "anti bait coip": 'psi-mi:"MI:0006"(anti bait coimmunoprecipitation)',
    "anti tag coip": 'psi-mi:"MI:0007"(anti tag coimmunoprecipitation)',
    "anti tag coimmunoprecipitation": 'psi-mi:"MI:0007"(anti tag coimmunoprecipitation)',
    "affinity chromatography technology": 'psi-mi:"MI:0004"(affinity chromatography technology)',
    "tandem affinity purification": 'psi-mi:"MI:0676"(tandem affinity purification)',
    "far western blotting": 'psi-mi:"MI:0047"(far western blotting)',
    "two hybrid": 'psi-mi:"MI:0018"(two hybrid)',
    "validated two hybrid": 'psi-mi:"MI:1356"(validated two hybrid)',
    "two hybrid array": 'psi-mi:"MI:0397"(two hybrid array)',
    "two hybrid pooling approach": 'psi-mi:"MI:0398"(two hybrid pooling approach)',
    "two hybrid prey pooling approach": 'psi-mi:"MI:1112"(two hybrid prey pooling approach)',
    "spr": 'psi-mi:"MI:0107"(surface plasmon resonance)',
    "surface plasmon resonance": 'psi-mi:"MI:0107"(surface plasmon resonance)',
    "fluorescence resonance energy transfer": 'psi-mi:"MI:0055"(fluorescence resonance energy transfer)',
    "fret": 'psi-mi:"MI:0055"(fluorescence resonance energy transfer)',
    "bioluminescence resonance energy transfer": 'psi-mi:"MI:0017"(bioluminescence resonance energy transfer)',
    "bret": 'psi-mi:"MI:0017"(bioluminescence resonance energy transfer)',
    "x-ray diffraction": 'psi-mi:"MI:0114"(x-ray crystallography)',
    "x-ray crystallography": 'psi-mi:"MI:0114"(x-ray crystallography)',
    "3d-em-single": 'psi-mi:"MI:2339"(electron microscopy 3d single particle reconstruction)',
    "electron microscopy 3d single particle reconstruction": 'psi-mi:"MI:2339"(electron microscopy 3d single particle reconstruction)',
    "electron microscopy": 'psi-mi:"MI:0040"(electron microscopy)',
    "protein complementation assay": 'psi-mi:"MI:0090"(protein complementation assay)',
    "protease assay": 'psi-mi:"MI:0428"(protease assay)',
    "molecular sieving": 'psi-mi:"MI:0071"(molecular sieving)',
    "gel filtration": 'psi-mi:"MI:0071"(molecular sieving)',
    "size exclusion chromatography": 'psi-mi:"MI:0071"(molecular sieving)',
    "cross-linking study": 'psi-mi:"MI:0030"(cross-linking study)',
    "protein array": 'psi-mi:"MI:0089"(protein array)',
    "mass spectrometry": 'psi-mi:"MI:0427"(mass spectrometry)',
    "immunoprecipitation": 'psi-mi:"MI:0098"(immunoprecipitation)',
    "affinity purification": 'psi-mi:"MI:0004"(affinity chromatography technology)',
    "gst pull down": 'psi-mi:"MI:0079"(gst pull down)',
    "his pull down": 'psi-mi:"MI:0061"(his pull down)',
    "tap": 'psi-mi:"MI:0676"(tandem affinity purification)',
    "cell fractionation": 'psi-mi:"MI:0025"(cell fractionation)',
    "centrifugation": 'psi-mi:"MI:0027"(centrifugation)',
    "density gradient centrifugation": 'psi-mi:"MI:0031"(density gradient centrifugation)',
    "unspecified method": 'psi-mi:"MI:0686"(unspecified method)',
}


def _has_value(value) -> bool:
    return value is not None and value != "" and value != "-"


def _format_taxid(tax_id):
    return f"taxid:{tax_id}" if _has_value(tax_id) else "-"


def _base_row(final_columns: list, tax_id, tax_id_a=None, tax_id_b=None) -> dict:
    row = {column: "-" for column in final_columns}
    row["Taxid interactor A"] = _format_taxid(tax_id_a or tax_id)
    row["Taxid interactor B"] = _format_taxid(tax_id_b or tax_id)
    return row


def _join(values) -> str:
    cleaned = [str(value) for value in values if _has_value(value)]
    return "|".join(cleaned) if cleaned else "-"


def _gene_alias(gene_name) -> str:
    return f"hgnc.symbol:{gene_name}" if _has_value(gene_name) else "-"


def _score_values(interaction: dict, selected_columns: list, fields: list[tuple[str, str]]) -> str:
    values = []
    for field, label in fields:
        if field in selected_columns and _has_value(interaction.get(field)):
            values.append(f"{label}:{interaction.get(field)}")
    return _join(values)


def _format_method(method: str, prefix: str | None = None) -> str:
    if not _has_value(method):
        return "-"
    method = str(method)
    mapped = METHOD_TO_MI.get(method.lower(), method)
    return f"{prefix}:{mapped}" if prefix else mapped


def _format_methods(methods, prefix: str | None = None) -> str:
    if isinstance(methods, str):
        methods = [methods]
    return _join(_format_method(method, prefix) for method in (methods or []))


def _format_biogrid_type(value: str) -> str:
    if not _has_value(value):
        return "-"
    return BIOGRID_TYPE_CODES.get(str(value).lower(), str(value))


def _pubmed_values(pubmed_ids) -> str:
    if isinstance(pubmed_ids, str):
        pubmed_ids = [pubmed_ids]
    values = []
    for pubmed_id in pubmed_ids or []:
        if _has_value(pubmed_id):
            values.append(f"pubmed:{pubmed_id}")
    return _join(values)


def populate_string(data: list, final_columns: list, selected_columns: list, uniprot_id, tax_id):
    rows = []
    for section_name in ("Direct_Interactions", "Indirect_Interactions"):
        section_index = 1 if section_name == "Direct_Interactions" else 2
        for interaction in data[section_index].get(section_name, []):
            row = _base_row(final_columns, tax_id, interaction.get("organism_tax_id"), interaction.get("organism_tax_id"))
            row["#ID(s) interactor A"] = f"hgnc.symbol:{interaction.get('Interactor_A', '-')}"
            row["ID(s) interactor B"] = f"hgnc.symbol:{interaction.get('Interactor_B', '-')}"
            row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_A"))
            row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_B"))
            row["Interaction type(s)"] = "string-functional-association"
            row["Source database(s)"] = 'psi-mi:"MI:1014"(string)'
            row["Confidence value(s)"] = _score_values(interaction, selected_columns, STRING_SCORE_FIELDS)
            rows.append(row)
    return rows


def populate_predictomes(data: list, final_columns: list, selected_columns: list, uniprot_id, tax_id):
    rows = []
    for interaction in data[1]["Interactors"]:
        row = _base_row(final_columns, tax_id)
        row["#ID(s) interactor A"] = f"uniprotkb:{interaction.get('Interactor_A', '-')}"
        row["ID(s) interactor B"] = f"uniprotkb:{interaction.get('Interactor_B', '-')}"
        row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_Gene_Name"))
        row["Interaction type(s)"] = "predictomes-structural-prediction"
        row["Source database(s)"] = "predictomes"
        row["Confidence value(s)"] = _score_values(interaction, selected_columns, PREDICTOMES_SCORE_FIELDS)
        rows.append(row)
    return rows


def populate_intact(data: list, final_columns: list, selected_columns: list, uniprot_id, tax_id):
    rows = []
    for interaction in data[1]["Interactions"]:
        row = _base_row(final_columns, tax_id, interaction.get("organism_tax_id"), tax_id)
        row["#ID(s) interactor A"] = f"uniprotkb:{interaction.get('Interactor_A', '-')}"
        row["ID(s) interactor B"] = f"uniprotkb:{interaction.get('Interactor_B', '-')}"
        row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_Gene_Name"))
        row["Source database(s)"] = 'psi-mi:"MI:0469"(intact)'

        if "Unique_Identification_Methods" in selected_columns:
            row["Interaction detection method(s)"] = _format_methods(interaction.get("Unique_Identification_Methods"))
        if "PubMed_Ids" in selected_columns:
            row["Publication Identifier(s)"] = _pubmed_values(interaction.get("PubMed_Ids"))

        row["Confidence value(s)"] = _score_values(interaction, selected_columns, INTACT_SCORE_FIELDS)
        rows.append(row)
    return rows


def populate_huri(data: list, final_columns: list, selected_columns: list, uniprot_id, tax_id):
    rows = []
    interactions = data[1].get("Interactors", data[1].get("Interactions", []))
    for interaction in interactions:
        row = _base_row(final_columns, tax_id)
        interactor_a_uniprot = interaction.get("Interactor_A_UniProt")
        interactor_b_uniprot = interaction.get("Interactor_B_UniProt")
        interactor_a_ensembl = interaction.get("Interactor_A_Ensembl")
        interactor_b_ensembl = interaction.get("Interactor_B_Ensembl")
        row["#ID(s) interactor A"] = (
            f"uniprotkb:{interactor_a_uniprot}"
            if interactor_a_uniprot
            else f"ensembl:{interactor_a_ensembl or interaction.get('Interactor_A', '-')}"
        )
        row["ID(s) interactor B"] = (
            f"uniprotkb:{interactor_b_uniprot}"
            if interactor_b_uniprot
            else f"ensembl:{interactor_b_ensembl or interaction.get('Interactor_B', '-')}"
        )
        row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_Gene_Name_A") or interaction.get("Interactor_Gene_Name"))
        row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_Gene_Name_B"))
        row["Interaction type(s)"] = 'psi-mi:"MI:0407"(direct interaction)'
        row["Source database(s)"] = "huri"
        rows.append(row)
    return rows


def populate_biogrid(data: list, final_columns: list, selected_columns: list, uniprot_id, tax_id):
    rows = []
    for interaction in data[1]["Interactors"]:
        row = _base_row(final_columns, tax_id, interaction.get("organism_tax_id"), tax_id)
        row["#ID(s) interactor A"] = f"uniprotkb:{interaction.get('Interactor_A', '-')}"
        row["ID(s) interactor B"] = f"uniprotkb:{interaction.get('Interactor_B', '-')}"
        row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_Gene_Name"))
        row["Source database(s)"] = 'psi-mi:"MI:0463"(biogrid)'

        if "Interaction_Detection_Method" in selected_columns:
            row["Interaction detection method(s)"] = _format_method(interaction.get("Interaction_Detection_Method"))
        if "Interaction_Type" in selected_columns:
            row["Interaction type(s)"] = _format_biogrid_type(interaction.get("Interaction_Type"))
        if "Confidence_Score" in selected_columns and _has_value(interaction.get("Confidence_Score")):
            row["Confidence value(s)"] = f"biogrid-confidence-score:{interaction.get('Confidence_Score')}"
        rows.append(row)
    return rows


def populate_corum(data: list, final_columns: list, selected_columns: list, uniprot_id, tax_id):
    rows = []
    info = data[0]["info"]
    for interaction in data[1]["Interactors"]:
        row = _base_row(final_columns, tax_id)
        row["#ID(s) interactor A"] = f"uniprotkb:{interaction.get('Interactor_A', '-')}"
        row["ID(s) interactor B"] = f"uniprotkb:{interaction.get('Interactor_B', '-')}"
        row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_Gene_Name"))
        row["Interaction type(s)"] = "corum-complex-co-membership"
        row["Source database(s)"] = "corum"

        if "Purification_Method" in selected_columns:
            row["Interaction detection method(s)"] = _format_methods(info.get("Purification_Method"), "corum-purification-method")

        evidence_values = []
        if "complex_name" in selected_columns and _has_value(info.get("complex_name")):
            evidence_values.append(f"corum-complex-name:{info.get('complex_name')}")
        if "cell_line" in selected_columns and _has_value(info.get("cell_line")):
            evidence_values.append(f"corum-cell-line:{info.get('cell_line')}")
        row["Confidence value(s)"] = _join(evidence_values)
        rows.append(row)
    return rows


DBs = {
    "String": populate_string,
    "Predictomes": populate_predictomes,
    "BioGrid": populate_biogrid,
    "IntAct": populate_intact,
    "HuRI": populate_huri,
    "Corum": populate_corum,
}
