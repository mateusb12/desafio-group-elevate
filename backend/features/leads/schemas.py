from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator


class TrackingData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(min_length=1, max_length=255)
    medium: str = Field(min_length=1, max_length=255)
    campaign: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=255)


class LeadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(pattern=r'^\+55\d{11}$')
    product: str = Field(min_length=1, max_length=80)
    funnel: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=100)
    campaign: str = Field(min_length=1, max_length=120)
    affiliate_id: str = Field(min_length=1, max_length=80)
    utm: TrackingData

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class LeadListQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    search: str | None = None
    product: str | None = None
    funnel: str | None = None
    source: str | None = None
    call_center_id: str | None = Field(default=None, alias='callCenterId')
    status: str | None = None
    from_date: date | None = Field(default=None, alias='from')
    to_date: date | None = Field(default=None, alias='to')
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=5, ge=1, le=100, alias='pageSize')

    @field_validator(
        'search', 'product', 'funnel', 'source', 'call_center_id', 'status',
        mode='before',
    )
    @classmethod
    def empty_string_to_none(cls, value):
        return None if value == '' else value


class LeadStatusUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Literal[
        'new', 'contacted', 'no_answer', 'callback',
        'qualified', 'sale', 'refund', 'invalid',
    ]


def validate_lead_status_update(body):
    try:
        return LeadStatusUpdateInput.model_validate(body), None
    except ValidationError:
        return None, 'Status inválido.'


def validate_lead_list_query(query):
    try:
        return LeadListQuery.model_validate(query), None
    except ValidationError as exc:
        field = exc.errors()[0]['loc'][0]
        if field in ('page', 'pageSize'):
            return None, 'page e pageSize devem ser números inteiros válidos.'
        if field in ('from', 'to'):
            return None, 'As datas devem usar o formato AAAA-MM-DD.'
        return None, 'Parâmetro de filtro inválido.'


def validation_error_message(error: ValidationError, body) -> str:
    if not isinstance(body, dict):
        return 'Envie um objeto JSON.'

    issue = error.errors()[0]
    field = issue['loc'][0]
    if field == 'email':
        return 'E-mail inválido.'
    if field == 'phone':
        return 'Telefone inválido. Use +55 seguido de DDD e 9 dígitos.'
    if field == 'utm':
        return 'UTM deve ser um objeto.' if not isinstance(body.get('utm'), dict) else 'UTM inválida.'
    return f'Campo inválido ou ausente: {field}.'
