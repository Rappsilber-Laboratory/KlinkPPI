import unittest
from threading import Event
from unittest.mock import Mock, patch
import requests
from app.services import collection_search as cs


def candidate(accession, gene=None):
    return {"id": accession, "gene": gene or accession, "gene_names": [gene or accession], "tax_id": "9606", "species": "Homo sapiens", "reviewed": True}


def entry(accession, gene="TP53", tax=9606, reviewed=True):
    return {"primaryAccession": accession, "entryType": "UniProtKB reviewed (Swiss-Prot)" if reviewed else "UniProtKB unreviewed (TrEMBL)",
            "genes": [{"geneName": {"value": gene}}], "organism": {"taxonId": tax, "scientificName": "Homo sapiens"},
            "uniProtKBCrossReferences": [{"database": "Ensembl", "id": "ENST00000269305.9", "properties": [{"key": "GeneId", "value": "ENSG00000141510.20"}]}, {"database": "GeneID", "id": "7157"}]}


def response(entries, next_url=None):
    result = Mock()
    result.json.return_value = {"results": entries}
    result.links = {"next": {"url": next_url}} if next_url else {}
    return result


class ResolutionTests(unittest.TestCase):
    @patch.object(cs.requests, 'get')
    def test_paginated_mixed_ids_species_and_review_status(self, get):
        get.side_effect = [response([entry("P04637"), entry("X00000", tax=10090)], "https://rest.uniprot.org/next"), response([entry("E9PFT5", reviewed=False)])]
        matches, errors = cs.resolve_tokens(["TP53", "P04637", "ENSG00000141510.20", "7157", "bad input"], "9606")
        self.assertEqual([c['id'] for c in matches['TP53']], ['P04637', 'E9PFT5'])
        self.assertFalse(matches['TP53'][1]['reviewed'])
        self.assertEqual(matches['P04637'][0]['id'], 'P04637')
        self.assertEqual(len(matches['7157']), 2)
        self.assertEqual(len(matches['ENSG00000141510.20']), 2)
        self.assertIn('bad input', errors)
        self.assertEqual(get.call_count, 2)

    @patch.object(cs.requests, 'get')
    def test_failed_later_page_does_not_look_unambiguous(self, get):
        get.side_effect = [response([entry('P04637')], 'https://rest.uniprot.org/next'), requests.Timeout('timeout')]
        matches, errors = cs.resolve_tokens(['TP53'], '9606')
        self.assertEqual(matches['TP53'], [])
        self.assertIn('TP53', errors)

    @patch.object(cs.requests, 'get')
    def test_isoform_collapses_to_primary_accession(self, get):
        get.return_value = response([entry('P04637')])
        matches, _ = cs.resolve_tokens(['P04637-2'], '9606')
        self.assertEqual(matches['P04637-2'][0]['id'], 'P04637')

    @patch.object(cs.requests, 'get')
    def test_unknown_gene_or_entry_name_does_not_poison_accession_query(self, get):
        get.return_value = response([entry('P04637')])
        matches, errors = cs.resolve_tokens(['P04637', 'MISSING_COLLECTION_GENE', 'P53_HUMAN'], '9606')
        query = get.call_args.kwargs['params']['query']
        self.assertIn('accession:P04637', query)
        self.assertIn('gene_exact:"MISSING_COLLECTION_GENE"', query)
        self.assertIn('id:P53_HUMAN', query)
        self.assertNotIn('accession:P53_HUMAN', query)
        self.assertEqual(matches['P04637'][0]['id'], 'P04637')
        self.assertFalse(errors)

    def test_ambiguity_requires_explicit_choice_and_rejects_forgery(self):
        job_id = 'test-ambiguity'
        cs.JOBS[job_id] = {'status': 'awaiting_selection', 'resolution': [{'input': 'TP53', 'candidates': [candidate('P04637'), candidate('E9PFT5')]}]}
        try:
            with self.assertRaisesRegex(ValueError, 'Choose a candidate'):
                cs.run_job(job_id, {})
            with self.assertRaisesRegex(ValueError, 'Invalid candidate'):
                cs.run_job(job_id, {'TP53': 'FAKE'})
        finally:
            del cs.JOBS[job_id]

    @patch.object(cs.POOL, 'submit')
    def test_skipped_ambiguous_id_is_explicit(self, submit):
        job_id = 'test-skip'
        cs.JOBS[job_id] = {'status': 'awaiting_selection', 'resolution': [{'input': 'TP53', 'candidates': [candidate('P04637'), candidate('E9PFT5')]}]}
        try:
            result = cs.run_job(job_id, {'TP53': None})
            self.assertIsNone(result['selections']['TP53'])
            self.assertEqual(result['status'], 'running')
            submit.assert_called_once()
        finally:
            del cs.JOBS[job_id]


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c, self.d = [candidate(x) for x in ['P04637', 'P38398', 'Q00001', 'Q00002']]
        self.canonical = {c['id']: c for c in [self.a, self.b, self.c, self.d]}
        self.seeds = {c['id']: c for c in [self.a, self.b]}
        self.records = [
            ('IntAct', self.a['id'], {'Interactor_A': self.b['id'], 'Interactor_B': self.a['id'], 'PubMed_Ids': ['123'], 'Interaction_Score_Intact': '0.8'}, {}),
            ('BioGrid', self.b['id'], {'Interactor_A': self.a['id'], 'Interactor_B': self.b['id']}, {}),
            ('IntAct', self.a['id'], {'Interactor_A': self.c['id'], 'Interactor_B': self.a['id']}, {}),
            ('String', self.a['id'], {'Interactor_A': self.d['id'], 'Interactor_B': self.c['id']}, {}),
            ('BioGrid', self.a['id'], {'Interactor_A': 'unknown', 'Interactor_B': self.a['id']}, {}),
            ('IntAct', self.a['id'], {'Interactor_A': self.d['id'], 'Interactor_B': self.a['id'], 'organism_tax_id': '10090'}, {}),
        ]

    def test_induced_pairs_are_deduplicated_and_unknown_input_is_isolated(self):
        graph = cs.build_graph(self.seeds, self.records, self.canonical, 'induced', '9606', 'Homo sapiens', ['missing'])
        self.assertEqual(len(graph['edges']), 1)
        self.assertEqual({ev['database'] for ev in graph['edges'][0]['evidence']}, {'IntAct', 'BioGrid'})
        self.assertEqual(len(graph['nodes']), 3)
        self.assertTrue(next(n for n in graph['nodes'] if n['gene'] == 'missing')['unresolved'])
        self.assertFalse(graph['edges'][0]['expanded'])

    def test_expanded_is_one_hop_and_drops_ambiguous_endpoints_and_other_species(self):
        graph = cs.build_graph(self.seeds, self.records, self.canonical, 'expanded', '9606', 'Homo sapiens', ['missing'])
        self.assertEqual(len(graph['edges']), 2)
        self.assertNotIn(self.d['id'], {n['id'] for n in graph['nodes']})
        self.assertEqual(sum(e['expanded'] for e in graph['edges']), 1)
        self.assertEqual(graph['unmapped_evidence_rows'], 1)

    def test_query_direction_does_not_duplicate_the_same_evidence(self):
        row = self.records[0][2]
        records = [('IntAct', self.a['id'], {**row, 'Interactor_Link': 'https://example.org/a'}, {}),
                   ('IntAct', self.b['id'], {**row, 'Interactor_A': self.a['id'], 'Interactor_B': self.b['id'], 'Interactor_Link': 'https://example.org/b'}, {})]
        graph = cs.build_graph(self.seeds, records, self.canonical, 'induced', '9606', 'Homo sapiens', [])
        self.assertEqual(len(graph['edges'][0]['evidence']), 1)

    def test_missing_scores_and_publications_are_not_invented(self):
        ev = cs.evidence('BioGrid', {'Confidence_Score': 'nan', 'PubMed_Ids': '-', 'Interaction_Type': 'genetic interaction'}, {})
        self.assertIsNone(ev['score'])
        self.assertEqual(ev['publications'], [])
        self.assertEqual(ev['type'], 'functional')
        self.assertEqual(cs.evidence('String', {}, {})['type'], 'functional')
        self.assertEqual(cs.evidence('HuMap', {}, {})['type'], 'predicted')

    def test_string_second_hop_rows_are_not_collected(self):
        rows, _, _ = cs.extract_rows('String', [{'info': {}}, {'Direct_Interactions': [{'Interactor_A': 'a'}]}, {'Indirect_Interactions': [{'Interactor_A': 'b'}]}])
        self.assertEqual(rows, [{'Interactor_A': 'a'}])

    def test_edge_cap_is_reported(self):
        with patch.object(cs, 'MAX_EDGES', 1):
            graph = cs.build_graph(self.seeds, self.records, self.canonical, 'expanded', '9606', 'Homo sapiens', [])
        self.assertEqual(len(graph['edges']), 1)
        self.assertTrue(graph['truncated'])

    def test_completed_job_is_not_changed_by_cancel(self):
        cs.JOBS['test-completed'] = {'status': 'completed', 'cancel': Event(), 'progress': 'Analysis complete'}
        try:
            self.assertEqual(cs.cancel_job('test-completed')['status'], 'completed')
        finally:
            del cs.JOBS['test-completed']


if __name__ == '__main__':
    unittest.main()
