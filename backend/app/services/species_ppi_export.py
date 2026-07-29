from __future__ import annotations

import io
from typing import Iterator

import pandas as pd

from app.services.populate_mitab import (
    COMMON_COLUMNS,
    INTACT_SCORE_FIELDS,
    PREDICTOMES_SCORE_FIELDS,
    STRING_SCORE_FIELDS,
    _format_biogrid_type,
    _format_method,
    _format_methods,
    _gene_alias,
    _join,
    _pubmed_values,
    _score_values,
)
from app.services.species_ppi_remote import iter_intact_species_rows, iter_string_species_rows


def _build_final_columns(selected_databases: list[str], selected_columns: list[str]) -> list[str]:
    return list(COMMON_COLUMNS)


def _format_taxid(tax_id: str | None) -> str:
    return f"taxid:{tax_id}" if tax_id else "-"


def _base_row(final_columns: list[str], tax_id: str, tax_id_a: str | None = None, tax_id_b: str | None = None) -> dict:
    row = {column: "-" for column in final_columns}
    row["Taxid interactor A"] = _format_taxid(tax_id_a or tax_id)
    row["Taxid interactor B"] = _format_taxid(tax_id_b or tax_id)
    return row


def _iter_species_rows(db_name: str, db_data) -> Iterator[dict]:
    if isinstance(db_data, dict):
        if db_data.get("kind") == "string_species_bundle":
            yield from iter_string_species_rows(db_data)
            return
        if db_data.get("kind") == "intact_species_bundle":
            yield from iter_intact_species_rows(db_data)
            return

    for row in db_data or []:
        yield row


def _format_interactor(interaction: dict, side: str, fallback_prefix: str) -> str:
    value = interaction.get(f"Interactor_{side}") or "-"
    prefix = interaction.get(f"Interactor_{side}_Prefix", fallback_prefix)
    return f"{prefix}:{value}"


def _corum_evidence(interaction: dict, selected_columns: list[str]) -> str:
    values = []
    if "complex_name" in selected_columns and interaction.get("complex_name"):
        values.append(f"corum-complex-name:{interaction.get('complex_name')}")
    if "cell_line" in selected_columns and interaction.get("cell_line"):
        values.append(f"corum-cell-line:{interaction.get('cell_line')}")
    return _join(values)


