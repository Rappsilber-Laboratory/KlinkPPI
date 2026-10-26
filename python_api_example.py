"""Choose one HTTP API workflow; importing this module performs no work.

Run `python python_api_example.py --help`. Large complete-species searches are
explicitly selected rather than running alongside every small example.
"""
import argparse
from importlib import import_module

WORKFLOWS = {
    "species": "species_lookup", "gene": "gene_lookup", "single": "single_search",
    "complete-species": "complete_species_search", "collection": "collection_search",
    "followups": "collection_followups",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", choices=WORKFLOWS, nargs="?", default="single")
    args, remaining = parser.parse_known_args(argv)
    module = import_module(f"api_examples.{WORKFLOWS[args.workflow]}")
    if args.workflow in {"gene", "complete-species", "collection", "followups"}:
        module.main(remaining)
    else:
        if remaining:
            parser.error("This workflow has no additional arguments")
        module.main()


if __name__ == "__main__":
    main()
