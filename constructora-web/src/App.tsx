import { Navigate, Route, Routes } from 'react-router-dom'

import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import DashboardPage from './pages/DashboardPage'
import EventsPage from './pages/EventsPage'
import {
  ClientsPage,
  CompaniesPage,
  ConstructionConceptsPage,
  HouseModelsPage,
  LaborRatesPage,
  MaterialsPage,
  ProjectMaterialPricesPage,
  ProjectsPage,
  QuotesPage,
  RolesPage,
  SuppliersPage,
  UsersPage,
} from './pages/GenericResourcePage'
import InventoryPage from './pages/InventoryPage'
import LoginPage from './pages/LoginPage'
import PurchasingApprovalsPage from './pages/PurchasingApprovalsPage'
import PurchasingOrdersPage from './pages/PurchasingOrdersPage'
import PurchasingPage from './pages/PurchasingPage'
import SettingsPage from './pages/SettingsPage'
import SupplierPaymentsPage from './pages/SupplierPaymentsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/house-models" element={<HouseModelsPage />} />
          <Route path="/project-material-prices" element={<ProjectMaterialPricesPage />} />
          <Route path="/materials" element={<MaterialsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/labor-rates" element={<LaborRatesPage />} />
          <Route path="/construction-concepts" element={<ConstructionConceptsPage />} />
          <Route path="/quotes" element={<QuotesPage />} />
          <Route path="/purchasing" element={<PurchasingPage />} />
          <Route path="/purchasing/approvals" element={<PurchasingApprovalsPage />} />
          <Route path="/purchasing/orders" element={<PurchasingOrdersPage />} />
          <Route path="/inventory" element={<Navigate to="/inventory/purchase-order-receiving" replace />} />
          <Route
            path="/inventory/purchase-order-receiving"
            element={<InventoryPage mode="purchase_order" />}
          />
          <Route
            path="/inventory/external-receiving"
            element={<InventoryPage mode="external_document" />}
          />
          <Route
            path="/inventory/document-validation"
            element={<InventoryPage mode="document_validation" />}
          />
          <Route path="/inventory/documents" element={<InventoryPage mode="documents" />} />
          <Route path="/inventory/missing" element={<InventoryPage mode="missing" />} />
          <Route path="/inventory/stock" element={<InventoryPage mode="stock" />} />
          <Route path="/supplier-payments" element={<SupplierPaymentsPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
