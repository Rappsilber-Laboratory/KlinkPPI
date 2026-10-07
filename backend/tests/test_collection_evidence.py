import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from app.services import biogrid_index as bg
from app.services import resolve_corum as corum


class EvidenceRetentionTests(unittest.TestCase):
    def test_biogrid_index_retains_publications_on_both_query_sides(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.tsv'
            index = Path(tmp) / 'index.sqlite3'
            row = {'Alt IDs Interactor A': 'uniprot/swiss-prot:P04637|biogrid:1',
                   'Alt IDs Interactor B': 'uniprot/swiss-prot:P38398|biogrid:2',
                   'Taxid Interactor A': 'taxid:9606', 'Taxid Interactor B': 'taxid:9606',
                   'Interaction Detection Method': 'psi-mi:MI:0018(two hybrid)',
                   'Interaction Types': 'psi-mi:MI:0915(physical association)',
                   'Confidence Values': '-', 'Aliases Interactor A': 'uniprot:TP53(gene name)',
                   'Aliases Interactor B': 'uniprot:BRCA1(gene name)',
                   'Publication Identifiers': 'pubmed:12345|pubmed:67890'}
            with source.open('w') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row), delimiter='\t')
                writer.writeheader()
                writer.writerow(row)
            with patch.object(bg, 'BIOGRID_SOURCE_PATH', source), patch.object(bg, 'BIOGRID_INDEX_PATH', index):
                bg.build_biogrid_index()
                self.assertTrue(bg._index_is_current())
                for query, partner in [('P04637', 'P38398'), ('P38398', 'P04637')]:
                    rows = bg.get_biogrid_interactions(query)
                    self.assertEqual(rows[0]['PubMed_Ids'], ['12345', '67890'])
                    self.assertEqual(rows[0]['Interactor_A'], partner)
                    self.assertEqual(rows[0]['Interaction_Detection_Method'], 'two hybrid')

    def test_corum_collection_returns_all_complexes_and_their_evidence(self):
        mapping = pd.DataFrame({'UniProtKB_accession_number': ['P04637', 'P04637'], 'corum_id': [1, 2]})
        complexes = pd.DataFrame([
            {'complex_id': 1, 'pmid': 123, 'purification_methods': [{'name': 'co-IP'}], 'subunits': [{'swissprot': {'uniprot_id': 'P04637'}}, {'swissprot': {'uniprot_id': 'P38398'}}]},
            {'complex_id': 2, 'pmid': 456, 'purification_methods': [{'name': 'pull down'}], 'subunits': [{'swissprot': {'uniprot_id': 'P04637'}}, {'swissprot': {'uniprot_id': 'Q00987'}}]},
        ])
        with patch.object(corum, 'CORUM_MAPPING_DF', mapping), patch.object(corum, 'CORUM_COMPLEXES_DF', complexes):
            rows = corum.resolve_corum_collection('P04637', '9606')[1]['Interactors']
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['Interactor_A'] for r in rows}, {'P38398', 'Q00987'})
        self.assertEqual(rows[0]['PubMed_Ids'], ['123'])
        self.assertEqual(rows[1]['Interaction_Detection_Method'], ['pull down'])
