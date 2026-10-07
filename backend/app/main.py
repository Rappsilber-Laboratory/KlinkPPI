import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Literal, Optional
from fastapi import FastAPI,HTTPException, Query
from fastapi.responses import StreamingResponse
from app.services.convert_input_to_uniprotKB import get_job_id
from app.services.resolve_string import get_string_interactions
from app.services.resolve_intact import resolve_intact
from app.services.resolve_predictomes import resolve_predictomes
from app.services.resolve_biogrid import resolve_biogrid
from app.services.resolve_corum import resolve_corum, resolve_corum_collection
from app.services.resolve_huri import resolve_HuRI
from app.services.resolve_complex_portal import resolve_complex_portal
from app.services.resolve_hippie import resolve_hippie
from app.services.resolve_humap import resolve_humap
from app.services.resolve_psicquic import resolve_mint, resolve_reactome
from app.services.resolve_signor import resolve_signor
from app.services.convert_input_to_ensembl import convert_to_ensemble
from app.services.species_index import get_species_by_tax_id, get_supported_databases, get_supported_organism_summary, resolve_species_name, search_species
from app.services.species_ppi_export import build_species_mitab, build_species_parquet
from app.services.species_ppi_jobs import cancel_species_ppi_job, create_species_ppi_job, get_species_display_name, get_species_ppi_job, get_species_ppi_job_rows
from app.services.uniprot_gene_search import search_gene_name_candidates
from app.services.uniprot_lookup import get_uniprot_taxonomy_id
import pandas as pd

from app.services.select_columns_mitab import build_final_columns
from app.services.populate_mitab import DBs,populate_huri
from app.services.toParquet import flatten_results

from pydantic import BaseModel,EmailStr,Field
from app.services import collection_search


from fastapi.middleware.cors import CORSMiddleware


class AuthCredentials(BaseModel):
    email:EmailStr
    password:str


class SpeciesPPIJobRequest(BaseModel):
    tax_id: Optional[str] = None
    species_name: Optional[str] = None
    selected_databases: list[str]


class SpeciesPPIDownloadRequest(BaseModel):
    selected_databases: list[str]
    selected_columns: list[str]

app=FastAPI() 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174","http://127.0.0.1:5174"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_RESOLVERS = {
    "String": get_string_interactions,
    "IntAct": resolve_intact,
    "Corum": resolve_corum,
    "Predictomes": resolve_predictomes,
    "BioGrid": resolve_biogrid,
    "ComplexPortal": resolve_complex_portal,
    "Reactome": resolve_reactome,
    "Signor": resolve_signor,
    "Hippie": resolve_hippie,
    "HuMap": resolve_humap,
    "Mint": resolve_mint,
}


def resolve_database(database_name: str, uniprotkb_id: str, tax_id: str):
    if database_name == "HuRI":
        ensembl_id = convert_to_ensemble(uniprotkb_id)
        return resolve_HuRI(ensembl_id, tax_id, uniprotkb_id)

    resolver = DATABASE_RESOLVERS.get(database_name)
    if resolver is None:
        raise KeyError(f"Unknown database: {database_name}")
    return resolver(uniprotkb_id, tax_id)


def resolve_database_safely(database_name: str, uniprotkb_id: str, tax_id: str):
    try:
        return resolve_database(database_name, uniprotkb_id, tax_id)
    except Exception as exc:
        return [
            {
                "info": {
                    "database": database_name,
                    "Input_UniProt": uniprotkb_id,
                    "organism_tax_id": tax_id,
                    "Error": f"{database_name} lookup failed: {exc}",
                }
            },
            {"Interactors": []},
        ]


