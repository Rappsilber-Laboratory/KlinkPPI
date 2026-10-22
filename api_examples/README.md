# KlinkPPI Python API examples

Start KlinkPPI first from the repository root:

```bash
npm run dev
```

The examples use `http://127.0.0.1:8000` by default. Override it when needed:

```bash
KLINKPPI_API_URL=http://server.example:8000 python api_examples/single_search.py
```

Run an example from the repository root:

```bash
python api_examples/species_lookup.py
python api_examples/single_search.py
python api_examples/complete_species_search.py
python api_examples/collection_search.py
```

The scripts print concise result summaries and write files under `api_example_outputs/`.
They do not generate plots.

| Example | Use case | Output |
| --- | --- | --- |
| `species_lookup.py` | Find supported species and taxonomy IDs | Printed species matches, JSON |
| `single_search.py` | Query selected databases for one protein | Raw JSON, flattened interaction CSV |
| `complete_species_search.py` | Run and monitor a complete-species job | Job JSON, server-generated Parquet |
| `collection_search.py` | Build an induced or expanded collection network | Job JSON, node CSV, edge CSV |

Collection identifiers with multiple UniProt matches require explicit choices. See
the commented `choices` argument in `collection_search.py`.
