from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class LoginInput(BaseModel):
    model_config = ConfigDict(strict=True)

    email: str = Field(min_length=1)
    password: str = Field(min_length=1)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


def validate_login(body):
    if not isinstance(body, dict):
        return None, 'JSON inválido.'

    try:
        return LoginInput.model_validate(body), None
    except ValidationError:
        return None, 'E-mail e senha são obrigatórios.'
