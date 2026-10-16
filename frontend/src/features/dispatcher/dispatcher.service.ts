export type CallCenterAllocation = { id: string; name: string; percentage: number }

const storageKey = 'group-elevate:dispatcher-allocations'

const defaultAllocations: CallCenterAllocation[] = [
  { id: 'call-center-a', name: 'Logicall', percentage: 50 },
  { id: 'call-center-b', name: 'Salesbound', percentage: 30 },
  { id: 'call-center-c', name: 'AtendeMais', percentage: 20 },
]

export async function getAllocations(): Promise<CallCenterAllocation[]> {
  await new Promise((resolve) => setTimeout(resolve, 200))
  const storedAllocations = localStorage.getItem(storageKey)
  if (!storedAllocations) {
    localStorage.setItem(storageKey, JSON.stringify(defaultAllocations))
    return defaultAllocations.map((item) => ({ ...item }))
  }

  try {
    return (JSON.parse(storedAllocations) as CallCenterAllocation[]).map((item) => ({
      ...item,
      name: defaultAllocations.find((center) => center.id === item.id)?.name ?? item.name,
    }))
  } catch {
    localStorage.setItem(storageKey, JSON.stringify(defaultAllocations))
    return defaultAllocations.map((item) => ({ ...item }))
  }
}

export async function saveAllocations(next: CallCenterAllocation[]): Promise<CallCenterAllocation[]> {
  await new Promise((resolve) => setTimeout(resolve, 250))
  if (next.some((item) => item.percentage < 0) || next.reduce((total, item) => total + item.percentage, 0) !== 100) {
    throw new Error('A soma das porcentagens precisa ser igual a 100%.')
  }
  const savedAllocations = next.map((item) => ({ ...item }))
  localStorage.setItem(storageKey, JSON.stringify(savedAllocations))
  return savedAllocations.map((item) => ({ ...item }))
}
