import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  CircleDollarSign,
  ClipboardCheck,
  Download,
  FileText,
  PackageCheck,
  RefreshCw,
  Search,
  ShoppingCart,
  Warehouse,
} from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { apiRequest } from '../lib/api'

type PortfolioTotals = {
  project_count: number
  active_project_count: number
  attention_project_count: number
  houses_count: number
  budget_amount: number
  committed_amount: number
  received_amount: number
  invoiced_amount: number
  paid_amount: number
  available_amount: number
  over_budget_amount: number
  purchase_orders_count: number
  invoices_count: number
  payments_count: number
}

type FlowStage = {
  key: string
  label: string
  count: number
  attention_count: number
  description: string
  action_url: string
}

type ExecutiveAlert = {
  key: string
  project_id: number | null
  project_name: string | null
  title: string
  detail: string
  priority: string
  action_label: string
  action_url: string
}

type ProjectRow = {
  project_id: number
  project_name: string
  client_name: string
  houses_count: number
  models_count: number
  baseline_id: number | null
  baseline_revision: number | null
  budget_amount: number
  committed_amount: number
  received_amount: number
  invoiced_amount: number
  paid_amount: number
  available_amount: number
  over_budget_amount: number
  committed_percent: number
  received_percent: number
  invoiced_percent: number
  paid_percent: number
  purchase_orders_count: number
  invoices_count: number
  payments_count: number
  integrity_issues: string[]
  health: 'healthy' | 'attention' | 'critical'
  health_label: string
  next_action_label: string
  next_action_url: string
}

type MaterialRow = {
  baseline_item_id: number
  house_model_name: string
  source_code: string | null
  description: string
  unit: string
  houses_quantity: number
  quantity_per_house: number
  budget_quantity: number
  ordered_quantity: number
  received_quantity: number
  budget_amount: number
  committed_amount: number
  received_amount: number
  invoiced_amount: number
  paid_amount: number
  available_amount: number
  committed_percent: number
  paid_percent: number
  status: string
}

type DashboardResponse = {
  generated_at: string
  selected_project_id: number | null
  totals: PortfolioTotals
  flow: FlowStage[]
  alerts: ExecutiveAlert[]
  projects: ProjectRow[]
  materials: MaterialRow[]
}

const money = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
  maximumFractionDigits: 0,
})

const quantity = new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 })

function amount(value: number | string) {
  return money.format(Number(value || 0))
}

function percent(value: number | string) {
  return `${Number(value || 0).toFixed(1)}%`
}

function healthStyle(health: ProjectRow['health']) {
  if (health === 'critical') return 'border-red-200 bg-red-50 text-red-800'
  if (health === 'attention') return 'border-amber-200 bg-amber-50 text-amber-800'
  return 'border-emerald-200 bg-emerald-50 text-emerald-700'
}

function materialStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: 'Pendiente',
    partial: 'Parcial',
    complete: 'Completo',
    over_budget: 'Excedido',
  }
  return labels[status] ?? status
}

