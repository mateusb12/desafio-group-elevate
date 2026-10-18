import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import delete, func, select

from shared.database import db_session
from features.leads.models import (
    Affiliate,
    Contact,
    Distribution,
    Funnel,
    Lead,
    Product,
    ProductFunnel,
)
from features.outbox.models import OutboxPendingDelivery


BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")


def post_lead(payload, idempotency_key=None):
    request = Request(
        f"{BASE_URL}/api/leads",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key or str(uuid4()),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


class CatalogAndDistributionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.marker = uuid4().hex[:10]
        cls.external_affiliate = f"integration-affiliate-{cls.marker}"
        cls.orphan_product = f"integration-product-{cls.marker}"
        cls.orphan_funnel = f"integration-funnel-{cls.marker}"

        with db_session() as db, db.begin():
            db.add(Product(
                code=cls.orphan_product,
                name="Integration Product",
            ))
            db.add(Funnel(
                code=cls.orphan_funnel,
                name="Integration Funnel",
            ))

        cls.addClassCleanup(cls.cleanup_data)

    @classmethod
    def cleanup_data(cls):
        with db_session() as db, db.begin():
            leads = db.scalars(
                select(Lead).where(Lead.campaign.like(f"integration-{cls.marker}-%"))
            ).all()
            lead_ids = [lead.id for lead in leads]
            contact_ids = [lead.contact_id for lead in leads]

            if lead_ids:
                db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
            if contact_ids:
                db.execute(delete(Contact).where(Contact.id.in_(contact_ids)))

            db.execute(delete(Affiliate).where(
                Affiliate.id == cls.external_affiliate
            ))
            db.execute(delete(ProductFunnel).where(
                ProductFunnel.product_code == cls.orphan_product
            ))
            db.execute(delete(Product).where(
                Product.code == cls.orphan_product
            ))
            db.execute(delete(Funnel).where(
                Funnel.code == cls.orphan_funnel
            ))

    def payload(self, suffix, **overrides):
        payload = {
            "name": f"Integration {suffix}",
            "email": f"{self.marker}-{suffix}@example.com",
            "phone": "+5585990000999",
            "product": "nutralean",
            "funnel": "vsl-01",
            "source": "integration",
            "campaign": f"integration-{self.marker}-{suffix}",
            "affiliate_id": self.external_affiliate,
            "utm": {
                "source": "integration",
                "medium": "test",
                "campaign": f"integration-{self.marker}-{suffix}",
                "content": "catalog-validation",
            },
        }
        payload.update(overrides)
        return payload

    def assert_bad_lead(self, suffix, **overrides):
        status, body = post_lead(self.payload(suffix, **overrides))
        self.assertEqual(status, 400, body)

    def test_catalog_validation_and_association(self):
        self.assert_bad_lead("missing-product", product="does-not-exist")
        self.assert_bad_lead("missing-funnel", funnel="does-not-exist")
        self.assert_bad_lead(
            "missing-association",
            product=self.orphan_product,
            funnel=self.orphan_funnel,
        )


    def test_valid_leads_affiliate_reuse_and_distribution(self):
        first_status, first_body = post_lead(self.payload("valid-1"))
        self.assertEqual(first_status, 201, first_body)

        second_status, second_body = post_lead(self.payload("valid-2"))
        self.assertEqual(second_status, 201, second_body)

        lead_ids = [first_body["id"], second_body["id"]]
        with db_session() as db:
            affiliate_count = db.scalar(
                select(func.count(Affiliate.id)).where(
                    Affiliate.id == self.external_affiliate
                )
            )
            distributions = db.scalars(
                select(Distribution).where(Distribution.lead_id.in_(lead_ids))
            ).all()
            pending_deliveries = db.scalars(
                select(OutboxPendingDelivery).where(
                    OutboxPendingDelivery.distribution_id.in_(
                        [distribution.id for distribution in distributions]
                    )
                )
            ).all()
            leads = db.scalars(select(Lead).where(Lead.id.in_(lead_ids))).all()

        self.assertEqual(affiliate_count, 1)
        self.assertEqual(len(distributions), 2)
        self.assertEqual(len(pending_deliveries), 2)
        self.assertTrue(all(
            delivery.event_type == 'lead.distributed'
            for delivery in pending_deliveries
        ))
        self.assertTrue(all(
            delivery.published_at is None
            for delivery in pending_deliveries
        ))
        self.assertEqual(
            {
                (delivery.payload['lead_id'], delivery.payload['distribution_id'],
                 delivery.payload['call_center_id'], delivery.payload['event_id'])
                for delivery in pending_deliveries
            },
            {
                (distribution.lead_id, distribution.id,
                 distribution.call_center_id, delivery.id)
                for distribution in distributions
                for delivery in pending_deliveries
                if delivery.distribution_id == distribution.id
            },
        )
        self.assertEqual(
            {distribution.lead_id for distribution in distributions},
            set(lead_ids),
        )
        self.assertTrue(all(distribution.reason == "initial" for distribution in distributions))
        self.assertEqual(
            {
                (lead.id, lead.call_center_id)
                for lead in leads
            },
            {
                (distribution.lead_id, distribution.call_center_id)
                for distribution in distributions
            },
        )

    def test_concurrent_new_affiliate_creation(self):
        payloads = [self.payload(f"affiliate-race-{number}") for number in range(20)]
        barrier = Barrier(len(payloads))

        def submit(payload):
            barrier.wait(timeout=15)
            return post_lead(payload)

        with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
            responses = list(executor.map(submit, payloads))

        self.assertTrue(all(status == 201 for status, _ in responses), responses)
        lead_ids = [body["id"] for _, body in responses]

        with db_session() as db:
            affiliate_count = db.scalar(
                select(func.count(Affiliate.id)).where(
                    Affiliate.id == self.external_affiliate
                )
            )
            distribution_count = db.scalar(
                select(func.count(Distribution.id)).where(
                    Distribution.lead_id.in_(lead_ids)
                )
            )
            pending_delivery_count = db.scalar(
                select(func.count(OutboxPendingDelivery.id)).where(
                    OutboxPendingDelivery.distribution_id.in_(
                        select(Distribution.id).where(
                            Distribution.lead_id.in_(lead_ids)
                        )
                    )
                )
            )

        self.assertEqual(affiliate_count, 1)
        self.assertEqual(distribution_count, len(lead_ids))
        self.assertEqual(pending_delivery_count, len(lead_ids))


if __name__ == "__main__":
    unittest.main(verbosity=2)
