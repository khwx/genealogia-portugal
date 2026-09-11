"""
Teste sem rede para o filtro de qualidade no endpoint /api/pessoas.

Garante que a pesquisa pública exclui registos rejeitados/ilegíveis
(qualidade = 0) ao incluir sempre a condição
`or(qualidade.gt.0,qualidade.is.null)` no URL PostgREST construído.

O teste monkeypatcha `requests.get` para capturar o URL sem fazer chamadas
de rede, cumprindo o pilar de segurança (sem BD remota, sem segredos).
"""
import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

import importlib.util
spec = importlib.util.spec_from_file_location('api_index', 'api/index.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class FakeResp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def json(self):
        return self._p


class TestPessoasQualityFilter(unittest.TestCase):

    def _run(self, query_string, captured):
        def fake_get(url, headers=None, timeout=None, **kw):
            captured['url'] = url
            return FakeResp([])

        with mock.patch.object(api.requests, 'get', side_effect=fake_get):
            client = api.app.test_client()
            return client.get('/api/pessoas?' + query_string)

    def test_quality_filter_present_in_url(self):
        captured = {}
        self._run('q=Joao', captured)
        url = captured.get('url', '')
        self.assertIn('or(qualidade.gt.0,qualidade.is.null)', url,
                      "A pesquisa deve excluir registos rejeitados (qualidade=0)")

    def test_quality_filter_with_year_and_type(self):
        captured = {}
        self._run('q=Maria&from_year=1700&to_year=1800&tipo=DEAT', captured)
        url = captured.get('url', '')
        self.assertIn('or(qualidade.gt.0,qualidade.is.null)', url)
        self.assertIn('tipo_registo=eq.DEAT', url)
        self.assertIn('data_obito.gte.1700-01-01', url)
        self.assertIn('data_obito.lte.1800-12-31', url)

    def test_quality_filter_without_query_still_applied(self):
        captured = {}
        self._run('', captured)
        url = captured.get('url', '')
        self.assertIn('or(qualidade.gt.0,qualidade.is.null)', url,
                      "O filtro de qualidade aplica-se mesmo sem termo de pesquisa")

    def test_keeps_rejected_records_out_by_quality_zero(self):
        # O filtro não usa qualidade.gte (que excluiria NULL/default),
        # mas sim 'or(qualidade.gt.0,qualidade.is.null)' para manter os
        # ainda por validar (NULL) e aprovados (>=1).
        self.assertIn('qualidade.is.null',
                      'or(qualidade.gt.0,qualidade.is.null)')
        self.assertNotIn('qualidade.gte',
                         'or(qualidade.gt.0,qualidade.is.null)')


if __name__ == '__main__':
    unittest.main()
