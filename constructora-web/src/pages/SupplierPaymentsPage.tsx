import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, CreditCard, FileCheck2, RefreshCw } from 'lucide-react'

import { apiRequest } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'

type Supplier = {
  id: number
  name: string
}

type PurchaseOrder = {
  id: number
  po_number: string
  status: string
  billing_mode: 'single' | 'partial'
  subtotal: string
  payment_terms_days: number
  supplier?: Supplier | null
  items: {
    id: number
    description: string
    quantity_ordered: string
    received_quantity: string
    unit_price: string
    unit: string
  }[]
}

type SupplierInvoiceItem = {
  id: number
  purchase_order_item_id: number
  quantity: string
  unit_price: string
  line_total: string
}

type SupplierInvoice = {
  id: number
  supplier_id: number
  purchase_order_id: number
  invoice_number: string
  invoice_date: string
  due_date: string
  total: string
  status: string
  document_name?: string | null
  notes?: string | null
  supplier?: Supplier | null
  purchase_order?: PurchaseOrder | null
  items: SupplierInvoiceItem[]
}

type SupplierPayment = {
  id: number
  supplier_invoice_id: number
  amount: string
  scheduled_date?: string | null
  paid_at?: string | null
  status: string
  reference?: string | null
}

const money = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
})

function formatMoney(value: string | number) {
  return money.format(Number(value || 0))
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    issued: 'Emitida',
    sent: 'Enviada',
    partially_received: 'Recepcion parcial',
    received: 'Recibida completa',
    factured: 'Facturada',
    closed: 'Cerrada',
    cancelled: 'Cancelada',
    received_invoice: 'Factura recibida',
    blocked: 'Bloqueada por faltantes',
    approved_for_payment: 'Aprobada para pago',
    scheduled: 'Pago programado',
    paid: 'Pagada',
    rejected: 'Rechazada',
  }
  return labels[status] ?? status
}

