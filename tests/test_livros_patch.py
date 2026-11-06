"""
Teste sem rede para a rota PATCH /api/livros/<id>.

Garante que o pedido ao Supabase leva `timeout` (como as restantes rotas),
que uma resposta de erro do Supabase não é devolvida como `{"status": "ok"}`
e que uma falha de rede continua a dar 500 com `error`.

O teste monkeypatcha `requests.patch` para capturar a chamada sem fazer
pedidos de rede (sem BD remota, sem segredos).
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
    def __init__(self, status_code):
        self.status_code = status_code

    def json(self):
        return {}


class TestLivrosPatch(unittest.TestCase):

    def _run(self, status_code, captured, exc=None):
        def fake_patch(url, headers=None, json=None, timeout=None, **kw):
            captured['url'] = url
            captured['json'] = json
            captured['timeout'] = timeout
            if exc is not None:
                raise exc
            return FakeResp(status_code)

        with mock.patch.object(api.requests, 'patch', side_effect=fake_patch):
            client = api.app.test_client()
            return client.patch('/api/livros/7', json={"status": "processado"})

    def test_sucesso_devolve_ok_e_usa_timeout(self):
        captured = {}
        r = self._run(204, captured)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok"})
        self.assertTrue(captured['url'].endswith('/rest/v1/livros?id=eq.7'))
        self.assertEqual(captured['json'], {"status": "processado"})
        self.assertIsNotNone(captured['timeout'],
                             "O pedido ao Supabase deve ter timeout")
        self.assertGreater(captured['timeout'], 0)

    def test_erro_do_supabase_nao_e_ok(self):
        captured = {}
        r = self._run(400, captured)
        self.assertGreaterEqual(r.status_code, 500)
        self.assertIn('error', r.get_json())
        self.assertNotEqual(r.get_json().get('status'), 'ok')

    def test_falha_de_rede_devolve_500(self):
        captured = {}
        r = self._run(None, captured,
                      exc=api.requests.exceptions.ConnectionError("sem rede"))
        self.assertEqual(r.status_code, 500)
        self.assertIn('error', r.get_json())


if __name__ == '__main__':
    unittest.main()
