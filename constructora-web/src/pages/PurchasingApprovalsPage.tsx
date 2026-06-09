import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ClipboardCheck, RefreshCw, XCircle } from 'lucide-react'

import { apiRequest } from '../lib/api'
import { showActionNotice, type ActionNoticeKind } from '../lib/actionNotice'

type Supplier = {
  id: number
  name: string
  payment_terms_days: number
}

type UserSummary = {
  id: number
  full_name: string
  email: string
}

type RFQItem = {
  id: number
  description: string
  unit: string
  quantity: string
}

type SupplierRFQ = {
  id: number
  rfq_number: string
  title: string
  status: string
  created_at: string
  creator?: UserSummary | null
  items: RFQItem[]
}

type SupplierQuote = {
  id: number
  supplier_id: number
  quote_number?: string | null
  status: string
  subtotal: string
  delivery_days?: number | null
  payment_terms_days: number
  supplier?: Supplier | null
  items: {
    id: number
    description: string
    unit: string
    quantity: string
    unit_price: string
    line_total: string
    delivery_days?: number | null
  }[]
}

type SupplierQuoteApproval = {
  id: number
  rfq_id: number
  supplier_quote_id: number
  status: string
  request_notes?: string | null
  decision_notes?: string | null
  requested_at: string
  decided_at?: string | null
  requester?: UserSummary | null
  decider?: UserSummary | null
  supplier_quote: SupplierQuote
  rfq: SupplierRFQ
}

type SupplierRFQException = {
  id: number
  title: string
  status: string
  required_by?: string | null
  response_deadline?: string | null
  supplier_count: number
  item_count: number
  payload_snapshot: {
    supplier_ids: number[]
    items: {
      description: string
      unit: string
      quantity: string
    }[]
  }
  request_notes: string
  requested_at: string
  requester?: UserSummary | null
}

type ComparisonRow = {
  supplier_quote_id: number
  supplier_name: string
  subtotal: string
  delivery_days?: number | null
  payment_terms_days: number
  status: string
  complete_items: number
  total_items: number
}

const money = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
})

function formatMoney(value: string | number) {
  return money.format(Number(value || 0))
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('es-MX', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    requested: 'Pendiente',
    approved: 'Aprobada',
    rejected: 'Rechazada',
    cancelled: 'Cancelada',
    queued: 'En cola',
    sent: 'Enviada',
    email_error: 'Error de correo',
    missing_email: 'Sin correo',
    received: 'Recibida',
    approval_requested: 'Pendiente aprobacion',
    discarded: 'Descartada',
  }
  return labels[status] ?? status
}

function approvalRequestContext(notes?: string | null) {
  const value = notes?.trim() ?? ''
  if (!value.startsWith('EXCEPCION:')) {
    return { isException: false, notes: value }
  }
  return {
    isException: true,
    notes: value.replace(/^EXCEPCION:\s*/i, '').trim(),
  }
}

