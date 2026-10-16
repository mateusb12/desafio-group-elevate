export type UserRole = 'ADMIN' | 'OPERATOR'

export type AuthenticatedUser = {
  id: string
  name: string
  email: string
  role: UserRole
  callCenterId?: string
  callCenterName?: string
}
