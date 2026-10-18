"""Catálogos de produtos, funis e associações usados pela API e pelo LAB."""

from flask import Blueprint, jsonify
from sqlalchemy import select

from database import db_session
from .models import Funnel, LeadStatus, Product, ProductFunnel

catalog_blueprint = Blueprint('catalog', __name__, url_prefix='/api')


def seed_demo_catalog(db):
    products = {
        'nutralean': 'Nutralean',
        'curso-vendas': 'Curso de Vendas',
        'marketing-digital': 'Marketing Digital',
    }
    funnels = {
        'vsl-01': 'VSL 01',
        'webinar-02': 'Webinar 02',
        'checkout-03': 'Checkout 03',
    }
    statuses = {
        'new': 'Novo',
        'contacted': 'Contatado',
        'no_answer': 'Sem resposta',
        'callback': 'Retorno',
        'qualified': 'Qualificado',
        'sale': 'Venda',
        'refund': 'Reembolso',
        'invalid': 'Inválido',
    }

    for code, name in products.items():
        if db.get(Product, code) is None:
            db.add(Product(code=code, name=name))
    for code, name in funnels.items():
        if db.get(Funnel, code) is None:
            db.add(Funnel(code=code, name=name))
    for code, label in statuses.items():
        if db.get(LeadStatus, code) is None:
            db.add(LeadStatus(code=code, label=label))

    db.flush()
    for product_code in products:
        for funnel_code in funnels:
            if db.get(ProductFunnel, (product_code, funnel_code)) is None:
                db.add(ProductFunnel(
                    product_code=product_code,
                    funnel_code=funnel_code,
                ))
    db.commit()


@catalog_blueprint.get('/products')
def list_products():
    with db_session() as db:
        products = db.scalars(
            select(Product).order_by(Product.code)
        ).all()
        return jsonify(products=[{'code': p.code, 'name': p.name} for p in products])


@catalog_blueprint.get('/funnels')
def list_funnels():
    with db_session() as db:
        funnels = db.scalars(
            select(Funnel).order_by(Funnel.code)
        ).all()
        return jsonify(funnels=[{'code': f.code, 'name': f.name} for f in funnels])


@catalog_blueprint.get('/product-funnels')
def list_product_funnels():
    with db_session() as db:
        associations = db.execute(
            select(ProductFunnel.product_code, ProductFunnel.funnel_code)
            .join(Product, Product.code == ProductFunnel.product_code)
            .join(Funnel, Funnel.code == ProductFunnel.funnel_code)
            .order_by(ProductFunnel.product_code, ProductFunnel.funnel_code)
        ).all()
        return jsonify(
            associations=[
                {'productCode': product_code, 'funnelCode': funnel_code}
                for product_code, funnel_code in associations
            ]
        )