def resolve_species_context(tax_id: Optional[str], species_name: Optional[str]):
    resolved_species=None
    resolved_tax_id=(tax_id or "").strip() or None
    requested_species_name=(species_name or "").strip()

    if resolved_tax_id:
        resolved_species=get_species_by_tax_id(resolved_tax_id)
        if resolved_species is None:
            raise HTTPException(status_code=404,detail="Taxonomy ID is not supported by the configured organism list")
    elif requested_species_name:
        resolved_species=resolve_species_name(requested_species_name)
        if resolved_species is None:
            species_matches=search_species(requested_species_name,limit=5)
            if species_matches:
                raise HTTPException(status_code=400,detail="Species name is ambiguous. Please choose one of the suggestions or enter a taxonomy ID")
            raise HTTPException(status_code=404,detail="Species name not found in the supported organism list")
        resolved_tax_id=resolved_species["tax_id"]

    return resolved_tax_id, requested_species_name, resolved_species


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/species/search")
def species_search(q:str="",limit:int=8):
    safe_limit=max(1,min(limit,10))
    return {"results":search_species(q,safe_limit)}


@app.get("/supported-organisms/summary")
def supported_organisms_summary():
    return get_supported_organism_summary()


@app.get("/gene-name/search")
def gene_name_search(
    query:str,
    tax_id:Optional[str]=None,
    species_name:Optional[str]=None,
    limit:int=8,
):
    resolved_tax_id, requested_species_name, resolved_species = resolve_species_context(tax_id, species_name)
    if resolved_tax_id is None:
        raise HTTPException(
            status_code=400,
            detail="Gene name lookup requires a species name or taxonomy ID",
        )

    safe_limit=max(1,min(limit,10))
    candidates=search_gene_name_candidates(query.strip(), resolved_tax_id, safe_limit)
    return {
        "query": query,
        "tax_id": resolved_tax_id,
        "species_name": resolved_species["display_name"] if resolved_species else requested_species_name,
        "candidates": candidates,
    }


@app.post("/species-ppi/jobs")
def start_species_ppi_job(request: SpeciesPPIJobRequest):
    resolved_tax_id, requested_species_name, resolved_species = resolve_species_context(
        request.tax_id, request.species_name
    )
    if resolved_tax_id is None:
        raise HTTPException(
            status_code=400,
            detail="Complete species PPI search requires a species name or taxonomy ID",
        )

    if not request.selected_databases:
        raise HTTPException(status_code=400, detail="Select at least one database")

    species_label = (
        resolved_species["display_name"]
        if resolved_species
        else get_species_display_name(resolved_tax_id, requested_species_name)
    )
    return create_species_ppi_job(resolved_tax_id, species_label, request.selected_databases)


@app.get("/species-ppi/jobs/{job_id}")
def get_species_ppi_job_status(job_id: str):
    try:
        return get_species_ppi_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Species PPI job not found")


@app.post("/species-ppi/jobs/{job_id}/cancel")
def cancel_complete_species_job(job_id: str):
    try:
        return cancel_species_ppi_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Species PPI job not found")


