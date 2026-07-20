import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  Box,
  CheckCircle2,
  Clock3,
  PackageCheck,
  RefreshCw,
  Search,
  Truck,
  Warehouse,
} from 'lucide-react'

import { apiRequest } from '../lib/api'

type InboundItem = {
  expected_item_id: number
  description: string
  unit: string
  house_model_id?: number | null
  house_model_name?: string | null
  expected_quantity: string
  accepted_quantity: string
  pending_quantity: string
  status: string
}

type InboundCase = {
  id: number
  expected_list_id: number
  purchase_order_id: number
  purchase_order_number: string
  purchase_order_status: string
  project_id: number
  project_name: string
  warehouse_id?: number | null
  warehouse_name?: string | null
  supplier_id: number
  supplier_name: string
  issued_at: string
  expected_delivery_date?: string | null
  stage: 'awaiting' | 'partial' | 'issue' | 'complete'
  item_count: number
  completed_item_count: number
  pending_item_count: number
  issue_item_count: number
  line_progress_percent: string
  next_action_label: string
  next_action_url: string
  items: InboundItem[]
}

const stageLabels = {
  awaiting: 'Por recibir',
  partial: 'Recepcion parcial',
  issue: 'Con incidencia',
  complete: 'Completada',
}

const stageOptions = [
  ['all', 'Todos'],
  ['awaiting', 'Por recibir'],
  ['partial', 'Parciales'],
  ['issue', 'Incidencias'],
  ['complete', 'Completadas'],
]

function formatDate(value?: string | null) {
  if (!value) return 'Sin fecha definida'
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(
    new Date(`${value.slice(0, 10)}T12:00:00`),
  )
}

function quantity(value: string | number) {
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 4 }).format(Number(value || 0))
}

function stageClasses(stage: InboundCase['stage']) {
  if (stage === 'complete') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (stage === 'issue') return 'border-amber-300 bg-amber-50 text-amber-900'
  if (stage === 'partial') return 'border-cyan-200 bg-cyan-50 text-cyan-900'
  return 'border-sky-200 bg-sky-50 text-sky-900'
}

function StageIcon({ stage }: { stage: InboundCase['stage'] }) {
  const Icon = stage === 'complete' ? CheckCircle2 : stage === 'issue' ? AlertTriangle : stage === 'partial' ? PackageCheck : Truck
  return <Icon className="h-4 w-4" aria-hidden="true" />
}

