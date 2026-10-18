"""Catálogos de produtos, funis e associações usados pela API e pelo LAB."""

from flask import Blueprint, jsonify
from sqlalchemy import select

from database import db_session
from .models import Funnel, Product, ProductFunnel

catalog_blueprint = Blueprint('catalog', __name__, url_prefix='/api')


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
