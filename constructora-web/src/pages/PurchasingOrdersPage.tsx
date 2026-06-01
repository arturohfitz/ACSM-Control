import { useEffect, useMemo, useState } from 'react'
import { Eye, FileText, Printer, RefreshCw, Search, Send, X } from 'lucide-react'

import { apiRequest } from '../lib/api'

type Supplier = {
  id: number
  name: string
  legal_name?: string | null
  tax_id?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  address?: string | null
  payment_terms_days: number
  average_delivery_days?: number | null
  material_categories?: string | null
}

type PurchaseOrderItem = {
  id: number
  description: string
  unit: string
  quantity_ordered: string
  unit_price: string
  line_total: string
  received_quantity: string
  status: string
  notes?: string | null
}

type PurchaseOrder = {
  id: number
  po_number: string
  status: string
  issued_at: string
  created_at?: string
  expected_delivery_date?: string | null
  payment_terms_days: number
  subtotal: string
  notes?: string | null
  supplier_id: number
  supplier?: Supplier | null
  items: PurchaseOrderItem[]
}

const money = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
})

function formatMoney(value: string | number) {
  return money.format(Number(value || 0))
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(new Date(value))
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    issued: 'Emitida',
    sent: 'Enviada',
    partially_received: 'Parcial recibida',
    received: 'Recibida',
    factured: 'Facturada',
    closed: 'Cerrada',
    cancelled: 'Cancelada',
  }
  return labels[status] ?? status
}

function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function orderProgress(order: PurchaseOrder) {
  const received = order.items.reduce((sum, item) => sum + Number(item.received_quantity || 0), 0)
  const total = order.items.reduce((sum, item) => sum + Number(item.quantity_ordered || 0), 0)
  const pending = Math.max(total - received, 0)
  const percent = total > 0 ? Math.min(100, Math.round((received / total) * 100)) : 0
  return { received, total, pending, percent }
}