@app.post("/species-ppi/jobs/{job_id}/mitab")
def download_species_mitab(job_id: str, request: SpeciesPPIDownloadRequest):
    try:
        summary, rows_by_db = get_species_ppi_job_rows(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Species PPI job not found")

    if summary["status"] != "completed":
        raise HTTPException(status_code=400, detail="Species PPI job is not finished yet")

    available_databases = [
        db_name
        for db_name, status in summary["database_statuses"].items()
        if status["status"] == "completed"
    ]
    selected_databases = [db_name for db_name in request.selected_databases if db_name in available_databases]
    if not selected_databases:
        raise HTTPException(status_code=400, detail="No completed databases were selected for export")

    buffer = build_species_mitab(rows_by_db, summary["tax_id"], selected_databases, request.selected_columns)
    filename = f"{summary['species_name'].replace(' ', '_')}_{summary['tax_id']}_ppi.mitab.txt"
    return StreamingResponse(
        buffer,
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/species-ppi/jobs/{job_id}/parquet")
def download_species_parquet(job_id: str, request: SpeciesPPIDownloadRequest):
    try:
        summary, rows_by_db = get_species_ppi_job_rows(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Species PPI job not found")

    if summary["status"] != "completed":
        raise HTTPException(status_code=400, detail="Species PPI job is not finished yet")

    available_databases = [
        db_name
        for db_name, status in summary["database_statuses"].items()
        if status["status"] == "completed"
    ]
    selected_databases = [db_name for db_name in request.selected_databases if db_name in available_databases]
    if not selected_databases:
        raise HTTPException(status_code=400, detail="No completed databases were selected for export")

    try:
        buffer = build_species_parquet(rows_by_db, selected_databases)
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"Parquet export is unavailable: {exc}")
    filename = f"{summary['species_name'].replace(' ', '_')}_{summary['tax_id']}_ppi.parquet"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.apache.parquet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/search")
def search(
    id_value:str,
    from_database:str,
    tax_id:Optional[str]=None,
    species_name:Optional[str]=None,
    selected_databases:Optional[List[str]]=Query(default=None)
):
    resolved_tax_id, requested_species_name, resolved_species = resolve_species_context(tax_id, species_name)

    uniprotkb_id=get_job_id(id_value,from_database,resolved_tax_id)
    if(not uniprotkb_id):
        context_details = []
        if requested_species_name:
            context_details.append(f"species '{requested_species_name}'")
        if resolved_tax_id:
            context_details.append(f"taxonomy ID '{resolved_tax_id}'")

        if from_database == "Gene_Name":
            if context_details:
                raise HTTPException(
                    status_code=404,
                    detail=f"Gene name '{id_value}' could not be resolved to a UniProtKB entry for {' and '.join(context_details)}",
                )
            raise HTTPException(
                status_code=404,
                detail=f"Gene name '{id_value}' could not be resolved to a UniProtKB entry. Try adding a species name or taxonomy ID",
            )

        if context_details:
            raise HTTPException(
                status_code=404,
                detail=f"Input '{id_value}' could not be resolved from {from_database} for {' and '.join(context_details)}",
            )

        raise HTTPException(
            status_code=404,
            detail=f"Input '{id_value}' could not be resolved from {from_database}",
        )

    if resolved_tax_id is None:
        resolved_tax_id=get_uniprot_taxonomy_id(uniprotkb_id)
        if resolved_tax_id is None:
            raise HTTPException(status_code=400,detail="Could not infer a taxonomy ID from the input. Please provide a species name or taxonomy ID")
        resolved_species=get_species_by_tax_id(resolved_tax_id)

    available_databases=get_supported_databases(resolved_tax_id)

    selected_databases_dict={}
    result=[]
    result.append({
        "Input":{
            "UniProtId":uniprotkb_id,
            "TaxonomyId":resolved_tax_id,
            "SpeciesName":resolved_species["display_name"] if resolved_species else requested_species_name
        }
    })
    output=[]
    requested_databases = sorted(available_databases) if selected_databases is None else selected_databases
    supported_requests = []
    for db in requested_databases:
        if db not in available_databases:
            output.append({db: f"{db} does not support taxonomy ID {resolved_tax_id}"})
        elif db not in DATABASE_RESOLVERS and db != "HuRI":
            output.append({db: f"{db} is not configured"})
        else:
            supported_requests.append(db)

    if supported_requests:
        worker_count = min(6, len(supported_requests))
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="klinkppi-search") as executor:
            futures = {
                executor.submit(resolve_database_safely, db, uniprotkb_id, resolved_tax_id): db
                for db in supported_requests
            }
            for future in as_completed(futures):
                db = futures[future]
                selected_databases_dict[db] = future.result()
    
    for key in supported_requests:
        if(key in available_databases):
            output.append({key:selected_databases_dict[key]})

    result.append({"output":output})

    return result

class DownloadRequest(BaseModel):
    results: list
    selected_databases: list[str]
    selected_columns: list[str]
    uniprot_id: str
    tax_id: str
    
@app.post("/mitab")
def download_mitab(request: DownloadRequest):
    final_columns = build_final_columns(request.selected_databases, request.selected_columns)
    all_rows = []
    
    output = request.results[1]["output"]

    for db_result in output:
        db_name = list(db_result.keys())[0]
        if db_name not in request.selected_databases:
            continue
        db_data = db_result[db_name]
        if isinstance(db_data, str):
            continue

        if db_name == "HuRI":
            rows = populate_huri(db_data, final_columns, request.uniprot_id,request.selected_columns, request.tax_id)
        elif db_name in DBs:
            rows = DBs[db_name](db_data,final_columns,request.selected_columns,request.uniprot_id, request.tax_id)
        else:
            continue

        all_rows.extend(rows)

    tsv_lines = ["\t".join(final_columns)]
    for row in all_rows:
        line = "\t".join(str(row.get(col, "-")) for col in final_columns)
        tsv_lines.append(line)
    tsv_content = "\n".join(tsv_lines)
    # return output
    # return final_columns
    return StreamingResponse(
        io.StringIO(tsv_content),
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": f"attachment; filename={request.uniprot_id}_interactions.mitab.txt"}
    )

@app.post("/parquet")
def download_parquet(request: DownloadRequest):
    rows = flatten_results(
        request.results,
        request.selected_databases
    )
    if not rows:
        raise HTTPException(status_code=404,detail="No Data")
    
    df=pd.DataFrame(rows)
    buffer=io.BytesIO()
    try:
        df.to_parquet(buffer, index=False)
    except ImportError as exc:
        raise HTTPException(status_code=500,detail=f"Parquet export is unavailable: {exc}")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.apache.parquet",
        headers={
            "Content-Disposition":
            f"attachment; filename={request.uniprot_id}.parquet"
        }
    )