export default function InventoryWorkspacePage() {
  const navigate = useNavigate()
  const params = useParams<{ caseId?: string }>()
  const [cases, setCases] = useState<InboundCase[]>([])
  const [search, setSearch] = useState('')
  const [stageFilter, setStageFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const detailRef = useRef<HTMLElement>(null)

  const routeCaseId = Number(params.caseId || 0)
  const selectedCase = useMemo(
    () => cases.find((item) => item.id === routeCaseId) ?? (routeCaseId ? null : cases[0] ?? null),
    [cases, routeCaseId],
  )

  const loadCases = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setCases(await apiRequest<InboundCase[]>('/inventory/inbound-cases?include_complete=true&limit=250'))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar Inventarios')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCases()
  }, [loadCases])

  useEffect(() => {
    if (!routeCaseId || !selectedCase || window.matchMedia('(min-width: 1280px)').matches) return
    window.requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }, [routeCaseId, selectedCase?.id])

  const filteredCases = useMemo(() => {
    const value = search.trim().toLocaleLowerCase()
    return cases.filter((item) => {
      if (stageFilter !== 'all' && item.stage !== stageFilter) return false
      if (!value) return true
      return [item.purchase_order_number, item.project_name, item.supplier_name, item.warehouse_name]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase()
        .includes(value)
    })
  }, [cases, search, stageFilter])

  const counters = useMemo(
    () => ({
      awaiting: cases.filter((item) => item.stage === 'awaiting').length,
      partial: cases.filter((item) => item.stage === 'partial').length,
      issue: cases.filter((item) => item.stage === 'issue').length,
      complete: cases.filter((item) => item.stage === 'complete').length,
    }),
    [cases],
  )

  function selectCase(item: InboundCase) {
    navigate(`/inventory/cases/${item.id}`)
  }

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-lg border border-acsm-line bg-white shadow-panel">
        <header className="flex flex-col gap-4 border-b border-acsm-line bg-acsm-paper/70 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-sky-200 bg-sky-50 text-sky-700">
              <Warehouse className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-widest text-acsm-muted">Operacion de inventarios</p>
              <h1 className="text-xl font-black text-acsm-ink">Centro de Inventarios</h1>
              <p className="text-sm text-acsm-muted">Controla lo esperado, lo aceptado y lo pendiente por orden de compra.</p>
            </div>
          </div>
          <button type="button" onClick={() => void loadCases()} className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Actualizar
          </button>
        </header>

        <div className="grid grid-cols-2 border-b border-acsm-line md:grid-cols-4">
          {([
            ['awaiting', 'Por recibir', counters.awaiting],
            ['partial', 'Parciales', counters.partial],
            ['issue', 'Incidencias', counters.issue],
            ['complete', 'Completadas', counters.complete],
          ] as const).map(([key, label, value]) => (
            <button key={key} type="button" onClick={() => setStageFilter(key)} className={`min-h-20 border-r border-acsm-line px-4 py-3 text-left last:border-r-0 hover:bg-acsm-paper ${stageFilter === key ? 'bg-sky-50' : 'bg-white'}`}>
              <span className="block text-xs font-bold uppercase text-acsm-muted">{label}</span>
              <span className="mt-1 block text-2xl font-black text-acsm-ink">{value}</span>
            </button>
          ))}
        </div>

        {error ? <div className="border-b border-red-200 bg-red-50 px-5 py-3 text-sm font-semibold text-red-800">{error}</div> : null}

        <div className="grid min-h-[620px] xl:grid-cols-[330px_minmax(0,1fr)]">
          <aside className="border-b border-acsm-line xl:border-b-0 xl:border-r">
            <div className="space-y-3 border-b border-acsm-line p-4">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-acsm-muted" aria-hidden="true" />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="OC, proveedor, desarrollo o bodega" className="h-10 w-full rounded-md border border-acsm-line bg-white pl-9 pr-3 text-sm" />
              </label>
              <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)} className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold">
                {stageOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            <div className="max-h-[720px] overflow-y-auto p-2">
              {filteredCases.map((item) => (
                <button key={item.id} type="button" onClick={() => selectCase(item)} className={`mb-2 w-full rounded-md border p-3 text-left transition ${selectedCase?.id === item.id ? 'border-sky-500 bg-sky-50 shadow-sm' : 'border-acsm-line bg-white hover:border-sky-300 hover:bg-acsm-paper'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-black text-acsm-ink">{item.purchase_order_number}</div>
                      <div className="mt-0.5 truncate text-sm text-acsm-muted">{item.supplier_name}</div>
                    </div>
                    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-bold ${stageClasses(item.stage)}`}>
                      <StageIcon stage={item.stage} />
                      {stageLabels[item.stage]}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3 text-xs text-acsm-muted">
                    <span className="truncate">{item.project_name}</span>
                    <strong className="shrink-0 text-acsm-ink">{quantity(item.line_progress_percent)}%</strong>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200">
                    <span className="block h-full bg-sky-600" style={{ width: `${Math.min(Number(item.line_progress_percent), 100)}%` }} />
                  </div>
                </button>
              ))}
              {!loading && !filteredCases.length ? <div className="px-4 py-12 text-center text-sm text-acsm-muted">No hay entradas con estos filtros.</div> : null}
            </div>
          </aside>

          <main ref={detailRef} className="min-w-0 scroll-mt-20">
            {selectedCase ? (
              <>
                <header className="border-b border-acsm-line px-5 py-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-xl font-black text-acsm-ink">{selectedCase.purchase_order_number}</h2>
                        <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-bold ${stageClasses(selectedCase.stage)}`}><StageIcon stage={selectedCase.stage} />{stageLabels[selectedCase.stage]}</span>
                      </div>
                      <p className="mt-1 text-sm text-acsm-muted">{selectedCase.supplier_name} · {selectedCase.project_name}</p>
                    </div>
                    <button type="button" onClick={() => navigate(selectedCase.next_action_url)} className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-bold text-white hover:bg-acsm-green-hover">
                      {selectedCase.next_action_label}
                      <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </header>

                <div className="grid border-b border-acsm-line sm:grid-cols-2 lg:grid-cols-4">
                  <div className="border-b border-r border-acsm-line p-4 sm:border-b-0"><span className="text-xs font-bold uppercase text-acsm-muted">Entrega esperada</span><strong className="mt-1 block text-sm text-acsm-ink">{formatDate(selectedCase.expected_delivery_date)}</strong></div>
                  <div className="border-b border-acsm-line p-4 lg:border-b-0 lg:border-r"><span className="text-xs font-bold uppercase text-acsm-muted">Bodega</span><strong className="mt-1 block text-sm text-acsm-ink">{selectedCase.warehouse_name || 'Por asignar'}</strong></div>
                  <div className="border-r border-acsm-line p-4"><span className="text-xs font-bold uppercase text-acsm-muted">Partidas completas</span><strong className="mt-1 block text-sm text-acsm-ink">{selectedCase.completed_item_count} de {selectedCase.item_count}</strong></div>
                  <div className="p-4"><span className="text-xs font-bold uppercase text-acsm-muted">Incidencias</span><strong className={`mt-1 block text-sm ${selectedCase.issue_item_count ? 'text-amber-800' : 'text-acsm-ink'}`}>{selectedCase.issue_item_count}</strong></div>
                </div>

                <section className="p-4 sm:p-5">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <h3 className="font-black text-acsm-ink">Material esperado</h3>
                      <p className="text-xs text-acsm-muted">El avance solo considera material aceptado en bodega.</p>
                    </div>
                    <span className="text-sm font-black text-sky-800">{quantity(selectedCase.line_progress_percent)}%</span>
                  </div>
                  <div className="overflow-hidden rounded-md border border-acsm-line">
                    <div className="hidden grid-cols-[minmax(150px,1fr)_90px_90px_90px_95px] bg-acsm-paper px-3 py-2 text-[11px] font-bold uppercase text-acsm-muted md:grid">
                      <span>Material</span><span>Ordenado</span><span>Aceptado</span><span>Pendiente</span><span>Estado</span>
                    </div>
                    {selectedCase.items.map((item) => (
                      <div key={item.expected_item_id} className="grid gap-3 border-t border-acsm-line p-3 first:border-t-0 md:grid-cols-[minmax(150px,1fr)_90px_90px_90px_95px] md:items-center">
                        <div className="min-w-0"><strong className="block truncate text-sm text-acsm-ink">{item.description}</strong><span className="text-xs text-acsm-muted">{item.house_model_name || 'Sin modelo asignado'}</span></div>
                        <div><span className="text-[11px] font-bold uppercase text-acsm-muted md:hidden">Ordenado </span><span className="text-sm font-semibold">{quantity(item.expected_quantity)} {item.unit}</span></div>
                        <div><span className="text-[11px] font-bold uppercase text-acsm-muted md:hidden">Aceptado </span><span className="text-sm font-semibold text-emerald-800">{quantity(item.accepted_quantity)} {item.unit}</span></div>
                        <div><span className="text-[11px] font-bold uppercase text-acsm-muted md:hidden">Pendiente </span><span className="text-sm font-semibold text-acsm-ink">{quantity(item.pending_quantity)} {item.unit}</span></div>
                        <span className={`w-fit rounded-full border px-2 py-1 text-xs font-bold ${item.status === 'complete' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : item.status === 'with_issue' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-sky-200 bg-sky-50 text-sky-800'}`}>{item.status === 'complete' ? 'Completo' : item.status === 'with_issue' ? 'Revisar' : item.status === 'partial' ? 'Parcial' : 'Pendiente'}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <footer className="flex flex-col gap-3 border-t border-acsm-line bg-acsm-paper/50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2 text-sm text-acsm-muted"><Clock3 className="h-4 w-4" /><span>Siguiente paso: <strong className="text-acsm-ink">{selectedCase.next_action_label}</strong></span></div>
                  <button type="button" onClick={() => navigate(selectedCase.next_action_url)} className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-sky-300 bg-white px-4 text-sm font-bold text-sky-800 hover:bg-sky-50">Abrir recepcion <ArrowRight className="h-4 w-4" /></button>
                </footer>
              </>
            ) : loading ? (
              <div className="flex min-h-[620px] flex-col items-center justify-center text-center"><RefreshCw className="h-8 w-8 animate-spin text-sky-600" /><p className="mt-4 font-bold text-acsm-ink">Cargando entradas de inventario</p></div>
            ) : (
              <div className="flex min-h-[620px] flex-col items-center justify-center px-6 text-center"><Box className="h-10 w-10 text-sky-300" /><h2 className="mt-4 text-lg font-black text-acsm-ink">Sin material esperado</h2><p className="mt-1 max-w-md text-sm text-acsm-muted">Las ordenes enviadas al proveedor apareceran aqui para coordinar su recepcion.</p></div>
            )}
          </main>
        </div>
      </section>
    </div>
  )
}
