import { useEffect, useMemo, useState } from 'react'
import { Activity, Filter, RefreshCw, Search } from 'lucide-react'

import { apiRequest } from '../lib/api'

type AuditEvent = {
  id: number
  user_name?: string | null
  user_email?: string | null
  module: string
  action: string
  entity_type: string
  entity_id?: string | null
  entity_label?: string | null
  description: string
  event_metadata?: Record<string, unknown> | null
  created_at: string
}

type AuditEventResponse = {
  total: number
  items: AuditEvent[]
}

const moduleLabels: Record<string, string> = {
  compras: 'Compras',
  cotizaciones: 'Cotizaciones',
  desarrolladoras: 'Desarrolladoras',
  facturas_proveedor: 'Facturas proveedor',
  materiales: 'Materiales',
  modelos: 'Modelos',
  ordenes_compra: 'Ordenes de compra',
  pagos_proveedores: 'Pagos proveedores',
  proveedores: 'Proveedores',
}

const actionLabels: Record<string, string> = {
  approve: 'Aprobacion',
  create: 'Creacion',
  delete: 'Eliminacion',
  pay: 'Pago',
  schedule: 'Programacion',
  send: 'Envio',
  update: 'Edicion',
  upload: 'Carga',
  validate: 'Validacion',
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('es-MX', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function metadataSummary(metadata?: Record<string, unknown> | null) {
  if (!metadata) return 'Sin detalle adicional'
  if ('cambios' in metadata && metadata.cambios && typeof metadata.cambios === 'object') {
    const fields = Object.keys(metadata.cambios as Record<string, unknown>)
    return fields.length ? `Campos modificados: ${fields.join(', ')}` : 'Sin cambios detectados'
  }
  if ('registro' in metadata && metadata.registro && typeof metadata.registro === 'object') {
    const record = metadata.registro as Record<string, unknown>
    const main = record.name || record.title || record.quote_number || record.rfq_number || record.po_number
    return main ? `Registro: ${String(main)}` : 'Registro creado'
  }
  if ('registro_eliminado' in metadata) return 'Registro eliminado con respaldo de datos'
  return Object.entries(metadata)
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(' · ')
}

export default function EventsPage() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [total, setTotal] = useState(0)
  const [module, setModule] = useState('')
  const [action, setAction] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<AuditEvent | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: '100' })
    if (module) params.set('module', module)
    if (action) params.set('action', action)
    if (search.trim()) params.set('search', search.trim())
    return params.toString()
  }, [action, module, search])

  async function loadEvents() {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest<AuditEventResponse>(`/events?${query}`)
      setEvents(data.items)
      setTotal(data.total)
      setSelected((current) => {
        if (!current) return data.items[0] ?? null
        return data.items.find((event) => event.id === current.id) ?? data.items[0] ?? null
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar eventos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadEvents()
  }, [query])

  return (
    <div className="space-y-5">
      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      ) : null}

      <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-200 bg-blue-50 text-blue-700">
              <Activity className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">Auditoria</p>
              <h2 className="text-lg font-bold text-acsm-ink">Eventos del sistema</h2>
              <p className="text-sm text-acsm-muted">
                Bitacora de cambios relevantes en operacion, compras, costos y catalogos.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadEvents()}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink shadow-sm hover:bg-blue-50"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {loading ? 'Cargando...' : 'Actualizar'}
          </button>
        </div>

        <div className="grid gap-4 border-b border-acsm-line bg-slate-50/80 p-4 lg:grid-cols-[minmax(260px,1fr)_220px_220px]">
          <label className="text-sm font-semibold text-acsm-ink">
            <span className="mb-1 flex items-center gap-2">
              <Search className="h-4 w-4" aria-hidden="true" />
              Buscar
            </span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Usuario, registro o descripcion..."
              className="h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
            />
          </label>
          <label className="text-sm font-semibold text-acsm-ink">
            <span className="mb-1 flex items-center gap-2">
              <Filter className="h-4 w-4" aria-hidden="true" />
              Modulo
            </span>
            <select
              value={module}
              onChange={(event) => setModule(event.target.value)}
              className="h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
            >
              <option value="">Todos</option>
              {Object.entries(moduleLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold text-acsm-ink">
            Accion
            <select
              value={action}
              onChange={(event) => setAction(event.target.value)}
              className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
            >
              <option value="">Todas</option>
              {Object.entries(actionLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid min-h-[560px] lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="divide-y divide-acsm-line">
            <div className="flex items-center justify-between px-5 py-3 text-sm text-acsm-muted">
              <span>{total} eventos encontrados</span>
              <span>Mostrando {events.length}</span>
            </div>
            {events.map((event) => (
              <button
                type="button"
                key={event.id}
                onClick={() => setSelected(event)}
                className={[
                  'block w-full px-5 py-4 text-left transition',
                  selected?.id === event.id ? 'bg-blue-50' : 'bg-white hover:bg-slate-50',
                ].join(' ')}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-bold text-blue-800">
                        {moduleLabels[event.module] ?? event.module}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                        {actionLabels[event.action] ?? event.action}
                      </span>
                    </div>
                    <p className="mt-2 font-semibold text-acsm-ink">{event.description}</p>
                    <p className="mt-1 text-sm text-acsm-muted">
                      {event.entity_label ?? event.entity_type} · {metadataSummary(event.event_metadata)}
                    </p>
                  </div>
                  <div className="shrink-0 text-right text-xs text-acsm-muted">
                    <div>{formatDate(event.created_at)}</div>
                    <div className="mt-1 font-semibold">{event.user_name ?? event.user_email}</div>
                  </div>
                </div>
              </button>
            ))}
            {!events.length ? (
              <div className="px-5 py-16 text-center text-sm text-acsm-muted">
                No hay eventos con los filtros actuales.
              </div>
            ) : null}
          </div>

          <aside className="border-t border-acsm-line bg-slate-50/80 p-5 lg:border-l lg:border-t-0">
            <h3 className="text-base font-bold text-acsm-ink">Detalle del evento</h3>
            {selected ? (
              <div className="mt-4 space-y-4">
                <dl className="grid gap-3 text-sm">
                  <div className="rounded-xl border border-acsm-line bg-white p-3">
                    <dt className="text-xs font-bold uppercase text-acsm-muted">Fecha</dt>
                    <dd className="mt-1 font-semibold">{formatDate(selected.created_at)}</dd>
                  </div>
                  <div className="rounded-xl border border-acsm-line bg-white p-3">
                    <dt className="text-xs font-bold uppercase text-acsm-muted">Usuario</dt>
                    <dd className="mt-1 font-semibold">{selected.user_name ?? 'Sin nombre'}</dd>
                    <dd className="text-acsm-muted">{selected.user_email}</dd>
                  </div>
                  <div className="rounded-xl border border-acsm-line bg-white p-3">
                    <dt className="text-xs font-bold uppercase text-acsm-muted">Registro afectado</dt>
                    <dd className="mt-1 font-semibold">{selected.entity_label ?? selected.entity_type}</dd>
                    <dd className="text-acsm-muted">
                      {selected.entity_type} {selected.entity_id ? `#${selected.entity_id}` : ''}
                    </dd>
                  </div>
                </dl>
                <div className="rounded-xl border border-acsm-line bg-white p-3">
                  <div className="text-xs font-bold uppercase text-acsm-muted">Detalle tecnico</div>
                  <pre className="mt-2 max-h-[320px] overflow-auto whitespace-pre-wrap break-words text-xs text-acsm-ink">
                    {JSON.stringify(selected.event_metadata ?? {}, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-acsm-muted">Selecciona un evento para ver su detalle.</p>
            )}
          </aside>
        </div>
      </section>
    </div>
  )
}