# Collection searches retain candidate lists on the server so clients cannot
# introduce unvalidated accessions or silently choose ambiguous mappings.
def resolve_collection_database(database_name: str, uniprotkb_id: str, tax_id: str):
    if database_name == "Corum":
        return resolve_corum_collection(uniprotkb_id, tax_id)
    return resolve_database_safely(database_name, uniprotkb_id, tax_id)


class CollectionRequest(BaseModel):
    identifiers: list[str] = Field(min_length=1, max_length=collection_search.MAX_INPUTS)
    species_name: str = Field(min_length=1, max_length=200)
    tax_id: Optional[str] = None
    selected_databases: list[str] = Field(min_length=1, max_length=12)
    input_type: Literal["auto", "UniProtKB", "Gene_Name", "Ensembl", "GeneID"] = "auto"
    mode: Literal["induced", "expanded"] = "induced"


class CollectionChoices(BaseModel):
    choices: dict[str, Optional[str]] = Field(default_factory=dict)


@app.post("/collection/jobs", status_code=202)
def start_collection(request: CollectionRequest):
    tax_id, _, species = resolve_species_context(request.tax_id, request.species_name)
    if not tax_id or not species:
        raise HTTPException(status_code=400, detail="Select a supported species before collection search")
    identifiers = list(dict.fromkeys(token.strip() for token in request.identifiers if token.strip()))
    if not identifiers or any(len(token) > 100 for token in identifiers):
        raise HTTPException(status_code=400, detail="Provide 1–200 identifiers, each at most 100 characters")
    supported = get_supported_databases(tax_id)
    databases = list(dict.fromkeys(request.selected_databases))
    invalid = [db for db in databases if db not in supported or (db not in DATABASE_RESOLVERS and db != "HuRI")]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Databases unavailable for this species: {', '.join(invalid)}")
    try:
        return collection_search.create_job(identifiers, tax_id, species["display_name"], databases,
                                            request.input_type, request.mode, resolve_collection_database)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))


@app.get("/collection/jobs/{job_id}")
def collection_status(job_id: str):
    try:
        return collection_search.snapshot(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Collection job not found or expired")


@app.post("/collection/jobs/{job_id}/run", status_code=202)
def run_collection(job_id: str, request: CollectionChoices):
    try:
        return collection_search.run_job(job_id, request.choices)
    except KeyError:
        raise HTTPException(status_code=404, detail="Collection job not found or expired")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/collection/jobs/{job_id}/cancel")
def cancel_collection(job_id: str):
    try:
        return collection_search.cancel_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Collection job not found or expired")
