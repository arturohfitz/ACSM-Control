import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity,
  Bell,
  Boxes,
  Building2,
  CheckCircle2,
  Calculator,
  ChevronDown,
  Clock,
  ClipboardList,
  ExternalLink,
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
  X,
} from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { brand } from '../config/brand'
import { buildInfo } from '../config/buildInfo'
import { apiRequest } from '../lib/api'
import { ACTION_NOTICE_EVENT, type ActionNoticePayload } from '../lib/actionNotice'

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
  {
    to: '/purchasing/orders',
    label: 'Ordenes de compra',
    icon: ReceiptText,
    permission: 'purchase_orders:view',
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
  '/purchasing/orders': 'Ordenes de compra',
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

type NotificationItem = {
  id: number
  notification_type: string
  title: string
  body: string
  category: 'task' | 'deadline' | 'warning' | 'info' | 'exception'
  priority: 'low' | 'normal' | 'high' | 'critical'
  status: 'unread' | 'read' | 'resolved' | 'dismissed'
  source_module: string
  entity_label?: string | null
  action_url?: string | null
  due_at?: string | null
  created_at: string
}

type NotificationCounts = {
  unread: number
  open: number
}

const priorityStyles: Record<NotificationItem['priority'], string> = {
  low: 'border-slate-200 bg-slate-50 text-slate-700',
  normal: 'border-sky-200 bg-sky-50 text-sky-800',
  high: 'border-amber-200 bg-amber-50 text-amber-800',
  critical: 'border-rose-200 bg-rose-50 text-rose-800',
}

const priorityLabels: Record<NotificationItem['priority'], string> = {
  low: 'Baja',
  normal: 'Normal',
  high: 'Alta',
  critical: 'Critica',
}

function formatNotificationDate(value: string) {
  return new Intl.DateTimeFormat('es-MX', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

export default function AppLayout() {
  const { user, logout, hasPermission } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const title = titles[location.pathname] ?? 'ACSM Control'
  const isPurchasingRoute = location.pathname.startsWith('/purchasing')
  const isInventoryRoute = location.pathname.startsWith('/inventory')
  const [purchasingOpen, setPurchasingOpen] = useState(isPurchasingRoute)
  const [inventoryOpen, setInventoryOpen] = useState(isInventoryRoute)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [notificationCounts, setNotificationCounts] = useState<NotificationCounts>({
    unread: 0,
    open: 0,
  })
  const [notificationsLoading, setNotificationsLoading] = useState(false)
  const [actionNotice, setActionNotice] = useState<
    (Required<ActionNoticePayload> & { id: number }) | null
  >(null)
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

  const loadNotificationCounts = useCallback(async () => {
    try {
      const counts = await apiRequest<NotificationCounts>('/notifications/counts')
      setNotificationCounts(counts)
    } catch {
      setNotificationCounts({ unread: 0, open: 0 })
    }
  }, [])

  const loadNotifications = useCallback(async () => {
    setNotificationsLoading(true)
    try {
      const [counts, items] = await Promise.all([
        apiRequest<NotificationCounts>('/notifications/counts'),
        apiRequest<NotificationItem[]>('/notifications?status_filter=open&limit=20'),
      ])
      setNotificationCounts(counts)
      setNotifications(items)
    } catch {
      setNotifications([])
    } finally {
      setNotificationsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!user) return
    loadNotificationCounts()
    const timer = window.setInterval(loadNotificationCounts, 60000)
    return () => window.clearInterval(timer)
  }, [loadNotificationCounts, user])

  useEffect(() => {
    if (notificationsOpen) {
      loadNotifications()
    }
  }, [loadNotifications, notificationsOpen])

  useEffect(() => {
    function handleActionNotice(event: Event) {
      const detail = (event as CustomEvent<ActionNoticePayload>).detail
      if (!detail?.message) return
      setActionNotice({
        id: Date.now(),
        message: detail.message,
        kind: detail.kind ?? 'success',
      })
    }

    window.addEventListener(ACTION_NOTICE_EVENT, handleActionNotice)
    return () => window.removeEventListener(ACTION_NOTICE_EVENT, handleActionNotice)
  }, [])

  useEffect(() => {
    if (!actionNotice) return undefined
    const timer = window.setTimeout(() => setActionNotice(null), 5200)
    return () => window.clearTimeout(timer)
  }, [actionNotice])

  async function markNotificationRead(notificationId: number) {
    await apiRequest<NotificationItem>(`/notifications/${notificationId}/read`, { method: 'POST' })
    await loadNotifications()
  }

  async function resolveNotification(notificationId: number) {
    await apiRequest<NotificationItem>(`/notifications/${notificationId}/resolve`, { method: 'POST' })
    await loadNotifications()
  }

  async function openNotification(notification: NotificationItem) {
    if (notification.status === 'unread') {
      await apiRequest<NotificationItem>(`/notifications/${notification.id}/read`, { method: 'POST' })
    }
    setNotificationsOpen(false)
    await loadNotificationCounts()
    if (notification.action_url) {
      navigate(notification.action_url)
    }
  }

  async function markAllNotificationsRead() {
    await apiRequest('/notifications/mark-all-read', { method: 'POST' })
    await loadNotifications()
  }

  const actionNoticeTitle = actionNotice
    ? {
        success: 'Accion completada',
        info: 'Aviso registrado',
        warning: 'Requiere atencion',
        error: 'No se pudo completar',
      }[actionNotice.kind]
    : ''

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
          <div className="shrink-0">
            <div className="text-[11px] font-bold uppercase tracking-[0.24em] text-blue-100/70">
              Operacion
            </div>
            <h1 className="text-xl font-semibold text-white">{title}</h1>
          </div>
          <div className="mx-5 hidden min-w-0 flex-1 lg:block" />
          <div className="hidden shrink-0 items-center gap-3 lg:flex">
            <div className="relative">
              <button
                type="button"
                onClick={() => setNotificationsOpen((value) => !value)}
                className="relative inline-flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/10 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.16)] transition hover:bg-white/20"
                aria-label="Notificaciones"
              >
                <Bell className="h-5 w-5" aria-hidden="true" />
                {notificationCounts.unread > 0 ? (
                  <span className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full border-2 border-[#081321] bg-rose-500 px-1 text-[10px] font-bold text-white shadow-lg">
                    {notificationCounts.unread > 99 ? '99+' : notificationCounts.unread}
                  </span>
                ) : null}
              </button>
            </div>
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
            onClick={() => setNotificationsOpen((value) => !value)}
            className="relative inline-flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/10 px-3 text-sm font-medium text-white hover:bg-white/20 lg:hidden"
            aria-label="Notificaciones"
          >
            <Bell className="h-4 w-4" aria-hidden="true" />
            {notificationCounts.unread > 0 ? (
              <span className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full border-2 border-[#081321] bg-rose-500 px-1 text-[10px] font-bold text-white">
                {notificationCounts.unread > 99 ? '99+' : notificationCounts.unread}
              </span>
            ) : null}
          </button>
          <button
            type="button"
            onClick={logout}
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/10 px-3 text-sm font-medium text-white hover:bg-white/20 lg:hidden"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Salir
          </button>
        </header>

        {actionNotice ? (
          <div className="fixed left-4 right-4 top-24 z-50 sm:left-auto sm:right-6 sm:w-[390px]">
            <div
              key={actionNotice.id}
              role="status"
              aria-live="polite"
              className={[
                'overflow-hidden rounded-3xl border bg-white shadow-[0_26px_70px_rgba(2,13,31,0.36),inset_0_1px_0_rgba(255,255,255,0.86)]',
                actionNotice.kind === 'error'
                  ? 'border-rose-200'
                  : actionNotice.kind === 'warning'
                    ? 'border-amber-200'
                    : actionNotice.kind === 'info'
                      ? 'border-sky-200'
                      : 'border-emerald-200',
              ].join(' ')}
            >
              <div
                className={[
                  'h-1.5',
                  actionNotice.kind === 'error'
                    ? 'bg-rose-500'
                    : actionNotice.kind === 'warning'
                      ? 'bg-amber-400'
                      : actionNotice.kind === 'info'
                        ? 'bg-sky-500'
                        : 'bg-emerald-500',
                ].join(' ')}
              />
              <div className="flex items-start gap-3 p-4">
                <div
                  className={[
                    'mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border',
                    actionNotice.kind === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-700'
                      : actionNotice.kind === 'warning'
                        ? 'border-amber-200 bg-amber-50 text-amber-800'
                        : actionNotice.kind === 'info'
                          ? 'border-sky-200 bg-sky-50 text-sky-800'
                          : 'border-emerald-200 bg-emerald-50 text-emerald-800',
                  ].join(' ')}
                >
                  <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-acsm-muted">
                    {actionNoticeTitle}
                  </div>
                  <div className="mt-1 text-sm font-bold leading-5 text-acsm-ink">
                    {actionNotice.message}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActionNotice(null)}
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-acsm-muted transition hover:border-sky-200 hover:text-acsm-ink"
                  aria-label="Cerrar notificacion"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {notificationsOpen ? (
          <div className="fixed right-4 top-20 z-40 w-[min(430px,calc(100vw-2rem))] overflow-hidden rounded-3xl border border-sky-100 bg-white shadow-[0_28px_90px_rgba(3,27,54,0.34)]">
            <div className="flex items-start justify-between gap-4 border-b border-sky-100 bg-[linear-gradient(135deg,#ffffff_0%,#e8f5ff_100%)] px-5 py-4">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-acsm-muted">
                  Centro de alertas
                </div>
                <h2 className="text-lg font-bold text-acsm-ink">Notificaciones</h2>
                <p className="text-sm text-acsm-muted">
                  {notificationCounts.open} pendiente(s), {notificationCounts.unread} nueva(s)
                </p>
              </div>
              <button
                type="button"
                onClick={() => setNotificationsOpen(false)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-sky-100 bg-white text-acsm-muted hover:text-acsm-ink"
                aria-label="Cerrar notificaciones"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-sky-100 px-5 py-3">
              <span className="text-sm font-semibold text-acsm-ink">
                Pendientes de atencion
              </span>
              <button
                type="button"
                onClick={markAllNotificationsRead}
                disabled={!notificationCounts.unread}
                className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-bold text-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Marcar leidas
              </button>
            </div>
            <div className="max-h-[68vh] space-y-3 overflow-y-auto bg-slate-50/80 p-4">
              {notificationsLoading ? (
                <div className="rounded-2xl border border-sky-100 bg-white px-4 py-5 text-sm text-acsm-muted">
                  Cargando notificaciones...
                </div>
              ) : notifications.length === 0 ? (
                <div className="rounded-2xl border border-sky-100 bg-white px-4 py-6 text-center">
                  <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500" aria-hidden="true" />
                  <div className="mt-2 font-bold text-acsm-ink">Sin pendientes</div>
                  <p className="text-sm text-acsm-muted">Todo esta al dia por ahora.</p>
                </div>
              ) : (
                notifications.map((notification) => (
                  <article
                    key={notification.id}
                    className={[
                      'rounded-2xl border bg-white p-4 shadow-[0_12px_30px_rgba(16,60,105,0.08)]',
                      notification.status === 'unread'
                        ? 'border-sky-300 ring-2 ring-sky-100'
                        : 'border-sky-100',
                    ].join(' ')}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={[
                              'rounded-full border px-2.5 py-1 text-[11px] font-bold',
                              priorityStyles[notification.priority],
                            ].join(' ')}
                          >
                            {priorityLabels[notification.priority]}
                          </span>
                          {notification.status === 'unread' ? (
                            <span className="rounded-full bg-rose-100 px-2.5 py-1 text-[11px] font-bold text-rose-700">
                              Nueva
                            </span>
                          ) : null}
                        </div>
                        <h3 className="mt-2 text-base font-bold text-acsm-ink">
                          {notification.title}
                        </h3>
                      </div>
                      <div className="flex shrink-0 items-center gap-1 text-xs text-acsm-muted">
                        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                        {formatNotificationDate(notification.created_at)}
                      </div>
                    </div>
                    <p className="mt-2 text-sm leading-5 text-acsm-muted">{notification.body}</p>
                    {notification.entity_label ? (
                      <div className="mt-3 rounded-xl border border-sky-100 bg-sky-50/70 px-3 py-2 text-xs font-semibold text-sky-800">
                        {notification.entity_label}
                      </div>
                    ) : null}
                    <div className="mt-4 flex flex-wrap gap-2">
                      {notification.action_url ? (
                        <button
                          type="button"
                          onClick={() => openNotification(notification)}
                          className="inline-flex h-9 items-center gap-2 rounded-xl bg-[linear-gradient(180deg,#0d8bd3,#07578d)] px-3 text-sm font-bold text-white shadow-[0_10px_22px_rgba(0,91,160,0.22)]"
                        >
                          <ExternalLink className="h-4 w-4" aria-hidden="true" />
                          Abrir
                        </button>
                      ) : null}
                      {notification.status === 'unread' ? (
                        <button
                          type="button"
                          onClick={() => markNotificationRead(notification.id)}
                          className="inline-flex h-9 items-center rounded-xl border border-sky-200 bg-white px-3 text-sm font-bold text-acsm-ink"
                        >
                          Leida
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => resolveNotification(notification.id)}
                        className="inline-flex h-9 items-center rounded-xl border border-sky-200 bg-white px-3 text-sm font-bold text-acsm-muted"
                      >
                        Resolver
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
        ) : null}

        <main className="min-w-0 overflow-x-hidden px-4 py-6 lg:px-7">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