export default function SupplierPaymentsPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [invoices, setInvoices] = useState<SupplierInvoice[]>([])
  const [payments, setPayments] = useState<SupplierPayment[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [purchaseOrderId, setPurchaseOrderId] = useState('')
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [invoiceDate, setInvoiceDate] = useState('')
  const [documentName, setDocumentName] = useState('')
  const [total, setTotal] = useState('')
  const [invoiceRows, setInvoiceRows] = useState<Record<number, { quantity: string; unit_price: string }>>({})

  const [invoiceToPay, setInvoiceToPay] = useState('')
  const [scheduledDate, setScheduledDate] = useState('')
  const [reference, setReference] = useState('')

  const invoiceMap = useMemo(
    () => new Map(invoices.map((invoice) => [invoice.id, invoice])),
    [invoices],
  )
  const selectedOrder = useMemo(
    () => orders.find((order) => String(order.id) === purchaseOrderId) ?? null,
    [orders, purchaseOrderId],
  )
  const invoicedQuantityByItem = useMemo(() => {
    const activeStatuses = new Set(['received', 'approved_for_payment', 'scheduled', 'paid'])
    const totals = new Map<number, number>()
    for (const invoice of invoices) {
      if (!activeStatuses.has(invoice.status)) continue
      for (const item of invoice.items ?? []) {
        totals.set(
          item.purchase_order_item_id,
          (totals.get(item.purchase_order_item_id) ?? 0) + Number(item.quantity || 0),
        )
      }
    }
    return totals
  }, [invoices])
  const partialInvoiceRows = useMemo(() => {
    if (!selectedOrder) return []
    return selectedOrder.items.map((item) => {
      const received = Number(item.received_quantity || 0)
      const invoiced = invoicedQuantityByItem.get(item.id) ?? 0
      const available = Math.max(received - invoiced, 0)
      const draft = invoiceRows[item.id] ?? { quantity: '', unit_price: item.unit_price || '0' }
      const quantity = Number(draft.quantity || 0)
      const unitPrice = Number(draft.unit_price || 0)
      return { ...item, received, invoiced, available, draft, lineTotal: quantity * unitPrice }
    })
  }, [invoiceRows, invoicedQuantityByItem, selectedOrder])
  const partialTotal = partialInvoiceRows.reduce((sum, row) => sum + row.lineTotal, 0)
  const selectedOrderIsPartial = selectedOrder?.billing_mode === 'partial'

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [orderData, invoiceData, paymentData] = await Promise.all([
        apiRequest<PurchaseOrder[]>('/purchasing/purchase-orders'),
        apiRequest<SupplierInvoice[]>('/purchasing/supplier-invoices'),
        apiRequest<SupplierPayment[]>('/purchasing/supplier-payments'),
      ])
      setOrders(orderData)
      setInvoices(invoiceData)
      setPayments(paymentData)
      if (!purchaseOrderId && orderData[0]) setPurchaseOrderId(String(orderData[0].id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar pagos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  useEffect(() => {
    if (!selectedOrder) {
      setInvoiceRows({})
      return
    }
    setInvoiceRows((current) => {
      const next: Record<number, { quantity: string; unit_price: string }> = {}
      for (const item of selectedOrder.items) {
        next[item.id] = current[item.id] ?? { quantity: '', unit_price: item.unit_price || '0' }
      }
      return next
    })
  }, [selectedOrder])

  function patchInvoiceRow(itemId: number, patch: Partial<{ quantity: string; unit_price: string }>) {
    setInvoiceRows((current) => ({
      ...current,
      [itemId]: {
        quantity: current[itemId]?.quantity ?? '',
        unit_price: current[itemId]?.unit_price ?? '0',
        ...patch,
      },
    }))
  }

  async function updateBillingMode(mode: 'single' | 'partial') {
    if (!selectedOrder) return
    setMessage('')
    setError('')
    try {
      const updated = await apiRequest<PurchaseOrder>(
        `/purchasing/purchase-orders/${selectedOrder.id}/billing-mode`,
        {
          method: 'PATCH',
          body: JSON.stringify({ billing_mode: mode }),
        },
      )
      setOrders((current) => current.map((order) => (order.id === updated.id ? updated : order)))
      const successMessage =
        mode === 'partial'
          ? `Orden ${updated.po_number} configurada para facturacion parcial.`
          : `Orden ${updated.po_number} configurada para pago unico.`
      setMessage(successMessage)
      showActionNotice(successMessage)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cambiar el modo de facturacion')
    }
  }

  async function createInvoice() {
    setMessage('')
    setError('')
    try {
      const partialItems = partialInvoiceRows
        .filter((row) => Number(row.draft.quantity || 0) > 0)
        .map((row) => ({
          purchase_order_item_id: row.id,
          quantity: Number(row.draft.quantity),
          unit_price: Number(row.draft.unit_price || row.unit_price || 0),
        }))
      const created = await apiRequest<SupplierInvoice>('/purchasing/supplier-invoices', {
        method: 'POST',
        body: JSON.stringify({
          purchase_order_id: Number(purchaseOrderId),
          invoice_number: invoiceNumber,
          invoice_date: invoiceDate,
          total: selectedOrderIsPartial ? Number(partialTotal.toFixed(2)) : Number(total),
          document_name: documentName || null,
          items: selectedOrderIsPartial ? partialItems : [],
        }),
      })
      const successMessage = `Factura ${created.invoice_number} registrada como ${statusLabel(created.status)}.`
      setMessage(successMessage)
      showActionNotice(successMessage)
      setInvoiceNumber('')
      setDocumentName('')
      setTotal('')
      setInvoiceRows({})
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible registrar la factura')
    }
  }

  async function validateInvoice(invoiceId: number) {
    setMessage('')
    setError('')
    try {
      const result = await apiRequest<{ status: string; pending_items: number; message: string }>(
        `/purchasing/supplier-invoices/${invoiceId}/validate`,
        { method: 'POST' },
      )
      setMessage(result.message)
      showActionNotice(result.message)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible validar la factura')
    }
  }

  async function schedulePayment() {
    const invoice = invoiceMap.get(Number(invoiceToPay))
    if (!invoice) return
    setMessage('')
    setError('')
    try {
      await apiRequest<SupplierPayment>('/purchasing/supplier-payments', {
        method: 'POST',
        body: JSON.stringify({
          supplier_invoice_id: invoice.id,
          amount: Number(invoice.total),
          scheduled_date: scheduledDate || null,
          status: 'scheduled',
          reference: reference || null,
        }),
      })
      const successMessage = `Pago programado para factura ${invoice.invoice_number}.`
      setMessage(successMessage)
      showActionNotice(successMessage)
      setInvoiceToPay('')
      setReference('')
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible programar el pago')
    }
  }

  async function markPaid(payment: SupplierPayment) {
    setMessage('')
    setError('')
    try {
      await apiRequest<SupplierPayment>(`/purchasing/supplier-payments/${payment.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: 'paid',
          paid_at: new Date().toISOString().slice(0, 10),
        }),
      })
      const successMessage = 'Pago marcado como realizado.'
      setMessage(successMessage)
      showActionNotice(successMessage)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible marcar el pago')
    }
  }

  const payableInvoices = invoices.filter((invoice) =>
    ['approved_for_payment', 'scheduled'].includes(invoice.status),
  )

  return (
    <div className="space-y-5">
      {error && (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
        >
          {error}
        </div>
      )}

      <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex items-center justify-between border-b border-acsm-line px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-green">
              <FileCheck2 className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <h2 className="font-semibold text-acsm-ink">Facturas de proveedores</h2>
              <p className="text-xs text-acsm-muted">
                Valida facturas completas o por entregas parciales contra material recibido.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadData()}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Actualizar
          </button>
        </div>

        <div className="grid gap-4 p-4 lg:grid-cols-[420px_minmax(0,1fr)]">
          <div className="rounded-md border border-acsm-line bg-acsm-paper p-3">
            <h3 className="mb-3 text-sm font-semibold text-acsm-ink">Registrar factura</h3>
            <div className="space-y-3">
              <select
                value={purchaseOrderId}
                onChange={(event) => setPurchaseOrderId(event.target.value)}
                className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
              >
                <option value="">Orden de compra</option>
                {orders.map((order) => (
                  <option key={order.id} value={order.id}>
                    {order.po_number} · {order.supplier?.name ?? 'Proveedor'} · {statusLabel(order.status)} ·{' '}
                    {order.billing_mode === 'partial' ? 'Parcial' : 'Pago unico'}
                  </option>
                ))}
              </select>
              {selectedOrder && (
                <div className="rounded-md border border-acsm-line bg-white p-2">
                  <div className="mb-2 text-xs font-semibold uppercase text-acsm-muted">Modo de facturacion</div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => void updateBillingMode('single')}
                      className={[
                        'h-9 rounded-md border px-3 text-xs font-bold',
                        !selectedOrderIsPartial
                          ? 'border-blue-300 bg-blue-50 text-blue-800'
                          : 'border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper',
                      ].join(' ')}
                    >
                      Pago unico
                    </button>
                    <button
                      type="button"
                      onClick={() => void updateBillingMode('partial')}
                      className={[
                        'h-9 rounded-md border px-3 text-xs font-bold',
                        selectedOrderIsPartial
                          ? 'border-blue-300 bg-blue-50 text-blue-800'
                          : 'border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper',
                      ].join(' ')}
                    >
                      Parcial por entregas
                    </button>
                  </div>
                </div>
              )}
              <input
                value={invoiceNumber}
                onChange={(event) => setInvoiceNumber(event.target.value)}
                placeholder="Folio factura"
                className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
              />
              <input
                type="date"
                value={invoiceDate}
                onChange={(event) => setInvoiceDate(event.target.value)}
                className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
              />
              <input
                value={documentName}
                onChange={(event) => setDocumentName(event.target.value)}
                placeholder="Archivo o referencia"
                className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
              />
              {selectedOrderIsPartial ? (
                <div className="overflow-hidden rounded-md border border-acsm-line bg-white">
                  <div className="border-b border-acsm-line px-3 py-2 text-xs font-semibold uppercase text-acsm-muted">
                    Partidas recibidas disponibles para facturar
                  </div>
                  <div className="max-h-[260px] overflow-auto">
                    <table className="min-w-[680px] w-full text-xs">
                      <thead className="bg-acsm-paper text-acsm-muted">
                        <tr>
                          <th className="px-2 py-2 text-left">Material</th>
                          <th className="px-2 py-2 text-right">Recibido</th>
                          <th className="px-2 py-2 text-right">Facturado</th>
                          <th className="px-2 py-2 text-right">Disponible</th>
                          <th className="px-2 py-2 text-right">Facturar</th>
                          <th className="px-2 py-2 text-right">PU</th>
                        </tr>
                      </thead>
                      <tbody>
                        {partialInvoiceRows.map((row) => (
                          <tr key={row.id} className="border-t border-acsm-line">
                            <td className="px-2 py-2 font-semibold text-acsm-ink">{row.description}</td>
                            <td className="px-2 py-2 text-right">{row.received.toLocaleString('es-MX')} {row.unit}</td>
                            <td className="px-2 py-2 text-right">{row.invoiced.toLocaleString('es-MX')}</td>
                            <td className="px-2 py-2 text-right">{row.available.toLocaleString('es-MX')}</td>
                            <td className="px-2 py-2">
                              <input
                                type="number"
                                min="0"
                                max={row.available}
                                step="0.0001"
                                value={row.draft.quantity}
                                onChange={(event) => patchInvoiceRow(row.id, { quantity: event.target.value })}
                                disabled={row.available <= 0}
                                className="h-8 w-full rounded-md border border-acsm-line px-2 text-right disabled:bg-slate-100"
                              />
                            </td>
                            <td className="px-2 py-2">
                              <input
                                type="number"
                                min="0"
                                step="0.0001"
                                value={row.draft.unit_price}
                                onChange={(event) => patchInvoiceRow(row.id, { unit_price: event.target.value })}
                                disabled={row.available <= 0}
                                className="h-8 w-full rounded-md border border-acsm-line px-2 text-right disabled:bg-slate-100"
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="border-t border-acsm-line px-3 py-2 text-right text-sm font-bold text-acsm-ink">
                    Total parcial: {formatMoney(partialTotal)}
                  </div>
                </div>
              ) : (
                <input
                  type="number"
                  step="0.01"
                  value={total}
                  onChange={(event) => setTotal(event.target.value)}
                  placeholder="Total factura"
                  className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                />
              )}
              <button
                type="button"
                onClick={() => void createInvoice()}
                disabled={
                  loading ||
                  !purchaseOrderId ||
                  !invoiceNumber ||
                  !invoiceDate ||
                  (selectedOrderIsPartial ? partialTotal <= 0 : !total)
                }
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
              >
                <FileCheck2 className="h-4 w-4" aria-hidden="true" />
                Guardar factura
              </button>
            </div>
          </div>

          <div className="overflow-x-auto rounded-md border border-acsm-line">
            <table className="min-w-[920px] w-full text-sm">
              <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                <tr>
                  <th className="px-4 py-3 text-left">Factura</th>
                  <th className="px-4 py-3 text-left">Proveedor</th>
                  <th className="px-4 py-3 text-left">Orden</th>
                  <th className="px-4 py-3 text-left">Vence</th>
                  <th className="px-4 py-3 text-left">Total</th>
                  <th className="px-4 py-3 text-left">Estado</th>
                  <th className="px-4 py-3 text-right">Accion</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="border-t border-acsm-line">
                    <td className="px-4 py-3 font-semibold">{invoice.invoice_number}</td>
                    <td className="px-4 py-3">{invoice.supplier?.name ?? invoice.supplier_id}</td>
                    <td className="px-4 py-3">{invoice.purchase_order?.po_number ?? invoice.purchase_order_id}</td>
                    <td className="px-4 py-3">{invoice.due_date}</td>
                    <td className="px-4 py-3">{formatMoney(invoice.total)}</td>
                    <td className="px-4 py-3">{statusLabel(invoice.status)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => void validateInvoice(invoice.id)}
                        className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
                      >
                        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                        Validar
                      </button>
                    </td>
                  </tr>
                ))}
                {!invoices.length && (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-acsm-muted">
                      Aun no hay facturas registradas.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[420px_minmax(0,1fr)]">
        <div className="rounded-md border border-acsm-line bg-white p-4 shadow-panel">
          <div className="mb-3 flex items-center gap-3">
            <CreditCard className="h-4 w-4 text-acsm-green" aria-hidden="true" />
            <div>
              <h2 className="font-semibold text-acsm-ink">Programar pago</h2>
              <p className="text-xs text-acsm-muted">Solo aparecen facturas aprobadas para pago.</p>
            </div>
          </div>
          <div className="space-y-3">
            <select
              value={invoiceToPay}
              onChange={(event) => setInvoiceToPay(event.target.value)}
              className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
            >
              <option value="">Factura aprobada</option>
              {payableInvoices.map((invoice) => (
                <option key={invoice.id} value={invoice.id}>
                  {invoice.invoice_number} · {invoice.supplier?.name ?? invoice.supplier_id} ·{' '}
                  {formatMoney(invoice.total)}
                </option>
              ))}
            </select>
            <input
              type="date"
              value={scheduledDate}
              onChange={(event) => setScheduledDate(event.target.value)}
              className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
            />
            <input
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              placeholder="Referencia interna"
              className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
            />
            <button
              type="button"
              onClick={() => void schedulePayment()}
              disabled={!invoiceToPay}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
            >
              <CreditCard className="h-4 w-4" aria-hidden="true" />
              Programar pago
            </button>
          </div>
        </div>

        <div className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
          <div className="border-b border-acsm-line px-4 py-3">
            <h2 className="font-semibold text-acsm-ink">Pagos</h2>
            <p className="text-xs text-acsm-muted">Seguimiento de pagos programados y realizados.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-[720px] w-full text-sm">
              <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                <tr>
                  <th className="px-4 py-3 text-left">Factura</th>
                  <th className="px-4 py-3 text-left">Monto</th>
                  <th className="px-4 py-3 text-left">Programado</th>
                  <th className="px-4 py-3 text-left">Estado</th>
                  <th className="px-4 py-3 text-right">Accion</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((payment) => {
                  const invoice = invoiceMap.get(payment.supplier_invoice_id)
                  return (
                    <tr key={payment.id} className="border-t border-acsm-line">
                      <td className="px-4 py-3 font-semibold">
                        {invoice?.invoice_number ?? payment.supplier_invoice_id}
                      </td>
                      <td className="px-4 py-3">{formatMoney(payment.amount)}</td>
                      <td className="px-4 py-3">{payment.scheduled_date ?? '-'}</td>
                      <td className="px-4 py-3">{statusLabel(payment.status)}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => void markPaid(payment)}
                          disabled={payment.status === 'paid'}
                          className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper disabled:opacity-60"
                        >
                          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                          Pagado
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {!payments.length && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-acsm-muted">
                      No hay pagos programados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  )
}
