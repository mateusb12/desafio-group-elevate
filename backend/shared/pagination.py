from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate_query(db: Session, query, page: int, page_size: int):
    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0
    total_pages = (total + page_size - 1) // page_size if total else 0
    rows = db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()

    return rows, {
        'page': page,
        'pageSize': page_size,
        'total': total,
        'totalPages': total_pages,
    }
