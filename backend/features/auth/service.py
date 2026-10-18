from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from features.dispatcher.models import CallCenter

from .models import User, UserRole


def user_payload(db: Session, user: User) -> dict[str, str]:
    payload = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
    }
    if user.call_center_id:
        call_center_name = db.scalar(
            select(CallCenter.name).where(CallCenter.id == user.call_center_id)
        )
        payload["callCenterId"] = user.call_center_id
        payload["callCenterName"] = call_center_name or ""
    return payload


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active or not check_password_hash(user.password_hash, password):
        return None
    return user


def seed_demo_users(db: Session) -> None:
    """Cria ou atualiza dados demo sem resetar senhas e pesos existentes."""
    demo_centers = [
        ("call-center-a", "Logicall", 50),
        ("call-center-b", "Salesbound", 30),
        ("call-center-c", "AtendeMais", 20),
    ]

    for center_id, name, initial_weight in demo_centers:
        center = db.get(CallCenter, center_id)
        if center is None:
            db.add(CallCenter(
                id=center_id,
                name=name,
                distribution_weight=initial_weight,
            ))
        else:
            center.name = name

    db.flush()

    demo_users = [
        ("admin-1", "Rafael - Gestor Elevate",
         "admin@elevate.dev", UserRole.ADMIN, None),
        ("operator-1", "Ana - Logicall",
         "ana@logicall.example", UserRole.OPERATOR, "call-center-a"),
        ("operator-2", "Bruno - Salesbound",
         "bruno@salesbound.example", UserRole.OPERATOR, "call-center-b"),
        ("operator-3", "Carla - AtendeMais",
         "carla@atendemais.example", UserRole.OPERATOR, "call-center-c"),
    ]

    for user_id, name, email, role, center_id in demo_users:
        user = db.get(User, user_id)
        if user is None:
            db.add(User(
                id=user_id,
                name=name,
                email=email,
                password_hash=generate_password_hash("demo123"),
                role=role,
                call_center_id=center_id,
            ))
        else:
            user.name = name
            user.email = email
            user.role = role
            user.call_center_id = center_id

    db.commit()
