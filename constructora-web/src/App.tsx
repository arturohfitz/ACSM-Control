import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useAuth } from './auth/AuthContext'
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
import InventoryWorkspacePage from './pages/InventoryWorkspacePage'
import LoginPage from './pages/LoginPage'
import MaterialRequisitionsPage from './pages/MaterialRequisitionsPage'
import MaterialsPage from './pages/MaterialsPage'
import ProjectsPage from './pages/ProjectsPage'
import PurchasingApprovalsPage from './pages/PurchasingApprovalsPage'
import PurchasingOrdersPage from './pages/PurchasingOrdersPage'
import PurchasingPage from './pages/PurchasingPage'
import PurchasingWorkspacePage from './pages/PurchasingWorkspacePage'
import SettingsPage from './pages/SettingsPage'
import SupplierAgreementsPage from './pages/SupplierAgreementsPage'
import SupplierPaymentsPage from './pages/SupplierPaymentsPage'
import SupplierQuotePortalPage from './pages/SupplierQuotePortalPage'
import WorkWorkspacePage from './pages/WorkWorkspacePage'

function InventoryReceivingRedirect({ type }: { type: 'oc' | 'sin-oc' }) {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  params.set('type', type)
  return <Navigate to={`/inventory/material-receiving?${params.toString()}`} replace />
}

function protect(element: ReactNode, permission: string | string[]) {
  return <ProtectedRoute permission={permission}>{element}</ProtectedRoute>
}

function HomeRoute() {
  const { hasPermission } = useAuth()
  if (hasPermission('executive_dashboard:view')) return <DashboardPage />
  if (hasPermission('material_requisitions:view')) return <Navigate to="/work" replace />
  if (hasPermission('supplier_rfq:view')) return <Navigate to="/purchasing" replace />
  if (hasPermission('inventory_receiving:view')) return <Navigate to="/inventory" replace />
  if (hasPermission('supplier_invoices:view')) return <Navigate to="/supplier-payments" replace />
  if (hasPermission('clients:view')) return <Navigate to="/clients" replace />
  if (hasPermission('users:view')) return <Navigate to="/users" replace />
  return <DashboardPage />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/supplier/quote/:token" element={<SupplierQuotePortalPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<HomeRoute />} />
          <Route
            path="/dashboard/projects/:projectId"
            element={protect(<DashboardPage />, 'executive_dashboard:view')}
          />
          <Route path="/companies" element={protect(<CompaniesPage />, 'companies:view')} />
          <Route path="/clients" element={protect(<ClientsPage />, 'clients:view')} />
          <Route path="/projects" element={protect(<ProjectsPage />, 'projects:view')} />
          <Route path="/house-models" element={protect(<HouseModelsPage />, 'house_models:view')} />
          <Route
            path="/work"
            element={protect(
              <WorkWorkspacePage />,
              ['materials:view', 'construction_concepts:view', 'material_requisitions:view'],
            )}
          />
          <Route path="/materials" element={protect(<MaterialsPage />, 'materials:view')} />
          <Route path="/suppliers" element={protect(<SuppliersPage />, 'suppliers:view')} />
          <Route
            path="/supplier-agreements"
            element={protect(<SupplierAgreementsPage />, 'supplier_agreements:view')}
          />
          <Route
            path="/field-requisitions"
            element={protect(<MaterialRequisitionsPage mode="field" />, 'material_requisitions:create')}
          />
          <Route
            path="/construction-concepts"
            element={protect(<ConstructionConceptsPage />, 'construction_concepts:view')}
          />
          <Route path="/purchasing" element={protect(<PurchasingWorkspacePage />, 'supplier_rfq:view')} />
          <Route path="/purchasing/cases/:caseId" element={protect(<PurchasingWorkspacePage />, 'supplier_rfq:view')} />
          <Route path="/purchasing/operations" element={protect(<PurchasingPage />, 'supplier_rfq:view')} />
          <Route
            path="/purchasing/material-requisitions"
            element={protect(<MaterialRequisitionsPage mode="purchasing" />, 'material_requisitions:review')}
          />
          <Route
            path="/purchasing/approvals"
            element={protect(<PurchasingApprovalsPage />, 'purchase_approvals:view')}
          />
          <Route
            path="/purchasing/orders"
            element={protect(<PurchasingOrdersPage />, 'purchase_orders:view')}
          />
          <Route
            path="/purchasing/audit"
            element={protect(<EventsPage scope="purchasing" />, 'purchasing_audit:view')}
          />
          <Route
            path="/inventory"
            element={protect(<InventoryWorkspacePage />, 'inventory_receiving:view')}
          />
          <Route
            path="/inventory/cases/:caseId"
            element={protect(<InventoryWorkspacePage />, 'inventory_receiving:view')}
          />
          <Route
            path="/inventory/material-receiving"
            element={protect(<InventoryPage mode="material_receiving" />, 'inventory_receiving:view')}
          />
          <Route
            path="/inventory/reception-history"
            element={protect(<InventoryPage mode="reception_history" />, 'inventory_reception_history:view')}
          />
          <Route
            path="/inventory/model-progress"
            element={protect(<InventoryPage mode="model_control" />, 'inventory_progress:view')}
          />
          <Route
            path="/inventory/purchase-order-receiving"
            element={protect(<InventoryReceivingRedirect type="oc" />, 'inventory_receiving:view')}
          />
          <Route
            path="/inventory/external-receiving"
            element={protect(<InventoryReceivingRedirect type="sin-oc" />, 'inventory_receiving:view')}
          />
          <Route
            path="/inventory/missing"
            element={protect(<InventoryPage mode="missing" />, 'inventory_missing:view')}
          />
          <Route
            path="/inventory/stock"
            element={protect(<InventoryPage mode="stock" />, 'inventory_stock:view')}
          />
          <Route
            path="/supplier-payments"
            element={protect(
              <SupplierPaymentsPage />,
              ['supplier_invoices:view', 'supplier_payments:view'],
            )}
          />
          <Route path="/users" element={protect(<UsersPage />, 'users:view')} />
          <Route path="/roles" element={protect(<RolesPage />, 'roles:view')} />
          <Route path="/events" element={protect(<EventsPage />, 'events:view')} />
          <Route path="/settings" element={protect(<SettingsPage />, 'settings:view')} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
