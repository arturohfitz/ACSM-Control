import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity,
  Boxes,
  Building2,
  Calculator,
  ChevronDown,
  ClipboardList,
  FileUp,
  FolderKanban,
  Hammer,
  Home,
  Layers3,
  LogOut,
  Package,
  ReceiptText,
  Settings,
  Shield,
  ShoppingCart,
  Store,
  Users,
  Warehouse,
} from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { brand } from '../config/brand'
import { buildInfo } from '../config/buildInfo'

const navItems = [
  { to: '/', label: 'Inicio', icon: Home, permission: null },
  { to: '/companies', label: 'Constructoras', icon: Building2, permission: 'companies:view' },
  { to: '/clients', label: 'Desarrolladoras', icon: Building2, permission: 'clients:view' },
  { to: '/projects', label: 'Desarrollos', icon: FolderKanban, permission: 'projects:view' },
  { to: '/house-models', label: 'Modelos', icon: Layers3, permission: 'house_models:view' },
  { to: '/project-material-prices', label: 'Tabulador', icon: ClipboardList, permission: 'materials:view' },
  { to: '/materials', label: 'Catalogo materiales', icon: Package, permission: 'materials:view' },
  { to: '/suppliers', label: 'Proveedores', icon: Store, permission: 'suppliers:view' },
  { to: '/labor-rates', label: 'Mano de obra', icon: Hammer, permission: 'labor:view' },
  {
    to: '/construction-concepts',
    label: 'Conceptos',
    icon: ClipboardList,
    permission: 'construction_concepts:view',
  },
  { to: '/quotes', label: 'Cotizaciones', icon: Calculator, permission: 'quotes:view' },
  { to: '/purchasing', label: 'Compras', icon: ShoppingCart, permission: 'supplier_rfq:view' },
  { to: '/inventory', label: 'Inventario', icon: Warehouse, permission: 'inventory:view' },
  {
    to: '/supplier-payments',
    label: 'Pagos proveedores',
    icon: ReceiptText,
    permission: 'supplier_payments:view',
  },
  { to: '/users', label: 'Usuarios', icon: Users, permission: 'users:view' },
  { to: '/roles', label: 'Roles', icon: Shield, permission: 'roles:view' },
  { to: '/events', label: 'Eventos', icon: Activity, permission: 'events:view' },
  { to: '/settings', label: 'Ajustes', icon: Settings, permission: 'settings:view' },
]

const purchasingSubItems = [
  {
    to: '/purchasing',
    label: 'Solicitudes',
    icon: ShoppingCart,
    permission: 'supplier_rfq:view',
  },
  {
    to: '/purchasing/approvals',
    label: 'Aprobaciones',
    icon: ClipboardList,
    permission: 'supplier_quotes:approve',
  },
]

const inventorySubItems = [
  {
    to: '/inventory/purchase-order-receiving',
    label: 'Recepcion por OC',
    icon: Warehouse,
    permission: 'inventory:view',
    indent: true,
  },
  {
    to: '/inventory/external-receiving',
    label: 'Recepcion sin OC',
    icon: FileUp,
    permission: 'inventory:create',
    indent: true,
  },
  {
    to: '/inventory/document-validation',
    label: 'Validar documentos',
    icon: ClipboardList,
    permission: 'inventory:create',
    indent: true,
  },
  {
    to: '/inventory/documents',
    label: 'Documentos material',
    icon: ReceiptText,
    permission: 'inventory:view',
    indent: true,
  },
  {
    to: '/inventory/missing',
    label: 'Faltantes',
    icon: ClipboardList,
    permission: 'inventory:view',
    indent: true,
  },
  {
    to: '/inventory/stock',
    label: 'Existencias',
    icon: Package,
    permission: 'inventory:view',
    indent: true,
  },
]

const titles: Record<string, string> = {
  '/': 'Inicio',
  '/companies': 'Constructoras',
  '/clients': 'Desarrolladoras',
  '/projects': 'Desarrollos',
  '/house-models': 'Modelos por desarrolladora',
  '/project-material-prices': 'Tabulador del desarrollo',
  '/materials': 'Catalogo de materiales',
  '/suppliers': 'Proveedores',
  '/labor-rates': 'Mano de obra',
  '/construction-concepts': 'Conceptos de obra',
  '/quotes': 'Cotizaciones',
  '/purchasing': 'Compras',
  '/purchasing/approvals': 'Aprobaciones de compras',
  '/inventory': 'Inventario',
  '/inventory/purchase-order-receiving': 'Recepcion por orden de compra',
  '/inventory/external-receiving': 'Recepcion sin orden de compra',
  '/inventory/document-validation': 'Validar documentos externos',
  '/inventory/documents': 'Documentos de material',
  '/inventory/missing': 'Faltantes de material',
  '/inventory/stock': 'Existencias',
  '/supplier-payments': 'Pagos a proveedores',
  '/users': 'Usuarios',
  '/roles': 'Roles y permisos',
  '/events': 'Eventos del sistema',
  '/settings': 'Ajustes',
}

