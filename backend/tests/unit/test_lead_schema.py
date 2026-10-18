import unittest

from pydantic import ValidationError
from features.leads.schemas import LeadInput, validation_error_message


class LeadSchemaTests(unittest.TestCase):
    def example(self):
        return {
            'name': ' Pessoa Teste ', 'email': ' TESTE@EXAMPLE.COM ',
            'phone': '+5585991234567', 'product': 'nutralean',
            'funnel': 'vsl-01', 'source': 'instagram',
            'campaign': 'campaign-123', 'affiliate_id': '999',
            'utm': {'source': 'instagram', 'medium': 'social',
                    'campaign': 'campaign-123', 'content': 'ad-01'},
        }

    def test_normalizacao(self):
        data = LeadInput.model_validate(self.example()).model_dump()
        self.assertEqual(data['name'], 'Pessoa Teste')
        self.assertEqual(data['email'], 'teste@example.com')
        self.assertIsInstance(data['utm'], dict)

    def test_scenarios_invalidos_do_lab(self):
        cases = [
            ({'email': 'email-sem-arroba'}, 'E-mail inválido.'),
            ({'phone': '123'}, 'Telefone inválido.'),
            ({'name': None}, 'Campo inválido ou ausente: name.'),
            ({'product': ''}, 'Campo inválido ou ausente: product.'),
            ({'utm': 'utm-invalida'}, 'UTM deve ser um objeto.'),
            ({'name': 12345}, 'Campo inválido ou ausente: name.'),
        ]
        for change, message in cases:
            with self.subTest(change=change):
                payload = {**self.example(), **change}
                with self.assertRaises(ValidationError) as caught:
                    LeadInput.model_validate(payload)
                self.assertIn(message, validation_error_message(caught.exception, payload))

    def test_nome_ausente_ou_so_espacos(self):
        for value in ({}, {'name': '   '}):
            payload = self.example()
            payload.update(value)
            if not value:
                del payload['name']
            with self.assertRaises(ValidationError):
                LeadInput.model_validate(payload)

    def test_codigo_de_funil_e_validado_pelo_catalogo(self):
        payload = self.example()
        payload['funnel'] = 'funil-inexistente'

        parsed = LeadInput.model_validate(payload).model_dump()

        self.assertEqual(parsed['funnel'], 'funil-inexistente')

    def test_utm_com_campo_invalido(self):
        payload = self.example()
        payload['utm'] = {'source': 'google', 'medium': 'cpc'}
        with self.assertRaises(ValidationError):
            LeadInput.model_validate(payload)
