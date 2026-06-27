import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import DashboardPage from './pages/DashboardPage'
import EventsPage from './pages/EventsPage'
import {
  ClientsPage,
  CompaniesPage,
  HouseModelsPage,
  RolesPage,
  SuppliersPage,
  UsersPage,
} from './pages/GenericResourcePage'
import ConstructionConceptsPage from './pages/ConstructionConceptsPage'
import InventoryPage from './pages/InventoryPage'
import LoginPage from './pages/LoginPage'
import MaterialRequisitionsPage from './pages/MaterialRequisitionsPage'
import MaterialsPage from './pages/MaterialsPage'
import ProjectsPage from './pages/ProjectsPage'
import PurchasingApprovalsPage from './pages/PurchasingApprovalsPage'
import PurchasingOrdersPage from './pages/PurchasingOrdersPage'
import PurchasingPage from './pages/PurchasingPage'
import SettingsPage from './pages/SettingsPage'
import SupplierAgreementsPage from './pages/SupplierAgreementsPage'
import SupplierPaymentsPage from './pages/SupplierPaymentsPage'
import SupplierQuotePortalPage from './pages/SupplierQuotePortalPage'

function InventoryReceivingRedirect({ type }: { type: 'oc' | 'sin-oc' }) {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  params.set('type', type)
  return <Navigate to={`/inventory/material-receiving?${params.toString()}`} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/supplier/quote/:token" element={<SupplierQuotePortalPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/house-models" element={<HouseModelsPage />} />
          <Route path="/materials" element={<MaterialsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/supplier-agreements" element={<SupplierAgreementsPage />} />
          <Route path="/field-requisitions" element={<MaterialRequisitionsPage mode="field" />} />
          <Route path="/construction-concepts" element={<ConstructionConceptsPage />} />
          <Route path="/purchasing" element={<PurchasingPage />} />
          <Route
            path="/purchasing/material-requisitions"
            element={<MaterialRequisitionsPage mode="purchasing" />}
          />
          <Route path="/purchasing/approvals" element={<PurchasingApprovalsPage />} />
          <Route path="/purchasing/orders" element={<PurchasingOrdersPage />} />
          <Route path="/inventory" element={<InventoryReceivingRedirect type="oc" />} />
          <Route
            path="/inventory/material-receiving"
            element={<InventoryPage mode="material_receiving" />}
          />
          <Route
            path="/inventory/purchase-order-receiving"
            element={<InventoryReceivingRedirect type="oc" />}
          />
          <Route
            path="/inventory/external-receiving"
            element={<InventoryReceivingRedirect type="sin-oc" />}
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
