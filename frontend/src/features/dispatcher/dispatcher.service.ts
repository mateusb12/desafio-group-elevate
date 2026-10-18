import { csrfHeaders } from '../auth/auth.service'

export type CallCenterAllocation = { id: string; name: string; percentage: number }

type AllocationsResponse = { allocations?: CallCenterAllocation[]; error?: string }

async function readResponse(response: Response): Promise<AllocationsResponse> {
  const body = await response.json() as AllocationsResponse
  if (!response.ok) throw new Error(body.error ?? 'Não foi possível atualizar as configurações.')
  if (!Array.isArray(body.allocations)) throw new Error('Resposta inválida do dispatcher.')
  return body
}

export async function getAllocations(): Promise<CallCenterAllocation[]> {
  const response = await fetch('/api/api/dispatcher/weights', {
    credentials: 'same-origin',
  })
  const body = await readResponse(response)
  return body.allocations ?? []
}

export async function saveAllocations(next: CallCenterAllocation[]): Promise<CallCenterAllocation[]> {
  if (next.some((item) => item.percentage < 0) || next.reduce((total, item) => total + item.percentage, 0) !== 100) {
    throw new Error('A soma das porcentagens precisa ser igual a 100%.')
  }

  const response = await fetch('/api/api/dispatcher/weights', {
    method: 'PUT',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...csrfHeaders(),
    },
    body: JSON.stringify({
      allocations: next.map(({ id, percentage }) => ({ id, percentage })),
    }),
  })
  const body = await readResponse(response)
  return body.allocations ?? []
}
