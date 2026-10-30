"""Choose one HTTP API workflow; importing this module performs no work.

Run `python python_api_example.py --help`. Large complete-species searches are
explicitly selected rather than running alongside every small example.
"""
import argparse
import sys
from importlib import import_module

WORKFLOWS = {
    "species": "species_lookup", "gene": "gene_lookup", "single": "single_search",
    "complete-species": "complete_species_search", "collection": "collection_search",
    "followups": "collection_followups", "embedding": "collection_embeddings",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", choices=WORKFLOWS, nargs="?", default="single")
    parser.add_argument("options", nargs=argparse.REMAINDER,
                        help="Options for the selected workflow; use WORKFLOW --help")
    args = parser.parse_args(argv)
    remaining = args.options
    module = import_module(f"api_examples.{WORKFLOWS[args.workflow]}")
    from klinkppi import KlinkPPIError
    try:
        if args.workflow in {"gene", "complete-species", "collection", "followups", "embedding"}:
            module.main(remaining)
        else:
            if remaining:
                parser.error("This workflow has no additional arguments")
            module.main()
    except KlinkPPIError as error:
        print(f"KlinkPPI: {error}", file=sys.stderr)
        if error.job is not None:
            print("Last known job/task:", error.job.get("job_id", error.job.get("alignment_id")), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
