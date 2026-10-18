import math

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class AllocationInput(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str = Field(min_length=1)
    percentage: int | float

    @model_validator(mode='after')
    def validate_allocation(self):
        if not self.id.strip():
            raise ValueError('Cada alocação precisa de um id válido.')
        if self.percentage < 0 or not math.isfinite(self.percentage):
            raise ValueError('As porcentagens não podem ser negativas ou inválidas.')
        return self


class WeightsInput(BaseModel):
    model_config = ConfigDict(strict=True)

    allocations: list[AllocationInput] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_allocations(self):
        ids = [allocation.id for allocation in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError('Não repita o mesmo call center.')
        if not math.isclose(
            sum(allocation.percentage for allocation in self.allocations),
            100.0,
            abs_tol=1e-6,
        ):
            raise ValueError('A soma das porcentagens precisa ser igual a 100%.')
        return self


def validate_weights(body):
    if not isinstance(body, dict) or not isinstance(body.get('allocations'), list):
        return None, 'Envie allocations como uma lista.'
    if not body['allocations']:
        return None, 'Informe pelo menos um call center.'

    try:
        parsed = WeightsInput.model_validate(body)
    except ValidationError as exc:
        error = exc.errors()[0]
        location = error['loc']
        message = error['msg'].removeprefix('Value error, ')

        if message in {
            'Cada alocação precisa de um id válido.',
            'As porcentagens não podem ser negativas ou inválidas.',
        }:
            return None, message

        if location == ('allocations',):
            return None, 'Envie allocations como uma lista.'
        if len(location) >= 2 and location[0] == 'allocations':
            if len(location) == 2 and isinstance(location[1], int):
                return None, 'Cada alocação deve ser um objeto.'
            if location[-1] == 'id':
                return None, 'Cada alocação precisa de um id válido.'
            if location[-1] == 'percentage':
                return None, 'Cada porcentagem precisa ser numérica.'
        return None, message

    return [
        (allocation.id, float(allocation.percentage))
        for allocation in parsed.allocations
    ], None