function printOrder(order: PurchaseOrder) {
  const popup = window.open('', '_blank', 'width=980,height=760')
  if (!popup) return
  const items = order.items
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.description)}</td>
          <td>${escapeHtml(Number(item.quantity_ordered).toLocaleString('es-MX'))}</td>
          <td>${escapeHtml(item.unit)}</td>
          <td>${escapeHtml(formatMoney(item.unit_price))}</td>
          <td>${escapeHtml(formatMoney(item.line_total))}</td>
          <td>${escapeHtml(Number(item.received_quantity).toLocaleString('es-MX'))}</td>
        </tr>
      `,
    )
    .join('')

  popup.document.write(`
    <!doctype html>
    <html>
      <head>
        <title>${escapeHtml(order.po_number)}</title>
        <style>
          body { font-family: Arial, sans-serif; color: #0f172a; margin: 32px; }
          header { border-bottom: 2px solid #0b5f99; padding-bottom: 16px; margin-bottom: 22px; }
          h1 { margin: 0; font-size: 24px; }
          .muted { color: #475569; font-size: 13px; }
          .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
          .box { border: 1px solid #bfd4e8; border-radius: 12px; padding: 12px; background: #f5f9fc; }
          .label { color: #48627d; font-size: 11px; font-weight: 700; text-transform: uppercase; }
          .value { font-weight: 700; margin-top: 4px; }
          table { width: 100%; border-collapse: collapse; margin-top: 18px; font-size: 12px; }
          th { background: #dbeaf5; color: #304963; text-align: left; text-transform: uppercase; font-size: 11px; }
          th, td { padding: 10px; border-bottom: 1px solid #d5e3ef; }
          .total { text-align: right; font-size: 16px; font-weight: 700; margin-top: 18px; }
          @media print { button { display: none; } body { margin: 20px; } }
        </style>
      </head>
      <body>
        <header>
          <p class="muted">ACSM Control</p>
          <h1>Orden de compra ${escapeHtml(order.po_number)}</h1>
          <p class="muted">${escapeHtml(order.supplier?.name ?? `Proveedor ${order.supplier_id}`)}</p>
        </header>
        <section class="grid">
          <div class="box"><div class="label">Estado</div><div class="value">${escapeHtml(statusLabel(order.status))}</div></div>
          <div class="box"><div class="label">Emitida</div><div class="value">${escapeHtml(formatDate(order.issued_at))}</div></div>
          <div class="box"><div class="label">Credito</div><div class="value">${escapeHtml(order.payment_terms_days)} dias</div></div>
          <div class="box"><div class="label">Subtotal</div><div class="value">${escapeHtml(formatMoney(order.subtotal))}</div></div>
        </section>
        <section>
          <p><strong>RFC:</strong> ${escapeHtml(order.supplier?.tax_id ?? '-')}</p>
          <p><strong>Contacto:</strong> ${escapeHtml(order.supplier?.contact_name ?? '-')} · ${escapeHtml(order.supplier?.contact_email ?? '-')} · ${escapeHtml(order.supplier?.contact_phone ?? '-')}</p>
        </section>
        <table>
          <thead>
            <tr>
              <th>Material</th>
              <th>Cantidad</th>
              <th>Unidad</th>
              <th>Precio</th>
              <th>Importe</th>
              <th>Recibido</th>
            </tr>
          </thead>
          <tbody>${items}</tbody>
        </table>
        <div class="total">Subtotal: ${escapeHtml(formatMoney(order.subtotal))}</div>
      </body>
    </html>
  `)
  popup.document.close()
  popup.focus()
  popup.print()
}

export default function PurchasingOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [supplierFilter, setSupplierFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const selectedOrder = useMemo(
    () => orders.find((order) => order.id === selectedOrderId) ?? null,
    [orders, selectedOrderId],
  )

  const filteredOrders = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase()
    const normalizedSupplier = supplierFilter.trim().toLocaleLowerCase()
    return orders.filter((order) => {
      const issuedDate = order.issued_at?.slice(0, 10) ?? ''
      if (dateFrom && issuedDate < dateFrom) return false
      if (dateTo && issuedDate > dateTo) return false
      if (statusFilter && order.status !== statusFilter) return false
      if (normalizedSupplier) {
        const supplierText = [order.supplier?.name, order.supplier?.legal_name, order.supplier?.tax_id]
          .join(' ')
          .toLocaleLowerCase()
        if (!supplierText.includes(normalizedSupplier)) return false
      }
      if (normalizedSearch) {
        const itemText = order.items.map((item) => item.description).join(' ')
        const searchText = [
          order.po_number,
          statusLabel(order.status),
          order.supplier?.name,
          order.supplier?.contact_email,
          itemText,
        ]
          .join(' ')
          .toLocaleLowerCase()
        if (!searchText.includes(normalizedSearch)) return false
      }
      return true
    })
  }, [dateFrom, dateTo, orders, search, statusFilter, supplierFilter])

  async function loadOrders() {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest<PurchaseOrder[]>('/purchasing/purchase-orders?limit=250')
      setOrders(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar ordenes de compra')
    } finally {
      setLoading(false)
    }
  }

  async function sendOrder(orderId: number) {
    setError('')
    setMessage('')
    try {
      const updated = await apiRequest<PurchaseOrder>(`/purchasing/purchase-orders/${orderId}/send`, {
        method: 'POST',
      })
      setMessage(`Orden ${updated.po_number} marcada como enviada al proveedor.`)
      await loadOrders()
      setSelectedOrderId(updated.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la orden')
    }
  }

  useEffect(() => {
    void loadOrders()
  }, [])

  return (
    <div className="space-y-5">
      {(message || error) && (
        <div
          className={[
            'rounded-xl border px-4 py-3 text-sm font-semibold',
            error ? 'border-red-200 bg-red-50 text-red-700' : 'border-blue-200 bg-blue-50 text-blue-800',
          ].join(' ')}
        >
          {error || message}
        </div>
      )}

      <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-acsm-paper text-acsm-green">
              <FileText className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">
                Control de compras
              </p>
              <h2 className="text-lg font-bold text-acsm-ink">Ordenes de compra</h2>
              <p className="text-sm text-acsm-muted">
                Consulta historica, auditoria, impresion y envio de ordenes emitidas a proveedores.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadOrders()}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Actualizar
          </button>
        </div>

        <div className="border-b border-acsm-line bg-acsm-panel px-5 py-4">
          <div className="grid gap-3 xl:grid-cols-[minmax(240px,1.4fr)_minmax(180px,0.8fr)_160px_160px_180px]">
            <label className="text-xs font-bold uppercase text-acsm-muted">
              Buscar
              <div className="relative mt-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-acsm-muted" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="h-11 w-full rounded-xl border border-acsm-line bg-white pl-9 pr-3 text-sm font-semibold text-acsm-ink shadow-inner-soft"
                  placeholder="OC, material, estado"
                />
              </div>
            </label>
            <label className="text-xs font-bold uppercase text-acsm-muted">
              Proveedor
              <input
                value={supplierFilter}
                onChange={(event) => setSupplierFilter(event.target.value)}
                className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink shadow-inner-soft"
                placeholder="Nombre o RFC"
              />
            </label>
            <label className="text-xs font-bold uppercase text-acsm-muted">
              Desde
              <input
                type="date"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink shadow-inner-soft"
              />
            </label>
            <label className="text-xs font-bold uppercase text-acsm-muted">
              Hasta
              <input
                type="date"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink shadow-inner-soft"
              />
            </label>
            <label className="text-xs font-bold uppercase text-acsm-muted">
              Estado
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink shadow-inner-soft"
              >
                <option value="">Todos</option>
                <option value="issued">Emitida</option>
                <option value="sent">Enviada</option>
                <option value="partially_received">Parcial recibida</option>
                <option value="received">Recibida</option>
                <option value="factured">Facturada</option>
                <option value="closed">Cerrada</option>
                <option value="cancelled">Cancelada</option>
              </select>
            </label>
          </div>
        </div>

        <div className="max-h-[620px] overflow-y-auto">
          <table className="w-full table-fixed text-sm">
            <thead className="sticky top-0 z-10 bg-acsm-paper text-xs uppercase text-acsm-muted shadow-[0_1px_0_rgba(128,160,190,0.35)]">
              <tr>
                <th className="w-[17%] px-4 py-3 text-left">Orden</th>
                <th className="w-[20%] px-4 py-3 text-left">Proveedor</th>
                <th className="w-[12%] px-4 py-3 text-left">Fecha</th>
                <th className="w-[12%] px-4 py-3 text-left">Estado</th>
                <th className="w-[13%] px-4 py-3 text-left">Subtotal</th>
                <th className="w-[16%] px-4 py-3 text-left">Recepcion</th>
                <th className="w-[10%] px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredOrders.map((order) => {
                const progress = orderProgress(order)
                return (
                  <tr
                    key={order.id}
                    className="border-t border-acsm-line bg-white hover:bg-sky-50/70"
                  >
                    <td className="px-4 py-4 align-top">
                      <button
                        type="button"
                        onClick={() => setSelectedOrderId(order.id)}
                        className="text-left"
                      >
                        <span className="block font-bold text-acsm-ink">{order.po_number}</span>
                        <span className="text-xs font-semibold text-blue-700">Ver documento</span>
                      </button>
                    </td>
                    <td className="px-4 py-4 align-top">
                      <div className="truncate font-bold text-acsm-ink">
                        {order.supplier?.name ?? `Proveedor ${order.supplier_id}`}
                      </div>
                      <div className="truncate text-xs text-acsm-muted">{order.supplier?.contact_email ?? '-'}</div>
                    </td>
                    <td className="px-4 py-4 align-top font-semibold">{formatDate(order.issued_at)}</td>
                    <td className="px-4 py-4 align-top">
                      <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
                        {statusLabel(order.status)}
                      </span>
                    </td>
                    <td className="px-4 py-4 align-top font-semibold">{formatMoney(order.subtotal)}</td>
                    <td className="px-4 py-4 align-top">
                      <div className="font-semibold text-acsm-ink">
                        {progress.received.toLocaleString('es-MX')} / {progress.total.toLocaleString('es-MX')}
                      </div>
                      <div className="mt-2 h-2 rounded-full bg-slate-200">
                        <div
                          className="h-2 rounded-full bg-blue-600"
                          style={{ width: `${progress.percent}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-4 text-right align-top">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setSelectedOrderId(order.id)}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper"
                          title="Abrir"
                        >
                          <Eye className="h-4 w-4" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          onClick={() => printOrder(order)}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper"
                          title="Imprimir / PDF"
                        >
                          <Printer className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
              {!filteredOrders.length && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-acsm-muted">
                    {loading ? 'Cargando ordenes...' : 'No hay ordenes que coincidan con los filtros.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {selectedOrder ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={() => setSelectedOrderId(null)}
        >
          <div
            className="max-h-[90vh] w-full max-w-6xl overflow-hidden rounded-[24px] border border-white/20 bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">
                  Documento de compra
                </p>
                <h2 className="text-xl font-bold text-acsm-ink">{selectedOrder.po_number}</h2>
                <p className="text-sm text-acsm-muted">
                  {selectedOrder.supplier?.name ?? `Proveedor ${selectedOrder.supplier_id}`} ·{' '}
                  {statusLabel(selectedOrder.status)} · Emitida {formatDate(selectedOrder.issued_at)}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => printOrder(selectedOrder)}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 text-sm font-bold text-blue-700 hover:bg-blue-100"
                >
                  <Printer className="h-4 w-4" aria-hidden="true" />
                  Imprimir / PDF
                </button>
                <button
                  type="button"
                  onClick={() => void sendOrder(selectedOrder.id)}
                  disabled={selectedOrder.status !== 'issued'}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper disabled:opacity-60"
                >
                  <Send className="h-4 w-4" aria-hidden="true" />
                  Enviar OC
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedOrderId(null)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper"
                  aria-label="Cerrar"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
            </div>

            <div className="max-h-[calc(90vh-92px)] overflow-y-auto p-6">
              <div className="grid gap-3 md:grid-cols-4">
                {[
                  ['Estado', statusLabel(selectedOrder.status)],
                  ['Fecha emision', formatDate(selectedOrder.issued_at)],
                  ['Credito', `${selectedOrder.payment_terms_days} dias`],
                  ['Subtotal', formatMoney(selectedOrder.subtotal)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-acsm-line bg-acsm-paper p-4">
                    <div className="text-xs font-bold uppercase text-acsm-muted">{label}</div>
                    <div className="mt-1 text-lg font-bold text-acsm-ink">{value}</div>
                  </div>
                ))}
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
                <section className="rounded-xl border border-acsm-line bg-white">
                  <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3 font-bold">
                    Proveedor
                  </div>
                  <div className="space-y-2 p-4 text-sm">
                    <div className="font-bold text-acsm-ink">
                      {selectedOrder.supplier?.name ?? `Proveedor ${selectedOrder.supplier_id}`}
                    </div>
                    <div className="text-acsm-muted">RFC: {selectedOrder.supplier?.tax_id ?? '-'}</div>
                    <div className="text-acsm-muted">Contacto: {selectedOrder.supplier?.contact_name ?? '-'}</div>
                    <div className="text-acsm-muted">Correo: {selectedOrder.supplier?.contact_email ?? '-'}</div>
                    <div className="text-acsm-muted">Telefono: {selectedOrder.supplier?.contact_phone ?? '-'}</div>
                    <div className="text-acsm-muted">Direccion: {selectedOrder.supplier?.address ?? '-'}</div>
                  </div>
                </section>

                <section className="rounded-xl border border-acsm-line bg-white">
                  <div className="flex items-center justify-between border-b border-acsm-line bg-acsm-paper px-4 py-3">
                    <div className="font-bold">Partidas de la orden</div>
                    <span className="rounded-full border border-acsm-line bg-white px-3 py-1 text-xs font-bold text-acsm-muted">
                      {selectedOrder.items.length} partidas
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full table-fixed text-sm">
                      <thead className="bg-slate-50 text-xs uppercase text-acsm-muted">
                        <tr>
                          <th className="w-[34%] px-4 py-3 text-left">Material</th>
                          <th className="w-[12%] px-4 py-3 text-left">Pedido</th>
                          <th className="w-[12%] px-4 py-3 text-left">Recibido</th>
                          <th className="w-[14%] px-4 py-3 text-left">Precio</th>
                          <th className="w-[14%] px-4 py-3 text-left">Importe</th>
                          <th className="w-[14%] px-4 py-3 text-left">Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedOrder.items.map((item) => (
                          <tr key={item.id} className="border-t border-acsm-line">
                            <td className="px-4 py-3 align-top font-semibold text-acsm-ink">
                              <div className="line-clamp-2">{item.description}</div>
                            </td>
                            <td className="px-4 py-3 align-top">
                              {Number(item.quantity_ordered).toLocaleString('es-MX')} {item.unit}
                            </td>
                            <td className="px-4 py-3 align-top">
                              {Number(item.received_quantity).toLocaleString('es-MX')} {item.unit}
                            </td>
                            <td className="px-4 py-3 align-top">{formatMoney(item.unit_price)}</td>
                            <td className="px-4 py-3 align-top">{formatMoney(item.line_total)}</td>
                            <td className="px-4 py-3 align-top">{statusLabel(item.status)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
