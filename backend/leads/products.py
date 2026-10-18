"""Catalogo de produtos usado pela API de leads e pelo LAB."""

from flask import Blueprint, jsonify
from sqlalchemy import select

from database import db_session
from .models import Product

products_blueprint = Blueprint('products', __name__, url_prefix='/api/products')


@products_blueprint.get('')
def list_products():
    with db_session() as db:
        products = db.scalars(
            select(Product).where(Product.is_active.is_(True)).order_by(Product.code)
        ).all()
        return jsonify(products=[{'code': p.code, 'name': p.name} for p in products])