function ProgressBar({ value, tone = 'blue' }: { value: number; tone?: 'blue' | 'teal' | 'green' }) {
  const color = tone === 'green' ? 'bg-emerald-500' : tone === 'teal' ? 'bg-cyan-500' : 'bg-blue-600'
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full ${color}`} style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }} />
    </div>
  )
}

export default function DashboardPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const selectedProjectId = projectId ? Number(projectId) : null
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [approving, setApproving] = useState(false)
  const [error, setError] = useState('')
  const [clientFilter, setClientFilter] = useState('')
  const [projectSearch, setProjectSearch] = useState('')
  const [materialSearch, setMaterialSearch] = useState('')
  const [materialStatus, setMaterialStatus] = useState('all')
  const [showAllMaterials, setShowAllMaterials] = useState(false)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const query = selectedProjectId ? `?project_id=${selectedProjectId}` : ''
      setData(await apiRequest<DashboardResponse>(`/executive-dashboard${query}`))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar el control ejecutivo')
    } finally {
      setLoading(false)
    }
  }, [selectedProjectId])

  useEffect(() => {
    void loadDashboard()
  }, [loadDashboard])

  const clients = useMemo(
    () => Array.from(new Set((data?.projects ?? []).map((project) => project.client_name))).sort(),
    [data?.projects],
  )
  const filteredProjects = useMemo(() => {
    const search = projectSearch.trim().toLocaleLowerCase('es-MX')
    return (data?.projects ?? []).filter((project) => {
      if (clientFilter && project.client_name !== clientFilter) return false
      if (!search) return true
      return `${project.project_name} ${project.client_name}`.toLocaleLowerCase('es-MX').includes(search)
    })
  }, [clientFilter, data?.projects, projectSearch])
  const selectedProject = selectedProjectId ? data?.projects[0] ?? null : null
  const filteredMaterials = useMemo(() => {
    const search = materialSearch.trim().toLocaleLowerCase('es-MX')
    return (data?.materials ?? []).filter((material) => {
      if (materialStatus !== 'all' && material.status !== materialStatus) return false
      if (!search) return true
      return `${material.source_code ?? ''} ${material.description} ${material.house_model_name}`
        .toLocaleLowerCase('es-MX')
        .includes(search)
    })
  }, [data?.materials, materialSearch, materialStatus])
  const visibleMaterials = showAllMaterials ? filteredMaterials : filteredMaterials.slice(0, 10)

  async function approveBaseline() {
    if (!selectedProject || approving) return
    setApproving(true)
    setError('')
    try {
      await apiRequest(`/purchasing/projects/${selectedProject.project_id}/material-budget-baselines`, {
        method: 'POST',
        body: JSON.stringify({ notes: 'Linea base aprobada desde Control Ejecutivo' }),
      })
      await loadDashboard()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible aprobar la linea base')
    } finally {
      setApproving(false)
    }
  }

  function exportPortfolio() {
    if (!data) return
    const rows = [
      ['Desarrollo', 'Inmobiliaria', 'Viviendas', 'Presupuesto', 'Comprometido', 'Recibido', 'Facturado', 'Pagado', 'Estado'],
      ...data.projects.map((project) => [
        project.project_name,
        project.client_name,
        project.houses_count,
        project.budget_amount,
        project.committed_amount,
        project.received_amount,
        project.invoiced_amount,
        project.paid_amount,
        project.health_label,
      ]),
    ]
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `control-ejecutivo-${new Date().toISOString().slice(0, 10)}.csv`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  if (loading && !data) {
    return (
      <div className="flex min-h-[320px] items-center justify-center rounded-md border border-acsm-line bg-white shadow-panel">
        <RefreshCw className="h-6 w-6 animate-spin text-acsm-green" aria-label="Cargando control ejecutivo" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-800">
          {error}
        </div>
      )}

      <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-green">
              <Building2 className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-acsm-muted">
                Dirección y control
              </div>
              <h2 className="font-semibold text-acsm-ink">
                {selectedProject ? selectedProject.project_name : 'Control Ejecutivo'}
              </h2>
              <p className="text-xs text-acsm-muted">
                Avance financiero y de abastecimiento. No representa avance físico ejecutado.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {selectedProjectId && (
              <button
                type="button"
                onClick={() => navigate('/')}
                className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold hover:bg-acsm-paper"
              >
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                Portafolio
              </button>
            )}
            {hasPermission('executive_dashboard:export') && !selectedProjectId && (
              <button
                type="button"
                onClick={exportPortfolio}
                className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold hover:bg-acsm-paper"
              >
                <Download className="h-4 w-4" aria-hidden="true" />
                Exportar
              </button>
            )}
            <button
              type="button"
              onClick={() => void loadDashboard()}
              disabled={loading}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold hover:bg-acsm-paper disabled:opacity-60"
            >
              <RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} aria-hidden="true" />
              Actualizar
            </button>
          </div>
        </div>

        {!selectedProjectId && (
          <div className="grid gap-2 border-b border-acsm-line bg-acsm-paper px-4 py-3 md:grid-cols-[minmax(220px,0.6fr)_minmax(280px,1fr)_auto]">
            <select
              aria-label="Filtrar por inmobiliaria"
              value={clientFilter}
              onChange={(event) => setClientFilter(event.target.value)}
              className="h-10 rounded-md border border-acsm-line bg-white px-3 text-sm"
            >
              <option value="">Todas las inmobiliarias</option>
              {clients.map((client) => <option key={client}>{client}</option>)}
            </select>
            <label className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-acsm-muted" aria-hidden="true" />
              <input
                value={projectSearch}
                onChange={(event) => setProjectSearch(event.target.value)}
                placeholder="Buscar desarrollo o inmobiliaria"
                className="h-10 w-full rounded-md border border-acsm-line bg-white pl-9 pr-3 text-sm"
              />
            </label>
            <div className="flex items-center text-xs font-medium text-acsm-muted">
              Actualizado {data ? new Date(data.generated_at).toLocaleString('es-MX') : '-'}
            </div>
          </div>
        )}

        {data && (
          <div className="grid grid-cols-2 divide-x divide-y divide-acsm-line sm:grid-cols-3 xl:grid-cols-6">
            {[
              { label: 'Presupuesto', value: amount(data.totals.budget_amount), detail: `${data.totals.project_count} desarrollos`, icon: CircleDollarSign },
              { label: 'Comprometido', value: amount(data.totals.committed_amount), detail: `${data.totals.purchase_orders_count} ordenes`, icon: ShoppingCart },
              { label: 'Recibido', value: amount(data.totals.received_amount), detail: 'Material aceptado', icon: Warehouse },
              { label: 'Facturado', value: amount(data.totals.invoiced_amount), detail: `${data.totals.invoices_count} facturas`, icon: FileText },
              { label: 'Pagado', value: amount(data.totals.paid_amount), detail: `${data.totals.payments_count} pagos`, icon: CheckCircle2 },
              { label: 'Disponible', value: amount(data.totals.available_amount), detail: data.totals.over_budget_amount > 0 ? `${amount(data.totals.over_budget_amount)} excedido` : 'Por ejercer', icon: ClipboardCheck },
            ].map((metric) => {
              const Icon = metric.icon
              return (
                <div key={metric.label} className="min-w-0 px-4 py-3">
                  <div className="flex items-center justify-between gap-2 text-[10px] font-bold uppercase text-acsm-muted">
                    {metric.label}
                    <Icon className="h-4 w-4 text-acsm-green" aria-hidden="true" />
                  </div>
                  <div className="mt-1 truncate text-lg font-bold text-acsm-ink" title={metric.value}>{metric.value}</div>
                  <div className="text-xs text-acsm-muted">{metric.detail}</div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {!selectedProjectId && data && (
        <>
          <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
            <div className="border-b border-acsm-line px-4 py-3">
              <h2 className="font-semibold text-acsm-ink">Flujo operativo</h2>
              <p className="text-xs text-acsm-muted">Cada etapa abre directamente la bandeja que requiere atención.</p>
            </div>
            <div className="grid grid-cols-2 xl:grid-cols-7">
              {data.flow.map((stage, index) => (
                <button
                  key={stage.key}
                  type="button"
                  onClick={() => navigate(stage.action_url)}
                  className="group min-h-28 border-b border-r border-acsm-line p-3 text-left hover:bg-acsm-paper"
                >
                  <div className="flex items-center justify-between">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-blue-700">
                      {index + 1}
                    </span>
                    <span className={stage.attention_count ? 'rounded-full bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-800' : 'rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-600'}>
                      {stage.count}
                    </span>
                  </div>
                  <div className="mt-2 text-sm font-bold text-acsm-ink">{stage.label}</div>
                  <div className="mt-1 text-xs leading-4 text-acsm-muted">{stage.description}</div>
                </button>
              ))}
            </div>
          </section>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
            <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
              <div className="flex items-center justify-between border-b border-acsm-line px-4 py-3">
                <div>
                  <h2 className="font-semibold text-acsm-ink">Portafolio de desarrollos</h2>
                  <p className="text-xs text-acsm-muted">Comparativo consolidado con acceso al detalle de cada proyecto.</p>
                </div>
                <span className="text-xs font-semibold text-acsm-muted">{filteredProjects.length} visibles</span>
              </div>
              <div className="hidden overflow-x-auto lg:block">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead className="bg-acsm-paper text-[10px] font-bold uppercase text-acsm-muted">
                    <tr>
                      <th className="px-4 py-2">Desarrollo</th>
                      <th className="px-3 py-2 text-right">Presupuesto</th>
                      <th className="px-3 py-2">Abastecimiento</th>
                      <th className="px-3 py-2 text-right">Pagado</th>
                      <th className="px-3 py-2">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-acsm-line">
                    {filteredProjects.map((project) => (
                      <tr key={project.project_id} className="hover:bg-acsm-paper">
                        <td className="px-4 py-3">
                          <button type="button" onClick={() => navigate(`/dashboard/projects/${project.project_id}`)} className="font-bold text-acsm-ink hover:text-acsm-green hover:underline">{project.project_name}</button>
                          <div className="text-xs text-acsm-muted">{project.client_name} · {quantity.format(project.houses_count)} viviendas</div>
                        </td>
                        <td className="px-3 py-3 text-right font-semibold">{amount(project.budget_amount)}</td>
                        <td className="w-48 px-3 py-3">
                          <div className="mb-1 flex justify-between text-xs"><span>Recibido</span><strong>{percent(project.received_percent)}</strong></div>
                          <ProgressBar value={Number(project.received_percent)} />
                        </td>
                        <td className="px-3 py-3 text-right">
                          <div className="font-semibold">{amount(project.paid_amount)}</div>
                          <div className="text-xs text-acsm-muted">{percent(project.paid_percent)}</div>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-bold ${healthStyle(project.health)}`}>
                            {project.health_label}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="divide-y divide-acsm-line lg:hidden">
                {filteredProjects.map((project) => (
                  <button key={project.project_id} type="button" onClick={() => navigate(`/dashboard/projects/${project.project_id}`)} className="block w-full p-4 text-left hover:bg-acsm-paper">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-bold">{project.project_name}</div>
                        <div className="text-xs text-acsm-muted">{project.client_name}</div>
                      </div>
                      <span className={`rounded-full border px-2 py-1 text-xs font-bold ${healthStyle(project.health)}`}>{project.health_label}</span>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                      <div><span className="block text-acsm-muted">Presupuesto</span><strong>{amount(project.budget_amount)}</strong></div>
                      <div><span className="block text-acsm-muted">Recibido</span><strong>{percent(project.received_percent)}</strong></div>
                      <div><span className="block text-acsm-muted">Pagado</span><strong>{amount(project.paid_amount)}</strong></div>
                    </div>
                  </button>
                ))}
              </div>
              {!filteredProjects.length && <div className="px-4 py-10 text-center text-sm text-acsm-muted">No hay desarrollos que coincidan con los filtros.</div>}
            </section>

            <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
              <div className="flex items-center justify-between border-b border-acsm-line px-4 py-3">
                <div>
                  <h2 className="font-semibold text-acsm-ink">Atención ejecutiva</h2>
                  <p className="text-xs text-acsm-muted">Excepciones que requieren una decisión.</p>
                </div>
                <span className={data.alerts.length ? 'rounded-full bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800' : 'rounded-full bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-700'}>
                  {data.alerts.length}
                </span>
              </div>
              <div className="divide-y divide-acsm-line">
                {data.alerts.slice(0, 6).map((alert) => (
                  <button key={alert.key} type="button" onClick={() => navigate(alert.action_url)} className="flex w-full gap-3 px-4 py-3 text-left hover:bg-acsm-paper">
                    <AlertTriangle className={alert.priority === 'critical' ? 'mt-0.5 h-4 w-4 shrink-0 text-red-700' : 'mt-0.5 h-4 w-4 shrink-0 text-amber-700'} aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block text-sm font-bold text-acsm-ink">{alert.title}</span>
                      <span className="block text-xs font-semibold text-acsm-muted">{alert.project_name}</span>
                      <span className="mt-1 block text-xs leading-4 text-acsm-muted">{alert.detail}</span>
                    </span>
                  </button>
                ))}
                {!data.alerts.length && (
                  <div className="flex items-center gap-3 px-4 py-8">
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                    <div><div className="text-sm font-bold">Sin alertas críticas</div><div className="text-xs text-acsm-muted">El portafolio no presenta excepciones financieras.</div></div>
                  </div>
                )}
              </div>
            </section>
          </div>
        </>
      )}

      {selectedProjectId && selectedProject && data && (
        <>
          <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
              <div>
                <div className="text-xs font-semibold text-acsm-muted">{selectedProject.client_name}</div>
                <h2 className="text-lg font-bold">{selectedProject.project_name}</h2>
                <div className="text-xs text-acsm-muted">{quantity.format(selectedProject.houses_count)} viviendas · {selectedProject.models_count} modelos · {selectedProject.purchase_orders_count} órdenes</div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full border px-3 py-1 text-xs font-bold ${healthStyle(selectedProject.health)}`}>{selectedProject.health_label}</span>
                {!selectedProject.baseline_id && hasPermission('project_material_budgets:approve') && (
                  <button type="button" onClick={() => void approveBaseline()} disabled={approving} className="inline-flex h-9 items-center gap-2 rounded-md bg-acsm-green px-3 text-sm font-bold text-white disabled:opacity-60">
                    <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
                    {approving ? 'Aprobando...' : 'Aprobar línea base'}
                  </button>
                )}
              </div>
            </div>
            <div className="grid divide-y divide-acsm-line md:grid-cols-5 md:divide-x md:divide-y-0">
              {[
                { label: 'Presupuesto', value: amount(selectedProject.budget_amount), progress: 100, tone: 'blue' as const },
                { label: 'Comprometido', value: amount(selectedProject.committed_amount), progress: Number(selectedProject.committed_percent), tone: 'blue' as const },
                { label: 'Recibido', value: amount(selectedProject.received_amount), progress: Number(selectedProject.received_percent), tone: 'blue' as const },
                { label: 'Facturado', value: amount(selectedProject.invoiced_amount), progress: Number(selectedProject.invoiced_percent), tone: 'teal' as const },
                { label: 'Pagado', value: amount(selectedProject.paid_amount), progress: Number(selectedProject.paid_percent), tone: 'green' as const },
              ].map((stage) => (
                <div key={stage.label} className="px-4 py-3">
                  <div className="text-[10px] font-bold uppercase text-acsm-muted">{stage.label}</div>
                  <div className="my-1 text-base font-bold">{stage.value}</div>
                  <ProgressBar value={stage.progress} tone={stage.tone} />
                  <div className="mt-1 text-right text-xs text-acsm-muted">{percent(stage.progress)}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
            <div className="grid gap-2 border-b border-acsm-line px-4 py-3 md:grid-cols-[minmax(260px,1fr)_220px_auto]">
              <label className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-acsm-muted" aria-hidden="true" />
                <input value={materialSearch} onChange={(event) => setMaterialSearch(event.target.value)} placeholder="Buscar material, código o modelo" className="h-10 w-full rounded-md border border-acsm-line pl-9 pr-3 text-sm" />
              </label>
              <select value={materialStatus} onChange={(event) => setMaterialStatus(event.target.value)} className="h-10 rounded-md border border-acsm-line bg-white px-3 text-sm">
                <option value="all">Todos los estados</option>
                <option value="pending">Pendiente</option>
                <option value="partial">Parcial</option>
                <option value="complete">Completo</option>
                <option value="over_budget">Excedido</option>
              </select>
              <div className="flex items-center text-xs font-semibold text-acsm-muted">{filteredMaterials.length} materiales</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="bg-acsm-paper text-[10px] font-bold uppercase text-acsm-muted">
                  <tr>
                    <th className="px-4 py-2">Material</th><th className="px-3 py-2 text-right">Presupuesto</th><th className="px-3 py-2 text-right">Ordenado</th><th className="px-3 py-2 text-right">Recibido</th><th className="px-3 py-2 text-right">Facturado</th><th className="px-3 py-2 text-right">Pagado</th><th className="px-4 py-2">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-acsm-line">
                  {visibleMaterials.map((material) => (
                    <tr key={material.baseline_item_id} className="hover:bg-acsm-paper">
                      <td className="px-4 py-3"><div className="font-bold">{material.description}</div><div className="text-xs text-acsm-muted">{material.source_code ?? 'Sin código'} · {material.house_model_name} · {quantity.format(material.budget_quantity)} {material.unit}</div></td>
                      <td className="px-3 py-3 text-right font-semibold">{amount(material.budget_amount)}</td>
                      <td className="px-3 py-3 text-right">{amount(material.committed_amount)}</td>
                      <td className="px-3 py-3 text-right">{amount(material.received_amount)}</td>
                      <td className="px-3 py-3 text-right">{amount(material.invoiced_amount)}</td>
                      <td className="px-3 py-3 text-right">{amount(material.paid_amount)}</td>
                      <td className="px-4 py-3"><span className="rounded-full border border-acsm-line bg-white px-2 py-1 text-xs font-bold">{materialStatusLabel(material.status)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!visibleMaterials.length && <div className="px-4 py-10 text-center text-sm text-acsm-muted">No hay materiales que coincidan con los filtros.</div>}
            {filteredMaterials.length > 10 && (
              <div className="border-t border-acsm-line px-4 py-3 text-center">
                <button type="button" onClick={() => setShowAllMaterials((value) => !value)} className="text-sm font-bold text-acsm-green hover:underline">
                  {showAllMaterials ? 'Mostrar solo 10' : `Ver los ${filteredMaterials.length} materiales`}
                </button>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