def _rows_to_mitab(rows_by_db: dict[str, list[dict] | dict], tax_id: str, selected_databases: list[str], selected_columns: list[str]) -> str:
    final_columns = _build_final_columns(selected_databases, selected_columns)
    output_rows = []

    for db_name in selected_databases:
        for interaction in _iter_species_rows(db_name, rows_by_db.get(db_name, [])):
            row = _base_row(final_columns, tax_id)

            if db_name == "String":
                row["#ID(s) interactor A"] = _format_interactor(interaction, "A", "stringdb")
                row["ID(s) interactor B"] = _format_interactor(interaction, "B", "stringdb")
                row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_Gene_Name_A"))
                row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_Gene_Name_B"))
                row["Interaction type(s)"] = "string-functional-association"
                row["Source database(s)"] = 'psi-mi:"MI:1014"(string)'
                row["Confidence value(s)"] = _score_values(interaction, selected_columns, STRING_SCORE_FIELDS)

            elif db_name == "IntAct":
                row = _base_row(final_columns, tax_id, interaction.get("Taxid_A"), interaction.get("Taxid_B"))
                row["#ID(s) interactor A"] = _format_interactor(interaction, "A", "uniprotkb")
                row["ID(s) interactor B"] = _format_interactor(interaction, "B", "uniprotkb")
                row["Alias(es) interactor A"] = _gene_alias(interaction.get("Interactor_Gene_Name_A"))
                row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_Gene_Name_B"))
                row["Source database(s)"] = interaction.get("Source_Database") or 'psi-mi:"MI:0469"(intact)'
                if "Interaction_Type" in selected_columns and interaction.get("Interaction_Type"):
                    row["Interaction type(s)"] = interaction.get("Interaction_Type")
                if "Unique_Identification_Methods" in selected_columns:
                    row["Interaction detection method(s)"] = _format_methods(interaction.get("Unique_Identification_Methods"))
                if "PubMed_Ids" in selected_columns:
                    row["Publication Identifier(s)"] = _pubmed_values(interaction.get("PubMed_Ids"))
                row["Confidence value(s)"] = _score_values(interaction, selected_columns, INTACT_SCORE_FIELDS)

            elif db_name == "BioGrid":
                row["#ID(s) interactor A"] = f"uniprotkb:{interaction.get('Interactor_A', '-')}"
                row["ID(s) interactor B"] = f"uniprotkb:{interaction.get('Interactor_B', '-')}"
                row["Alias(es) interactor A"] = _gene_alias(
                    interaction.get("Interactor_Gene_Name_A") or interaction.get("Interactor_Gene_Name")
                )
                row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_Gene_Name_B"))
                row["Source database(s)"] = 'psi-mi:"MI:0463"(biogrid)'
                if "Interaction_Detection_Method" in selected_columns:
                    row["Interaction detection method(s)"] = _format_method(interaction.get("Interaction_Detection_Method"))
                if "Interaction_Type" in selected_columns:
                    row["Interaction type(s)"] = _format_biogrid_type(interaction.get("Interaction_Type"))
                if "Confidence_Score" in selected_columns and interaction.get("Confidence_Score"):
                    row["Confidence value(s)"] = f"biogrid-confidence-score:{interaction.get('Confidence_Score')}"

            elif db_name == "Predictomes":
                row["#ID(s) interactor A"] = f"uniprotkb:{interaction.get('Interactor_A', '-')}"
                row["ID(s) interactor B"] = f"uniprotkb:{interaction.get('Interactor_B', '-')}"
                row["Alias(es) interactor A"] = _gene_alias(
                    interaction.get("Interactor_Gene_Name_A") or interaction.get("Interactor_Gene_Name")
                )
                row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_Gene_Name_B"))
                row["Interaction type(s)"] = "predictomes-structural-prediction"
                row["Source database(s)"] = "predictomes"
                row["Confidence value(s)"] = _score_values(interaction, selected_columns, PREDICTOMES_SCORE_FIELDS)

            elif db_name == "Corum":
                row["#ID(s) interactor A"] = f"uniprotkb:{interaction.get('Interactor_A', '-')}"
                row["ID(s) interactor B"] = f"uniprotkb:{interaction.get('Interactor_B', '-')}"
                row["Alias(es) interactor A"] = _gene_alias(
                    interaction.get("Interactor_Gene_Name_A") or interaction.get("Interactor_Gene_Name")
                )
                row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_Gene_Name_B"))
                row["Interaction type(s)"] = "corum-complex-co-membership"
                row["Source database(s)"] = "corum"
                if "Purification_Method" in selected_columns:
                    row["Interaction detection method(s)"] = _format_methods(
                        interaction.get("Purification_Method"), "corum-purification-method"
                    )
                row["Confidence value(s)"] = _corum_evidence(interaction, selected_columns)

            elif db_name == "HuRI":
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
                row["Alias(es) interactor A"] = _gene_alias(
                    interaction.get("Interactor_Gene_Name_A") or interaction.get("Interactor_Gene_Name")
                )
                row["Alias(es) interactor B"] = _gene_alias(interaction.get("Interactor_Gene_Name_B"))
                row["Interaction type(s)"] = 'psi-mi:"MI:0407"(direct interaction)'
                row["Source database(s)"] = "huri"

            output_rows.append(row)

    tsv_lines = ["\t".join(final_columns)]
    for row in output_rows:
        tsv_lines.append("\t".join(str(row.get(col, "-")) for col in final_columns))
    return "\n".join(tsv_lines)


def _rows_to_parquet(rows_by_db: dict[str, list[dict] | dict], selected_databases: list[str]) -> bytes:
    rows = []
    for db_name in selected_databases:
        for interaction in _iter_species_rows(db_name, rows_by_db.get(db_name, [])):
            temp = dict(interaction)
            temp["Database"] = db_name
            rows.append(temp)

    dataframe = pd.DataFrame(rows)
    buffer = io.BytesIO()
    dataframe.to_parquet(buffer, index=False)
    buffer.seek(0)
    return buffer.getvalue()


def build_species_mitab(rows_by_db: dict[str, list[dict] | dict], tax_id: str, selected_databases: list[str], selected_columns: list[str]) -> io.StringIO:
    content = _rows_to_mitab(rows_by_db, tax_id, selected_databases, selected_columns)
    return io.StringIO(content)


def build_species_parquet(rows_by_db: dict[str, list[dict] | dict], selected_databases: list[str]) -> io.BytesIO:
    content = _rows_to_parquet(rows_by_db, selected_databases)
    buffer = io.BytesIO(content)
    buffer.seek(0)
    return buffer
