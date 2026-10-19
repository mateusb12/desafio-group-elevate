import unittest

from features.dispatcher.models import CallCenter
from features.dispatcher.service import select_call_center


class DispatcherServiceTests(unittest.TestCase):
    def call_centers(self):
        return [
            CallCenter(
                id='call-center-a',
                name='Logicall',
                distribution_weight=50,
                is_active=True,
            ),
            CallCenter(
                id='call-center-b',
                name='Salesbound',
                distribution_weight=30,
                is_active=True,
            ),
            CallCenter(
                id='call-center-c',
                name='AtendeMais',
                distribution_weight=20,
                is_active=True,
            ),
        ]

    def test_selects_call_center_with_greatest_distribution_deficit(self):
        call_centers = self.call_centers()

        with self.subTest(
            "1.1 - selecionar o centro com maior déficit proporcional"
        ):
            selected = select_call_center(
                call_centers,
                {
                    'call-center-a': 5,
                    'call-center-b': 3,
                    'call-center-c': 0,
                },
                leads_after_assignment=9,
            )
            self.assertEqual(selected.id, 'call-center-c')

    def test_uses_weight_as_tie_breaker(self):
        call_centers = self.call_centers()

        with self.subTest(
            "2.1 - usar o maior peso como critério de desempate"
        ):
            selected = select_call_center(
                call_centers,
                {
                    'call-center-a': 0,
                    'call-center-b': 0,
                    'call-center-c': 0,
                },
                leads_after_assignment=1,
            )
            self.assertEqual(selected.id, 'call-center-a')

    def test_returns_deterministic_result_when_weight_and_deficit_tie(self):
        call_centers = [
            CallCenter(
                id='call-center-b',
                name='B',
                distribution_weight=50,
                is_active=True,
            ),
            CallCenter(
                id='call-center-a',
                name='A',
                distribution_weight=50,
                is_active=True,
            ),
        ]

        with self.subTest(
            "3.1 - usar o ID como último critério de desempate"
        ):
            selected = select_call_center(
                call_centers,
                {},
                leads_after_assignment=2,
            )
            self.assertEqual(selected.id, 'call-center-b')


if __name__ == '__main__':
    unittest.main(verbosity=2)