export default function PurchasingApprovalsPage() {
  const [approvals, setApprovals] = useState<SupplierQuoteApproval[]>([])
  const [rfqExceptions, setRfqExceptions] = useState<SupplierRFQException[]>([])
  const [selectedApprovalId, setSelectedApprovalId] = useState<number | null>(null)
  const [selectedExceptionId, setSelectedExceptionId] = useState<number | null>(null)
  const [comparison, setComparison] = useState<ComparisonRow[]>([])
  const [quotes, setQuotes] = useState<SupplierQuote[]>([])
  const [selectedQuoteId, setSelectedQuoteId] = useState<number | null>(null)
  const [decisionNotes, setDecisionNotes] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const selectedApproval = useMemo(
    () => approvals.find((approval) => approval.id === selectedApprovalId) ?? null,
    [approvals, selectedApprovalId],
  )
  const selectedException = useMemo(
    () => rfqExceptions.find((entry) => entry.id === selectedExceptionId) ?? null,
    [rfqExceptions, selectedExceptionId],
  )
  const selectedQuote = useMemo(
    () =>
      quotes.find((quote) => quote.id === selectedQuoteId) ??
      (selectedApproval?.supplier_quote_id === selectedQuoteId ? selectedApproval.supplier_quote : null) ??
      selectedApproval?.supplier_quote ??
      null,
    [quotes, selectedApproval, selectedQuoteId],
  )
  const selectedContext = useMemo(
    () => approvalRequestContext(selectedApproval?.request_notes),
    [selectedApproval?.request_notes],
  )

  function notifySuccess(text: string, kind: ActionNoticeKind = 'success') {
    setMessage(text)
    showActionNotice(text, kind)
  }

  async function loadApprovals(nextSelectedId = selectedApprovalId) {
    setLoading(true)
    setError('')
    try {
      const [data, exceptionData] = await Promise.all([
        apiRequest<SupplierQuoteApproval[]>('/purchasing/supplier-quote-approvals?approval_status=requested'),
        apiRequest<SupplierRFQException[]>('/purchasing/supplier-rfq-exceptions?approval_status=requested'),
      ])
      setApprovals(data)
      setRfqExceptions(exceptionData)
      if (exceptionData.length && !nextSelectedId) {
        setSelectedExceptionId(exceptionData[0].id)
        setSelectedApprovalId(null)
      } else {
        setSelectedApprovalId(nextSelectedId ?? data[0]?.id ?? null)
        setSelectedExceptionId(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar aprobaciones')
    } finally {
      setLoading(false)
    }
  }

  async function loadComparison(rfqId: number | undefined) {
    if (!rfqId) {
      setComparison([])
      setQuotes([])
      return
    }
    try {
      const [comparisonData, quoteData] = await Promise.all([
        apiRequest<ComparisonRow[]>(`/purchasing/supplier-rfqs/${rfqId}/comparison`),
        apiRequest<SupplierQuote[]>(`/purchasing/supplier-rfqs/${rfqId}/quotes`),
      ])
      setComparison(comparisonData)
      setQuotes(quoteData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar comparativo')
    }
  }

  useEffect(() => {
    void loadApprovals()
  }, [])

  useEffect(() => {
    setSelectedQuoteId(selectedApproval?.supplier_quote_id ?? null)
    void loadComparison(selectedApproval?.rfq_id)
    setDecisionNotes('')
  }, [selectedApproval?.id, selectedException?.id])

  async function approveSelected() {
    if (!selectedApproval || !selectedQuote) return
    setError('')
    setMessage('')
    try {
      const result = await apiRequest<{ purchase_order: { po_number: string } }>(
        `/purchasing/supplier-quotes/${selectedQuote.id}/approve`,
        { method: 'POST' },
      )
      notifySuccess(`Aprobacion registrada. Se genero la orden ${result.purchase_order.po_number}.`)
      await loadApprovals()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible aprobar la cotizacion')
    }
  }

  async function rejectSelected() {
    if (!selectedApproval) return
    setError('')
    setMessage('')
    try {
      await apiRequest(`/purchasing/supplier-quotes/${selectedApproval.supplier_quote_id}/reject-approval`, {
        method: 'POST',
        body: JSON.stringify({ decision_notes: decisionNotes || null }),
      })
      notifySuccess('Cotizacion rechazada. El comprador podra seleccionar otra opcion.', 'warning')
      await loadApprovals()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible rechazar la cotizacion')
    }
  }

  async function approveSelectedException() {
    if (!selectedException) return
    setError('')
    setMessage('')
    try {
      await apiRequest(`/purchasing/supplier-rfq-exceptions/${selectedException.id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ decision_notes: decisionNotes || null }),
      })
      notifySuccess('Excepcion aprobada. El comprador ya puede crear la solicitud con menos de 3 proveedores.')
      setSelectedExceptionId(null)
      await loadApprovals()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible aprobar la excepcion')
    }
  }

  async function rejectSelectedException() {
    if (!selectedException) return
    setError('')
    setMessage('')
    try {
      await apiRequest(`/purchasing/supplier-rfq-exceptions/${selectedException.id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ decision_notes: decisionNotes || null }),
      })
      notifySuccess('Excepcion rechazada.', 'warning')
      setSelectedExceptionId(null)
      await loadApprovals()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible rechazar la excepcion')
    }
  }

  return (
    <div className="space-y-5">
      {error && (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
        >
          {error}
        </div>
      )}

      <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-acsm-paper text-acsm-green">
              <ClipboardCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">
                Control de compras
              </p>
              <h2 className="text-lg font-bold text-acsm-ink">Aprobaciones de cotizacion</h2>
              <p className="text-sm text-acsm-muted">
                Revisa la recomendacion del comprador antes de autorizar la orden de compra.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadApprovals()}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Actualizar
          </button>
        </div>

        <div className="grid min-h-[560px] lg:grid-cols-[420px_minmax(0,1fr)]">
          <aside className="border-b border-acsm-line bg-acsm-paper/60 lg:border-b-0 lg:border-r">
            <div className="flex items-center justify-between border-b border-acsm-line px-4 py-3">
              <div>
                <h3 className="font-bold text-acsm-ink">Pendientes</h3>
                <p className="text-xs text-acsm-muted">
                  {approvals.length + rfqExceptions.length} por revisar
                </p>
              </div>
              {loading ? <span className="text-xs text-acsm-muted">Cargando...</span> : null}
            </div>
            <div className="max-h-[520px] overflow-y-auto">
              {rfqExceptions.map((entry) => (
                <button
                  key={`exception-${entry.id}`}
                  type="button"
                  onClick={() => {
                    setSelectedExceptionId(entry.id)
                    setSelectedApprovalId(null)
                  }}
                  className={[
                    'block w-full border-l-4 border-b border-acsm-line px-4 py-4 text-left transition',
                    selectedException?.id === entry.id
                      ? 'border-amber-500 bg-white shadow-[inset_0_0_0_1px_rgba(217,119,6,0.24)]'
                      : 'border-transparent hover:bg-white',
                  ].join(' ')}
                >
                  <span className="block text-sm font-bold text-acsm-ink">{entry.title}</span>
                  <span className="mt-1 block text-xs font-semibold text-amber-800">
                    Excepcion para crear solicitud
                  </span>
                  <span className="mt-3 block text-sm font-semibold text-acsm-ink">
                    {entry.supplier_count} proveedor(es) · {entry.item_count} partida(s)
                  </span>
                  <span className="text-xs text-acsm-muted">
                    Solicitada por {entry.requester?.full_name ?? 'Sin usuario'}
                  </span>
                </button>
              ))}
              {approvals.map((approval) => {
                const context = approvalRequestContext(approval.request_notes)
                return (
                  <button
                    key={approval.id}
                    type="button"
                    onClick={() => setSelectedApprovalId(approval.id)}
                    className={[
                      'block w-full border-l-4 border-b border-acsm-line px-4 py-4 text-left transition',
                      selectedApproval?.id === approval.id
                        ? 'border-blue-600 bg-white shadow-[inset_0_0_0_1px_rgba(47,120,189,0.18)]'
                        : 'border-transparent hover:bg-white',
                    ].join(' ')}
                  >
                    <span className="block text-sm font-bold text-acsm-ink">{approval.rfq.title}</span>
                    <span className="mt-1 block text-xs font-semibold text-blue-800">
                      {approval.rfq.rfq_number}
                    </span>
                    <span className="mt-3 block text-sm font-semibold text-acsm-ink">
                      Comparativo de proveedores
                    </span>
                    <span className="text-xs text-acsm-muted">
                      Referencia:{' '}
                      {approval.supplier_quote.supplier?.name ?? `Proveedor ${approval.supplier_quote.supplier_id}`} ·{' '}
                      solicitada por {approval.requester?.full_name ?? 'Sin usuario'}
                    </span>
                    {context.isException ? (
                      <span className="mt-2 inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-800">
                        Excepcion
                      </span>
                    ) : null}
                  </button>
                )
              })}
              {!approvals.length && !rfqExceptions.length ? (
                <div className="px-4 py-12 text-center text-sm text-acsm-muted">
                  No hay cotizaciones pendientes de aprobacion.
                </div>
              ) : null}
            </div>
          </aside>

          <div className="min-w-0 p-5">
            {selectedException ? (
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-700">
                      Excepcion para crear solicitud
                    </p>
                    <h3 className="text-2xl font-bold text-acsm-ink">{selectedException.title}</h3>
                    <p className="text-sm text-acsm-muted">
                      Solicitada el {formatDateTime(selectedException.requested_at)} por{' '}
                      {selectedException.requester?.full_name ?? 'Sin usuario'}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    <div className="rounded-xl border border-acsm-line bg-white p-3">
                      <div className="text-xs font-bold uppercase text-acsm-muted">Proveedores</div>
                      <div className="mt-1 text-lg font-bold text-acsm-ink">
                        {selectedException.supplier_count}
                      </div>
                    </div>
                    <div className="rounded-xl border border-acsm-line bg-white p-3">
                      <div className="text-xs font-bold uppercase text-acsm-muted">Partidas</div>
                      <div className="mt-1 text-lg font-bold text-acsm-ink">
                        {selectedException.item_count}
                      </div>
                    </div>
                    <div className="rounded-xl border border-acsm-line bg-white p-3">
                      <div className="text-xs font-bold uppercase text-acsm-muted">Estado</div>
                      <div className="mt-1 text-lg font-bold text-acsm-ink">
                        {statusLabel(selectedException.status)}
                      </div>
                    </div>
                  </div>
                </div>

                <section className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <h4 className="font-bold text-amber-950">Motivo capturado por compras</h4>
                  <p className="mt-2 whitespace-pre-wrap text-sm font-semibold text-amber-900">
                    {selectedException.request_notes}
                  </p>
                </section>

                <section className="overflow-hidden rounded-xl border border-acsm-line">
                  <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3">
                    <h4 className="font-bold text-acsm-ink">Partidas que se desean cotizar</h4>
                    <p className="text-xs text-acsm-muted">
                      Esta aprobacion solo permite crear la solicitud con menos de 3 proveedores.
                    </p>
                  </div>
                  <table className="w-full text-sm">
                    <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                      <tr>
                        <th className="px-4 py-3 text-left">Material</th>
                        <th className="px-4 py-3 text-left">Cantidad</th>
                        <th className="px-4 py-3 text-left">Unidad</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedException.payload_snapshot.items.map((item, index) => (
                        <tr key={`${item.description}-${index}`} className="border-t border-acsm-line">
                          <td className="px-4 py-3 font-semibold">{item.description}</td>
                          <td className="px-4 py-3">{Number(item.quantity).toLocaleString('es-MX')}</td>
                          <td className="px-4 py-3">{item.unit}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>

                <div className="rounded-xl border border-acsm-line bg-white p-4">
                  <label className="block text-sm font-bold text-acsm-ink">
                    Comentarios de decision
                    <textarea
                      value={decisionNotes}
                      onChange={(event) => setDecisionNotes(event.target.value)}
                      rows={3}
                      className="mt-2 w-full rounded-xl border border-acsm-line px-3 py-2 text-sm"
                      placeholder="Motivo de aprobacion o rechazo"
                    />
                  </label>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void approveSelectedException()}
                      className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white hover:bg-acsm-green-hover"
                    >
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Aprobar excepcion
                    </button>
                    <button
                      type="button"
                      onClick={() => void rejectSelectedException()}
                      className="inline-flex h-10 items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 text-sm font-bold text-red-700 hover:bg-red-100"
                    >
                      <XCircle className="h-4 w-4" aria-hidden="true" />
                      Rechazar
                    </button>
                  </div>
                </div>
              </div>
            ) : selectedApproval ? (
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-acsm-muted">
                      Solicitud seleccionada
                    </p>
                    <h3 className="text-2xl font-bold text-acsm-ink">{selectedApproval.rfq.title}</h3>
                    <p className="text-sm text-acsm-muted">
                      {selectedApproval.rfq.rfq_number} · solicitada el{' '}
                      {formatDateTime(selectedApproval.requested_at)}
                    </p>
                    {selectedContext.isException ? (
                      <span className="mt-3 inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800">
                        Aprobacion por excepcion
                      </span>
                    ) : null}
                  </div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <div className="rounded-xl border border-acsm-line bg-white p-3">
                      <div className="text-xs font-bold uppercase text-acsm-muted">Proveedor</div>
                      <div className="mt-1 text-sm font-bold text-acsm-ink">
                        {selectedQuote?.supplier?.name}
                      </div>
                    </div>
                    <div className="rounded-xl border border-acsm-line bg-white p-3">
                      <div className="text-xs font-bold uppercase text-acsm-muted">Total</div>
                      <div className="mt-1 text-sm font-bold text-acsm-ink">
                        {formatMoney(selectedQuote?.subtotal ?? 0)}
                      </div>
                    </div>
                    <div className="rounded-xl border border-acsm-line bg-white p-3">
                      <div className="text-xs font-bold uppercase text-acsm-muted">Entrega</div>
                      <div className="mt-1 text-sm font-bold text-acsm-ink">
                        {selectedQuote?.delivery_days ?? '-'} dias
                      </div>
                    </div>
                    <div className="rounded-xl border border-acsm-line bg-white p-3">
                      <div className="text-xs font-bold uppercase text-acsm-muted">Credito</div>
                      <div className="mt-1 text-sm font-bold text-acsm-ink">
                        {selectedQuote?.payment_terms_days ?? '-'} dias
                      </div>
                    </div>
                  </div>
                </div>

                {selectedContext.isException ? (
                  <section className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                    <h4 className="font-bold text-amber-950">Motivo de excepcion capturado por compras</h4>
                    <p className="mt-2 whitespace-pre-wrap text-sm font-semibold text-amber-900">
                      {selectedContext.notes}
                    </p>
                  </section>
                ) : null}

                <section className="overflow-hidden rounded-xl border border-acsm-line">
                  <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3">
                    <h4 className="font-bold text-acsm-ink">Comparativo recibido</h4>
                    <p className="text-xs text-acsm-muted">
                      Selecciona el proveedor que gerencia autorizara para generar la orden de compra.
                    </p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-[860px] w-full text-sm">
                      <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                        <tr>
                          <th className="px-4 py-3 text-left">Proveedor</th>
                          <th className="px-4 py-3 text-left">Subtotal</th>
                          <th className="px-4 py-3 text-left">Entrega</th>
                          <th className="px-4 py-3 text-left">Credito</th>
                          <th className="px-4 py-3 text-left">Estado</th>
                          <th className="px-4 py-3 text-right">Decision</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.map((row) => {
                          const isRecommended = row.supplier_quote_id === selectedApproval.supplier_quote_id
                          const isSelected = row.supplier_quote_id === selectedQuote?.id
                          return (
                            <tr
                              key={row.supplier_quote_id}
                              onClick={() => setSelectedQuoteId(row.supplier_quote_id)}
                              className={[
                                'cursor-pointer border-t border-acsm-line transition hover:bg-blue-50',
                                isSelected ? 'bg-blue-100/80 shadow-[inset_4px_0_0_#0b74b8]' : '',
                              ].join(' ')}
                          >
                            <td className="px-4 py-3 font-semibold">
                              <div>{row.supplier_name}</div>
                              {isRecommended ? (
                                <span className="mt-1 inline-flex rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-blue-800">
                                  Recomendada por compras
                                </span>
                              ) : null}
                            </td>
                            <td className="px-4 py-3">{formatMoney(row.subtotal)}</td>
                            <td className="px-4 py-3">{row.delivery_days ?? '-'} dias</td>
                            <td className="px-4 py-3">{row.payment_terms_days} dias</td>
                            <td className="px-4 py-3">{statusLabel(row.status)}</td>
                            <td className="px-4 py-3 text-right">
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  setSelectedQuoteId(row.supplier_quote_id)
                                }}
                                className={[
                                  'inline-flex h-8 items-center rounded-full border px-3 text-xs font-bold',
                                  isSelected
                                    ? 'border-blue-500 bg-blue-600 text-white'
                                    : 'border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper',
                                ].join(' ')}
                              >
                                {isSelected ? 'Seleccionada' : 'Elegir'}
                              </button>
                            </td>
                          </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>

                <section className="overflow-hidden rounded-xl border border-acsm-line">
                  <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3 font-bold text-acsm-ink">
                    Partidas de la cotizacion seleccionada
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-[820px] w-full text-sm">
                      <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                        <tr>
                          <th className="px-4 py-3 text-left">Material</th>
                          <th className="px-4 py-3 text-left">Cantidad</th>
                          <th className="px-4 py-3 text-left">Precio unitario</th>
                          <th className="px-4 py-3 text-left">Importe</th>
                          <th className="px-4 py-3 text-left">Entrega partida</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(selectedQuote?.items ?? []).map((item) => (
                          <tr key={item.id} className="border-t border-acsm-line">
                            <td className="px-4 py-3 font-semibold">{item.description}</td>
                            <td className="px-4 py-3">
                              {Number(item.quantity).toLocaleString('es-MX')} {item.unit}
                            </td>
                            <td className="px-4 py-3">{formatMoney(item.unit_price)}</td>
                            <td className="px-4 py-3">{formatMoney(item.line_total)}</td>
                            <td className="px-4 py-3">{item.delivery_days ?? '-'} dias</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                <div className="rounded-xl border border-acsm-line bg-white p-4">
                  <label className="block text-sm font-bold text-acsm-ink">
                    Comentarios de decision
                    <textarea
                      value={decisionNotes}
                      onChange={(event) => setDecisionNotes(event.target.value)}
                      rows={3}
                      className="mt-2 w-full rounded-xl border border-acsm-line px-3 py-2 text-sm"
                      placeholder="Motivo de aprobacion o rechazo"
                    />
                  </label>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void approveSelected()}
                      disabled={!selectedQuote}
                      className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white hover:bg-acsm-green-hover disabled:opacity-60"
                    >
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Aprobar cotizacion seleccionada y generar OC
                    </button>
                    <button
                      type="button"
                      onClick={() => void rejectSelected()}
                      className="inline-flex h-10 items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 text-sm font-bold text-red-700 hover:bg-red-100"
                    >
                      <XCircle className="h-4 w-4" aria-hidden="true" />
                      Rechazar
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[360px] items-center justify-center rounded-xl border border-dashed border-acsm-line text-sm text-acsm-muted">
                Selecciona una cotizacion pendiente para revisar.
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
