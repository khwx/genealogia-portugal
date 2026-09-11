"""
Testes unitários para o módulo name_phonetics.py.
Valida:
- Normalização de acentos e tokens
- Expansão de variantes históricas (João, Manuel, Teresa, Tomás, Inácio, etc.)
- Soundex português (TH/T, PH/F, Y/I, grafias equivalentes)
- Geração de condições de pesquisa PostgREST / Supabase
- Tratamento de casos limite (strings vazias, caracteres especiais, números)
"""
import unittest
import name_phonetics


class TestNamePhonetics(unittest.TestCase):

    def test_remove_accents(self):
        self.assertEqual(name_phonetics.remove_accents("João"), "Joao")
        self.assertEqual(name_phonetics.remove_accents("António"), "Antonio")
        self.assertEqual(name_phonetics.remove_accents("Gonçalo"), "Goncalo")
        self.assertEqual(name_phonetics.remove_accents(""), "")
        self.assertEqual(name_phonetics.remove_accents(None), "")

    def test_normalize_token(self):
        self.assertEqual(name_phonetics.normalize_token("  D'Ávila  "), "davila")
        self.assertEqual(name_phonetics.normalize_token("São-Pedro!"), "saopedro")
        self.assertEqual(name_phonetics.normalize_token(""), "")

    def test_historical_variants_joao(self):
        vars_joao = name_phonetics.get_token_variants("João")
        self.assertIn("Joam", vars_joao)
        self.assertIn("Joao", vars_joao)
        self.assertIn("Joan", vars_joao)

    def test_historical_variants_manuel(self):
        vars_manuel = name_phonetics.get_token_variants("Manoel")
        self.assertIn("Manuel", vars_manuel)
        self.assertIn("Manoel", vars_manuel)

    def test_historical_variants_teresa(self):
        vars_teresa = name_phonetics.get_token_variants("Theresa")
        self.assertIn("Teresa", vars_teresa)
        self.assertIn("Tereza", vars_teresa)
        self.assertIn("Thereza", vars_teresa)

    def test_historical_variants_unknown_name(self):
        self.assertEqual(name_phonetics.get_token_variants("Zulmira"), ["Zulmira"])

    def test_expand_name_variants_composite(self):
        exp = name_phonetics.expand_name_variants("João da Silva")
        self.assertTrue(any("Joam" in v for v in exp))
        self.assertTrue(any("Silva" in v for v in exp))

    def test_soundex_pt_basic(self):
        # Nomes comuns
        s_joao = name_phonetics.soundex_pt("João")
        self.assertEqual(len(s_joao), 4)
        self.assertEqual(s_joao[0], "J")

    def test_soundex_pt_historical_equivalences(self):
        # Teresa / Theresa
        self.assertEqual(
            name_phonetics.soundex_pt("Teresa"),
            name_phonetics.soundex_pt("Theresa")
        )
        # Filippe / Filipe / Philipe
        self.assertEqual(
            name_phonetics.soundex_pt("Filipe"),
            name_phonetics.soundex_pt("Philipe")
        )
        # Luis / Luiz / Luys
        self.assertEqual(
            name_phonetics.soundex_pt("Luis"),
            name_phonetics.soundex_pt("Luiz")
        )
        self.assertEqual(
            name_phonetics.soundex_pt("Luis"),
            name_phonetics.soundex_pt("Luys")
        )
        # Mateus / Matheus
        self.assertEqual(
            name_phonetics.soundex_pt("Mateus"),
            name_phonetics.soundex_pt("Matheus")
        )

    def test_phonetic_match(self):
        self.assertTrue(name_phonetics.phonetic_match("Teresa", "Theresa"))
        self.assertTrue(name_phonetics.phonetic_match("Filipe", "Philipe"))
        self.assertFalse(name_phonetics.phonetic_match("João", "Manuel"))

    def test_build_postgrest_query_condition(self):
        cond = name_phonetics.build_postgrest_query_condition("Teresa")
        self.assertTrue(cond.startswith("or("))
        self.assertTrue(cond.endswith(")"))
        self.assertIn("nome.ilike.*Teresa*", cond)
        self.assertIn("nome.ilike.*Theresa*", cond)
        self.assertIn("freguesia.ilike.*Teresa*", cond)

    def test_build_postgrest_query_condition_empty(self):
        self.assertEqual(name_phonetics.build_postgrest_query_condition(""), "")
        self.assertEqual(name_phonetics.build_postgrest_query_condition("   "), "")


if __name__ == "__main__":
    unittest.main()