export default function AppLayout() {
  const { user, logout, hasPermission } = useAuth()
  const location = useLocation()
  const title = titles[location.pathname] ?? 'ACSM Control'
  const isPurchasingRoute = location.pathname.startsWith('/purchasing')
  const isInventoryRoute = location.pathname.startsWith('/inventory')
  const [purchasingOpen, setPurchasingOpen] = useState(isPurchasingRoute)
  const [inventoryOpen, setInventoryOpen] = useState(isInventoryRoute)
  const visiblePurchasingSubItems = useMemo(
    () => purchasingSubItems.filter((item) => hasPermission(item.permission)),
    [hasPermission],
  )
  const visibleInventorySubItems = useMemo(
    () => inventorySubItems.filter((item) => hasPermission(item.permission)),
    [hasPermission],
  )
  const visibleNavItems = useMemo(
    () => navItems.filter((item) => !item.permission || hasPermission(item.permission)),
    [hasPermission],
  )

  useEffect(() => {
    setPurchasingOpen(isPurchasingRoute)
  }, [isPurchasingRoute])

  useEffect(() => {
    setInventoryOpen(isInventoryRoute)
  }, [isInventoryRoute])

  return (
    <div className="acsm-app-shell min-h-screen overflow-x-hidden bg-acsm-canvas text-acsm-ink lg:grid lg:grid-cols-[264px_minmax(0,1fr)]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[264px] border-r border-acsm-sidebar-line bg-[linear-gradient(180deg,#081321_0%,#102a4b_54%,#09172a_100%)] text-white shadow-[18px_0_48px_rgba(2,13,31,0.34)] lg:flex lg:flex-col">
        <div className="flex h-[72px] items-center gap-3 border-b border-acsm-sidebar-line px-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.16),rgba(255,255,255,0.04))] shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]">
            {brand.logoPath ? (
              <img src={brand.logoPath} alt={brand.logoAlt} className="h-8 w-8 object-contain" />
            ) : (
              <Boxes className="h-5 w-5 text-acsm-gold" aria-hidden="true" />
            )}
          </div>
          <div className="min-w-0">
            <div className="truncate text-base font-semibold text-white">{brand.appName}</div>
            <div className="truncate text-xs text-acsm-sidebar-muted">{brand.companyName}</div>
          </div>
        </div>

        <nav className="scrollbar-thin flex-1 space-y-2 overflow-y-auto px-3 py-5">
          {visibleNavItems.map((item) => {
            const Icon = item.icon
            const hasPurchasingChildren = item.to === '/purchasing' && visiblePurchasingSubItems.length > 0
            const hasInventoryChildren = item.to === '/inventory' && visibleInventorySubItems.length > 0
            const isModuleOpen =
              (hasPurchasingChildren && purchasingOpen) || (hasInventoryChildren && inventoryOpen)

            return (
              <div
                key={item.to}
                className={[
                  'rounded-2xl transition',
                  isModuleOpen
                    ? 'border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.025))] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                    : '',
                ].join(' ')}
              >
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) => {
                    const isSectionActive =
                      isActive ||
                      (item.to === '/purchasing' && isPurchasingRoute) ||
                      (item.to === '/inventory' && isInventoryRoute)
                    return [
                      'group flex min-h-11 items-center gap-3 rounded-xl border px-3 py-2 text-sm font-semibold transition',
                      isSectionActive
                        ? 'border-sky-300/30 bg-[linear-gradient(180deg,#0d8bd3_0%,#0873b4_48%,#07578d_100%)] text-white shadow-[0_14px_28px_rgba(0,96,168,0.34),inset_0_1px_0_rgba(255,255,255,0.22)]'
                        : 'border-transparent text-acsm-sidebar-muted hover:border-white/10 hover:bg-white/10 hover:text-white',
                    ].join(' ')
                  }}
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/10 text-current ring-1 ring-white/10 transition group-hover:bg-white/15">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="truncate">{item.label}</span>
                  {hasPurchasingChildren || hasInventoryChildren ? (
                    <ChevronDown
                      className={[
                        'ml-auto h-4 w-4 shrink-0 opacity-80 transition-transform',
                        (hasPurchasingChildren && purchasingOpen) || (hasInventoryChildren && inventoryOpen)
                          ? 'rotate-180'
                          : '',
                      ].join(' ')}
                      aria-hidden="true"
                    />
                  ) : null}
                </NavLink>
                {hasPurchasingChildren ? (
                  <div className="mt-1 space-y-1">
                    {purchasingOpen ? (
                      <div className="space-y-1 border-l border-sky-200/20 pl-3">
                        {visiblePurchasingSubItems.map((subItem) => (
                          <NavLink
                            key={subItem.to}
                            to={subItem.to}
                            end={subItem.to === '/purchasing'}
                            className={({ isActive }) =>
                              [
                                'flex min-h-10 items-center gap-3 rounded-xl border px-3 py-2 text-[13px] font-semibold transition',
                                isActive
                                  ? 'border-sky-300/35 bg-[linear-gradient(180deg,rgba(14,128,203,0.95),rgba(9,96,157,0.92))] text-white shadow-[0_10px_20px_rgba(0,91,160,0.26)]'
                                  : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10 hover:text-white',
                              ].join(' ')
                            }
                          >
                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/10 ring-1 ring-white/10">
                              <subItem.icon className="h-3.5 w-3.5" aria-hidden="true" />
                            </span>
                            <span className="truncate">{subItem.label}</span>
                          </NavLink>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {hasInventoryChildren ? (
                  <div className="mt-1 space-y-1">
                    {inventoryOpen ? (
                      <div className="space-y-1 border-l border-sky-200/20 pl-3">
                        {visibleInventorySubItems.map((subItem) => (
                          <NavLink
                            key={subItem.to}
                            to={subItem.to}
                            className={({ isActive }) =>
                              [
                                'flex min-h-10 items-center gap-3 rounded-xl border px-3 py-2 text-[13px] font-semibold transition',
                                isActive
                                  ? 'border-sky-300/35 bg-[linear-gradient(180deg,rgba(14,128,203,0.95),rgba(9,96,157,0.92))] text-white shadow-[0_10px_20px_rgba(0,91,160,0.26)]'
                                  : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10 hover:text-white',
                              ].join(' ')
                            }
                          >
                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/10 ring-1 ring-white/10">
                              <subItem.icon className="h-3.5 w-3.5" aria-hidden="true" />
                            </span>
                            <span className="truncate">{subItem.label}</span>
                          </NavLink>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )
          })}
        </nav>

        <div className="border-t border-acsm-sidebar-line p-3">
          <div className="mb-3 rounded-xl border border-white/10 bg-black/15 px-3 py-2 text-[11px] text-acsm-sidebar-muted">
            <div className="flex items-center justify-between gap-2">
              <span className="font-bold uppercase tracking-[0.16em]">Version</span>
              <span className={buildInfo.dirty ? 'text-amber-200' : 'text-sky-100'}>
                {buildInfo.version}
                {buildInfo.dirty ? ' *' : ''}
              </span>
            </div>
            <div className="mt-1 truncate">{buildInfo.updatedAt}</div>
          </div>
          <div className="mb-3 rounded-xl border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.14),rgba(255,255,255,0.05))] px-3 py-2">
            <div className="truncate text-sm font-medium text-white">{user?.full_name}</div>
            <div className="truncate text-xs text-acsm-sidebar-muted">{user?.email}</div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm font-medium text-acsm-sidebar-muted transition hover:bg-white/10 hover:text-white"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Salir
          </button>
        </div>
      </aside>

      <div className="min-w-0 lg:col-start-2">
        <header className="sticky top-0 z-20 flex h-[72px] min-w-0 items-center justify-between border-b border-white/10 bg-[linear-gradient(180deg,#081321_0%,#0d2139_100%)] px-4 text-white shadow-[0_12px_34px_rgba(2,13,31,0.28)] lg:px-6">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-[0.24em] text-blue-100/70">
              Operacion
            </div>
            <h1 className="text-xl font-semibold text-white">{title}</h1>
          </div>
          <div className="hidden items-center gap-3 lg:flex">
            <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-right">
              <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-acsm-sidebar-muted">
                Sesion activa
              </div>
              <div className="max-w-[260px] truncate text-sm font-semibold text-white">{user?.email}</div>
            </div>
            <button
              type="button"
              onClick={logout}
              className="inline-flex h-11 items-center gap-2 rounded-xl border border-white/10 bg-white/10 px-4 text-sm font-semibold text-white hover:bg-white/20"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Salir
            </button>
          </div>
          <button
            type="button"
            onClick={logout}
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/10 px-3 text-sm font-medium text-white hover:bg-white/20 lg:hidden"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Salir
          </button>
        </header>

        <main className="min-w-0 overflow-x-hidden px-4 py-6 lg:px-7">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
