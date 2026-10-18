from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
)


class CallCenterWebhookInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    lead_id: StrictStr = Field(min_length=1)
    external_id: StrictStr = Field(min_length=1, max_length=120)
    status: Literal[
        'new', 'contacted', 'no_answer', 'callback',
        'qualified', 'sale', 'refund', 'invalid',
    ]
    event_at: AwareDatetime

    @field_validator('event_at', mode='before')
    @classmethod
    def require_iso_string(cls, value):
        if not isinstance(value, str):
            raise ValueError('Informe uma data ISO 8601.')
        return value


def validate_webhook_payload(body):
    try:
        return CallCenterWebhookInput.model_validate(body), None
    except ValidationError as exc:
        location = exc.errors()[0]['loc']
        field = location[0] if location else None
        messages = {
            'lead_id': 'lead_id é obrigatório.',
            'external_id': 'external_id é obrigatório (até 120 caracteres).',
            'status': 'Status desconhecido.',
            'event_at': 'event_at inválido: informe data e timezone.',
        }
        return None, messages.get(field, 'Payload inválido.')
