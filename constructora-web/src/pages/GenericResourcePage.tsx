import ResourcePage from '../components/ResourcePage'
import { resources } from '../config/resources'
import HouseModelsByDeveloperPage from './HouseModelsByDeveloperPage'

export function ClientsPage() {
  return <ResourcePage config={resources.clients} />
}

export function CompaniesPage() {
  return <ResourcePage config={resources.companies} />
}

export function HouseModelsPage() {
  return <HouseModelsByDeveloperPage />
}

export function SuppliersPage() {
  return <ResourcePage config={resources.suppliers} />
}

export function UsersPage() {
  return <ResourcePage config={resources.users} />
}

export function RolesPage() {
  return <ResourcePage config={resources.roles} />
}
