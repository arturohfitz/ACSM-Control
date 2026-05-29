import ResourcePage from '../components/ResourcePage'
import { resources } from '../config/resources'
import HouseModelsByDeveloperPage from './HouseModelsByDeveloperPage'
import QuoteTools from './QuoteTools'

export function ClientsPage() {
  return <ResourcePage config={resources.clients} />
}

export function CompaniesPage() {
  return <ResourcePage config={resources.companies} />
}

export function ProjectsPage() {
  return <ResourcePage config={resources.projects} />
}

export function HouseModelsPage() {
  return <HouseModelsByDeveloperPage />
}

export function MaterialsPage() {
  return <ResourcePage config={resources.materials} />
}

export function SuppliersPage() {
  return <ResourcePage config={resources.suppliers} />
}

export function ProjectMaterialPricesPage() {
  return <ResourcePage config={resources.projectMaterialPrices} />
}

export function LaborRatesPage() {
  return <ResourcePage config={resources.laborRates} />
}

export function ConstructionConceptsPage() {
  return <ResourcePage config={resources.constructionConcepts} />
}

export function QuotesPage() {
  return (
    <>
      <QuoteTools />
      <ResourcePage config={resources.quotes} />
    </>
  )
}

export function UsersPage() {
  return <ResourcePage config={resources.users} />
}

export function RolesPage() {
  return <ResourcePage config={resources.roles} />
}
