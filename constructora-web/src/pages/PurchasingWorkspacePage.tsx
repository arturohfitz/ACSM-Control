import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertCircle,
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock3,
  FileCheck2,
  FileText,
  PackageCheck,
  RefreshCw,
  Search,
  Send,
  ShoppingCart,
  Truck,
  Users,
  WalletCards,
} from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { apiRequest } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'

type PurchaseCaseStep = {
  key: string
  label: string
  status: 'complete' | 'current' | 'pending' | 'attention'
  detail: string
}

type PurchaseCase = {
  id: number
  rfq_id: number
  rfq_number: string
  title: string
  status: string
  project_id: number
  project_name: string
  requisition_id?: number | null
  requisition_number?: string | null
  owner_name?: string | null
  required_by?: string | null
  response_deadline?: string | null
  supplier_count: number
  item_count: number
  upload_count: number
  quote_count: number
  complete_quote_count: number
  required_quote_count: number
  approval_status?: string | null
  approved_supplier_name?: string | null
  approved_total?: string | null
  purchase_order_id?: number | null
  purchase_order_number?: string | null
  purchase_order_status?: string | null
  current_stage: string
  current_stage_label: string
  next_action_label: string
  next_action_url: string
  needs_attention: boolean
  steps: PurchaseCaseStep[]
  created_at: string
  updated_at: string
}

type MaterialRequisition = {
  id: number
  requisition_number: string
  title: string
  status: string
  project_id: number
  required_date?: string | null
  converted_rfq_id?: number | null
  items: unknown[]
}

type SupplierRFQItem = {
  id: number
  source_code?: string | null
  description: string
  unit: string
  quantity: string
}

type SupplierRFQ = {
  id: number
  items: SupplierRFQItem[]
}

type PurchaseOrder = {
  id: number
  po_number: string
  status: string
}

const stageIcons: Record<string, typeof ClipboardList> = {
  origin: ClipboardList,
  providers: Users,
  documents: FileText,
  capture: FileCheck2,
  comparison: ShoppingCart,
  approval: CheckCircle2,
  order: Send,
  receiving: Truck,
  payment: WalletCards,
}

const stageOptions = [
  ['all', 'Todas las etapas'],
  ['documents', 'Esperando proveedor'],
  ['capture', 'Captura de cotizaciones'],
  ['comparison', 'Comparativo'],
  ['approval', 'Aprobacion'],
  ['order', 'Orden de compra'],
  ['receiving', 'Recepcion'],
  ['payment', 'Pago'],
  ['closed', 'Concluidos'],
]

const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' })

function formatDate(value?: string | null) {
  if (!value) return 'Sin fecha'
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(new Date(`${value.slice(0, 10)}T12:00:00`))
}

function stageTone(stage: string, attention = false) {
  if (attention) return 'border-amber-300 bg-amber-50 text-amber-800'
  if (stage === 'closed') return 'border-emerald-300 bg-emerald-50 text-emerald-800'
  if (stage === 'approval') return 'border-violet-300 bg-violet-50 text-violet-800'
  if (stage === 'order') return 'border-cyan-300 bg-cyan-50 text-cyan-800'
  return 'border-sky-300 bg-sky-50 text-sky-800'
}

export default function PurchasingWorkspacePage() {
  const navigate = useNavigate()
  const params = useParams<{ caseId?: string }>()
  const { hasPermission } = useAuth()
  const [cases, setCases] = useState<PurchaseCase[]>([])
  const [requisitions, setRequisitions] = useState<MaterialRequisition[]>([])
  const [rfqDetail, setRfqDetail] = useState<SupplierRFQ | null>(null)
  const [search, setSearch] = useState('')
  const [stageFilter, setStageFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState('')
  const caseDetailRef = useRef<HTMLElement>(null)

  const routeCaseId = Number(params.caseId || 0)
  const selectedCase = useMemo(
    () => cases.find((item) => item.id === routeCaseId) ?? (routeCaseId ? null : cases[0] ?? null),
    [cases, routeCaseId],
  )

  const loadWorkspace = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [caseRows, requisitionRows] = await Promise.all([
        apiRequest<PurchaseCase[]>('/purchasing/purchase-cases?limit=250'),
        apiRequest<MaterialRequisition[]>('/material-requisitions?limit=250'),
      ])
      setCases(caseRows)
      setRequisitions(requisitionRows)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar la bandeja de Compras')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadWorkspace()
  }, [loadWorkspace])

  useEffect(() => {
    if (!selectedCase) {
      setRfqDetail(null)
      return
    }
    apiRequest<SupplierRFQ>(`/purchasing/supplier-rfqs/${selectedCase.rfq_id}`)
      .then(setRfqDetail)
      .catch(() => setRfqDetail(null))
  }, [selectedCase?.rfq_id])

  useEffect(() => {
    if (!routeCaseId || !selectedCase || window.matchMedia('(min-width: 1280px)').matches) return
    window.requestAnimationFrame(() => {
      caseDetailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }, [routeCaseId, selectedCase?.id])

  const pendingRequisitions = useMemo(
    () => requisitions.filter((item) => !item.converted_rfq_id && ['submitted', 'in_review', 'approved'].includes(item.status)),
    [requisitions],
  )

  const filteredCases = useMemo(() => {
    const normalized = search.trim().toLocaleLowerCase()
    return cases.filter((item) => {
      if (stageFilter !== 'all' && item.current_stage !== stageFilter) return false
      if (!normalized) return true
      return [
        item.rfq_number,
        item.title,
        item.project_name,
        item.requisition_number,
        item.approved_supplier_name,
        item.purchase_order_number,
      ]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase()
        .includes(normalized)
    })
  }, [cases, search, stageFilter])

  const counters = useMemo(
    () => ({
      action: cases.filter((item) => !['approval', 'receiving', 'payment', 'closed', 'cancelled'].includes(item.current_stage)).length + pendingRequisitions.length,
      approval: cases.filter((item) => item.current_stage === 'approval').length,
      order: cases.filter((item) => item.current_stage === 'order').length,
      attention: cases.filter((item) => item.needs_attention).length,
    }),
    [cases, pendingRequisitions.length],
  )

  async function executePrimaryAction() {
    if (!selectedCase) return
    setActionLoading(true)
    setError('')
    try {
      if (selectedCase.current_stage === 'order' && !selectedCase.purchase_order_id) {
        const order = await apiRequest<PurchaseOrder>(
          `/purchasing/supplier-rfqs/${selectedCase.rfq_id}/purchase-order`,
          { method: 'POST' },
        )
        showActionNotice(`Orden ${order.po_number} preparada. Revisa y confirma su envio al proveedor.`)
        await loadWorkspace()
        return
      }
      if (selectedCase.purchase_order_id && selectedCase.purchase_order_status === 'issued') {
        const order = await apiRequest<PurchaseOrder>(
          `/purchasing/purchase-orders/${selectedCase.purchase_order_id}/send`,
          { method: 'POST' },
        )
        showActionNotice(`Orden ${order.po_number} enviada. Inventario ya tiene el material esperado.`)
        await loadWorkspace()
        return
      }
      navigate(selectedCase.next_action_url)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'No fue posible completar la accion'
      setError(message)
      showActionNotice(message, 'error')
    } finally {
      setActionLoading(false)
    }
  }

  function primaryActionLabel() {
    if (!selectedCase) return ''
    if (selectedCase.current_stage === 'order' && !selectedCase.purchase_order_id) return 'Generar orden de compra'
    if (selectedCase.purchase_order_status === 'issued') return 'Enviar OC al proveedor'
    return selectedCase.next_action_label
  }

  return (
    <div className="space-y-4 pb-8">
      <section className="overflow-hidden rounded-lg border border-sky-200 bg-[#f6faff] shadow-[0_18px_42px_rgba(2,18,38,0.20)]">
        <div className="flex flex-col gap-4 border-b border-sky-200 bg-[#e7f1f9] px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-sky-300 bg-white text-sky-700">
              <ShoppingCart className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Centro de operacion</p>
              <h2 className="text-lg font-black text-slate-900">Bandeja de compras</h2>
              <p className="mt-0.5 text-sm text-slate-600">Cada solicitud conserva su origen, etapa actual y siguiente accion.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadWorkspace()}
            disabled={loading}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-sky-300 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-sky-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Actualizar
          </button>
        </div>
        <div className="grid grid-cols-2 divide-x divide-y divide-sky-200 bg-white md:grid-cols-4 md:divide-y-0">
          {[
            { label: 'Por atender', value: counters.action, icon: ClipboardList, color: 'text-sky-700' },
            { label: 'En aprobacion', value: counters.approval, icon: Clock3, color: 'text-violet-700' },
            { label: 'OC por preparar', value: counters.order, icon: Send, color: 'text-cyan-700' },
            { label: 'Con alerta', value: counters.attention, icon: AlertCircle, color: 'text-amber-700' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="flex items-center gap-3 px-4 py-3">
              <Icon className={`h-5 w-5 ${color}`} aria-hidden="true" />
              <div>
                <p className="text-[10px] font-black uppercase text-slate-500">{label}</p>
                <p className="text-xl font-black text-slate-900">{value}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {error ? (
        <div className="flex items-center gap-2 rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
      ) : null}

      {pendingRequisitions.length ? (
        <section className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <ClipboardList className="h-5 w-5 text-amber-700" aria-hidden="true" />
            <div>
              <p className="font-black text-slate-900">{pendingRequisitions.length} requerimiento(s) de Obra por convertir</p>
              <p className="text-xs text-slate-600">Todavia no forman un expediente de cotizacion.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/purchasing/operations?focus=requisitions')}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-amber-700 px-4 text-sm font-bold text-white hover:bg-amber-800"
          >
            Revisar entrada de Obra
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </section>
      ) : null}

      <div className="grid min-h-[620px] gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-lg border border-sky-200 bg-[#f6faff]">
          <div className="space-y-3 border-b border-sky-200 bg-[#e7f1f9] p-3">
            <div>
              <h2 className="font-black text-slate-900">Expedientes activos</h2>
              <p className="text-xs text-slate-600">Ordenados por ultima actividad.</p>
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Folio, proyecto o proveedor"
                className="h-10 w-full rounded-lg border border-sky-200 pl-9 pr-3 text-sm"
              />
            </div>
            <select
              value={stageFilter}
              onChange={(event) => setStageFilter(event.target.value)}
              className="h-10 w-full rounded-lg border border-sky-200 px-3 text-sm font-semibold text-slate-700"
            >
              {stageOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="max-h-[680px] space-y-2 overflow-y-auto p-3 scrollbar-thin">
            {filteredCases.map((item) => {
              const isSelected = selectedCase?.id === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => navigate(`/purchasing/cases/${item.id}`)}
                  className={`w-full rounded-lg border p-3 text-left transition ${
                    isSelected
                      ? 'border-sky-500 bg-white shadow-[inset_4px_0_0_#0284c7,0_8px_18px_rgba(14,116,144,0.12)]'
                      : 'border-sky-200 bg-white/70 hover:border-sky-400 hover:bg-white'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-black text-slate-900">{item.title}</p>
                      <p className="mt-0.5 text-[11px] font-bold text-sky-700">{item.rfq_number}</p>
                    </div>
                    {item.needs_attention ? <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" aria-hidden="true" /> : null}
                  </div>
                  <p className="mt-2 truncate text-xs text-slate-600">{item.project_name}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className={`rounded-md border px-2 py-1 text-[10px] font-black ${stageTone(item.current_stage, item.needs_attention)}`}>
                      {item.current_stage_label}
                    </span>
                    <span className="text-[10px] font-bold text-slate-500">{item.item_count} partidas</span>
                  </div>
                </button>
              )
            })}
            {!loading && !filteredCases.length ? (
              <div className="px-4 py-10 text-center text-sm text-slate-500">No hay expedientes con estos filtros.</div>
            ) : null}
          </div>
        </aside>

        <main ref={caseDetailRef} className="min-w-0 scroll-mt-20 overflow-hidden rounded-lg border border-sky-200 bg-[#f8fbfe]">
          {selectedCase ? (
            <>
              <header className="border-b border-sky-200 bg-[#e7f1f9] px-4 py-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-black uppercase tracking-[0.16em] text-sky-700">{selectedCase.rfq_number}</span>
                      <span className={`rounded-md border px-2 py-1 text-[10px] font-black ${stageTone(selectedCase.current_stage, selectedCase.needs_attention)}`}>
                        {selectedCase.current_stage_label}
                      </span>
                    </div>
                    <h2 className="mt-2 text-xl font-black text-slate-900">{selectedCase.title}</h2>
                    <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
                      <span className="inline-flex items-center gap-1.5"><Building2 className="h-3.5 w-3.5" />{selectedCase.project_name}</span>
                      <span>Origen: {selectedCase.requisition_number ?? 'Compra directa'}</span>
                      <span>Responsable: {selectedCase.owner_name ?? 'Sin asignar'}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void executePrimaryAction()}
                    disabled={actionLoading || (selectedCase.current_stage === 'order' && !hasPermission('purchase_orders:send'))}
                    className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-acsm-green px-5 text-sm font-black text-white hover:bg-acsm-green-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {selectedCase.purchase_order_status === 'issued' ? <Send className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                    {actionLoading ? 'Procesando...' : primaryActionLabel()}
                  </button>
                </div>
              </header>

              <section className="border-b border-sky-200 bg-white px-4 py-4">
                <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9">
                  {selectedCase.steps.map((step, index) => {
                    const Icon = stageIcons[step.key] ?? Clock3
                    return (
                      <div key={step.key} className="relative min-w-0">
                        <div className={`flex min-h-[78px] flex-col rounded-lg border p-2 ${
                          step.status === 'complete'
                            ? 'border-emerald-200 bg-emerald-50'
                            : step.status === 'current'
                              ? 'border-sky-400 bg-sky-50 shadow-[inset_0_0_0_1px_#38bdf8]'
                              : step.status === 'attention'
                                ? 'border-amber-300 bg-amber-50'
                                : 'border-slate-200 bg-slate-50 text-slate-400'
                        }`}>
                          <div className="flex items-center justify-between gap-1">
                            <span className="text-[9px] font-black text-slate-500">{String(index + 1).padStart(2, '0')}</span>
                            {step.status === 'complete' ? <Check className="h-3.5 w-3.5 text-emerald-700" /> : <Icon className="h-3.5 w-3.5" />}
                          </div>
                          <p className="mt-2 text-[10px] font-black leading-tight text-slate-800">{step.label}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>

              <section className="grid border-b border-sky-200 bg-[#f0f7fc] md:grid-cols-2 xl:grid-cols-4">
                {[
                  ['Proveedores', `${selectedCase.supplier_count}`, `${selectedCase.upload_count} documento(s)`],
                  ['Cotizaciones', `${selectedCase.complete_quote_count}/${selectedCase.required_quote_count}`, 'completas para comparar'],
                  ['Proveedor aprobado', selectedCase.approved_supplier_name ?? 'Pendiente', selectedCase.approved_total ? money.format(Number(selectedCase.approved_total)) : 'Sin monto aprobado'],
                  ['Orden de compra', selectedCase.purchase_order_number ?? 'Pendiente', selectedCase.purchase_order_status ?? 'Aun no generada'],
                ].map(([label, value, detail]) => (
                  <div key={label} className="border-b border-sky-200 px-4 py-3 last:border-b-0 md:border-r xl:border-b-0">
                    <p className="text-[10px] font-black uppercase text-slate-500">{label}</p>
                    <p className="mt-1 truncate text-base font-black text-slate-900">{value}</p>
                    <p className="mt-0.5 text-xs text-slate-500">{detail}</p>
                  </div>
                ))}
              </section>

              <section className="p-4">
                <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Alcance del expediente</p>
                    <h3 className="text-base font-black text-slate-900">Materiales solicitados</h3>
                  </div>
                  <div className="flex gap-4 text-xs text-slate-600">
                    <span>Requerido: <strong>{formatDate(selectedCase.required_by)}</strong></span>
                    <span>Respuesta: <strong>{formatDate(selectedCase.response_deadline)}</strong></span>
                  </div>
                </div>
                <div className="overflow-x-auto rounded-lg border border-sky-200 bg-white">
                  <table className="w-full min-w-[680px] text-left text-sm">
                    <thead className="bg-[#dcebf6] text-[10px] font-black uppercase text-slate-600">
                      <tr>
                        <th className="px-3 py-2.5">Codigo</th>
                        <th className="px-3 py-2.5">Material</th>
                        <th className="px-3 py-2.5 text-right">Cantidad</th>
                        <th className="px-3 py-2.5">Unidad</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-sky-100">
                      {(rfqDetail?.items ?? []).map((item) => (
                        <tr key={item.id} className="hover:bg-sky-50/70">
                          <td className="px-3 py-2.5 text-xs font-bold text-slate-500">{item.source_code ?? '-'}</td>
                          <td className="px-3 py-2.5 font-semibold text-slate-800">{item.description}</td>
                          <td className="px-3 py-2.5 text-right font-black text-slate-900">{Number(item.quantity).toLocaleString('es-MX')}</td>
                          <td className="px-3 py-2.5 text-xs font-bold text-slate-600">{item.unit}</td>
                        </tr>
                      ))}
                      {!rfqDetail?.items?.length ? (
                        <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-500">Cargando partidas del expediente...</td></tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </section>

              <footer className="flex flex-col gap-3 border-t border-sky-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <PackageCheck className="h-4 w-4 text-sky-700" aria-hidden="true" />
                  Ultima actividad: {formatDate(selectedCase.updated_at)}
                </div>
                <button
                  type="button"
                  onClick={() => navigate(`/purchasing/operations?rfq_id=${selectedCase.rfq_id}`)}
                  className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-sky-300 bg-white px-4 text-sm font-bold text-sky-800 hover:bg-sky-50"
                >
                  Abrir operacion completa
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </button>
              </footer>
            </>
          ) : loading ? (
            <div className="flex min-h-[620px] flex-col items-center justify-center px-6 text-center">
              <RefreshCw className="h-8 w-8 animate-spin text-sky-600" aria-hidden="true" />
              <h2 className="mt-4 text-base font-black text-slate-800">Cargando expedientes</h2>
              <p className="mt-1 text-sm text-slate-500">Consultando la etapa actual de cada compra.</p>
            </div>
          ) : (
            <div className="flex min-h-[620px] flex-col items-center justify-center px-6 text-center">
              <ShoppingCart className="h-10 w-10 text-sky-300" aria-hidden="true" />
              <h2 className="mt-4 text-lg font-black text-slate-800">Sin expedientes de compra</h2>
              <p className="mt-1 max-w-md text-sm text-slate-500">Los requerimientos de Obra apareceran aqui al convertirse en solicitudes de cotizacion.</p>
              <button
                type="button"
                onClick={() => navigate('/purchasing/operations')}
                className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-acsm-green px-4 text-sm font-bold text-white"
              >
                Iniciar una solicitud
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
