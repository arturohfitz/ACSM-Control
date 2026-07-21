import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, History, RotateCcw, XCircle } from 'lucide-react'

import { apiRequest } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'

type Invoice = {
  id: number
  invoice_number: string
  subtotal?: string | null
  total: string
  status: string
  purchase_order_id: number
  purchase_order?: { id: number; project_id: number; po_number: string; subtotal: string } | null
}

type Payment = {
  id: number
  supplier_invoice_id: number
  amount: string
  status: string
  reference?: string | null
}

type ReconciliationCase = {
  id: number
  project_id: number
  project_name: string
  purchase_order_number: string
  supplier_invoice_id: number
  invoice_number: string
  supplier_payment_id?: number | null
  payment_reference?: string | null
  case_number: string
  issue_type: string
  resolution_type: Resolution
  status: 'requested' | 'applied' | 'rejected'
  reason: string
  proposed_data: Record<string, string>
  decision_notes?: string | null
  requester_name?: string | null
  requested_at: string
  decider_name?: string | null
}

type Resolution = 'correct_invoice' | 'amend_purchase_order' | 'reverse_payment' | 'cancel_invoice'

type Props = {
  invoices: Invoice[]
  payments: Payment[]
  selectedProjectId: string
  canView: boolean
  canRequest: boolean
  canApprove: boolean
  onApplied: () => Promise<void> | void
}

const resolutionLabels: Record<Resolution, string> = {
  correct_invoice: 'Corregir importes de factura',
  amend_purchase_order: 'Autorizar adenda de la OC',
  reverse_payment: 'Revertir pago aplicado',
  cancel_invoice: 'Cancelar factura',
}

const statusLabels = { requested: 'Pendiente de autorización', applied: 'Aplicada', rejected: 'Rechazada' }

export default function FinancialReconciliationPanel({
  invoices,
  payments,
  selectedProjectId,
  canView,
  canRequest,
  canApprove,
  onApplied,
}: Props) {
  const [cases, setCases] = useState<ReconciliationCase[]>([])
  const [showForm, setShowForm] = useState(false)
  const [invoiceId, setInvoiceId] = useState('')
  const [resolution, setResolution] = useState<Resolution>('correct_invoice')
  const [paymentId, setPaymentId] = useState('')
  const [reason, setReason] = useState('')
  const [correctedSubtotal, setCorrectedSubtotal] = useState('')
  const [correctedTotal, setCorrectedTotal] = useState('')
  const [correctedDiscount, setCorrectedDiscount] = useState('0')
  const [transferredTaxes, setTransferredTaxes] = useState('0')
  const [withheldTaxes, setWithheldTaxes] = useState('0')
  const [amendedSubtotal, setAmendedSubtotal] = useState('')
  const [decisionNotes, setDecisionNotes] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const eligibleInvoices = useMemo(
    () => invoices.filter(
      (invoice) => !['rejected', 'cancelled'].includes(invoice.status)
        && (!selectedProjectId || String(invoice.purchase_order?.project_id) === selectedProjectId),
    ),
    [invoices, selectedProjectId],
  )
  const selectedInvoice = useMemo(
    () => eligibleInvoices.find((invoice) => String(invoice.id) === invoiceId) ?? null,
    [eligibleInvoices, invoiceId],
  )
  const paidPayments = useMemo(
    () => payments.filter((payment) => payment.supplier_invoice_id === Number(invoiceId) && payment.status === 'paid'),
    [invoiceId, payments],
  )

  async function loadCases() {
    if (!canView) return
    const query = selectedProjectId ? `?project_id=${selectedProjectId}` : ''
    try {
      setCases(await apiRequest<ReconciliationCase[]>(`/purchasing/financial-reconciliations${query}`))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar las conciliaciones')
    }
  }

  useEffect(() => {
    void loadCases()
  }, [canView, selectedProjectId])

  useEffect(() => {
    const requestedCaseId = new URLSearchParams(window.location.search).get('reconciliation_id')
    if (!requestedCaseId || !cases.some((item) => String(item.id) === requestedCaseId)) return
    window.requestAnimationFrame(() => {
      document.getElementById(`financial-reconciliation-${requestedCaseId}`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    })
  }, [cases])

  useEffect(() => {
    if (!selectedInvoice) return
    setCorrectedSubtotal(selectedInvoice.subtotal ?? '')
    setCorrectedTotal(selectedInvoice.total)
    setAmendedSubtotal(selectedInvoice.purchase_order?.subtotal ?? '')
  }, [selectedInvoice])

  async function requestCase() {
    if (!invoiceId || reason.trim().length < 10) {
      setError('Selecciona la factura y explica el motivo con al menos 10 caracteres.')
      return
    }
    const payload: Record<string, unknown> = {
      supplier_invoice_id: Number(invoiceId),
      issue_type: 'amount_mismatch',
      resolution_type: resolution,
      reason: reason.trim(),
    }
    if (resolution === 'correct_invoice') {
      Object.assign(payload, {
        corrected_subtotal: correctedSubtotal,
        corrected_total: correctedTotal,
        corrected_discount: correctedDiscount || '0',
        corrected_transferred_taxes: transferredTaxes || '0',
        corrected_withheld_taxes: withheldTaxes || '0',
      })
    }
    if (resolution === 'amend_purchase_order') payload.amended_purchase_order_subtotal = amendedSubtotal
    if (resolution === 'reverse_payment') payload.supplier_payment_id = Number(paymentId)
    setBusy(true)
    setError('')
    try {
      await apiRequest('/purchasing/financial-reconciliations', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      showActionNotice('Conciliación enviada a Administración para autorización.')
      setShowForm(false)
      setReason('')
      await loadCases()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible solicitar la conciliación')
    } finally {
      setBusy(false)
    }
  }

  async function decide(item: ReconciliationCase, decision: 'approved' | 'rejected') {
    const notes = decisionNotes[item.id]?.trim() ?? ''
    if (notes.length < 5) {
      setError('Captura una nota de decisión de al menos 5 caracteres.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await apiRequest(`/purchasing/financial-reconciliations/${item.id}/decision`, {
        method: 'POST',
        body: JSON.stringify({ decision, notes }),
      })
      showActionNotice(
        decision === 'approved' ? 'Conciliación autorizada y aplicada.' : 'Conciliación rechazada.',
        decision === 'approved' ? 'success' : 'warning',
      )
      await Promise.all([loadCases(), Promise.resolve(onApplied())])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible resolver la conciliación')
    } finally {
      setBusy(false)
    }
  }

  if (!canView) return null

  return (
    <section id="financial-reconciliations" className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line bg-acsm-paper px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-amber-200 bg-amber-50 text-amber-700">
            <History className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-acsm-muted">Control financiero</div>
            <h2 className="font-semibold text-acsm-ink">Conciliaciones y correcciones</h2>
            <p className="text-xs text-acsm-muted">Corrige excepciones sin borrar el historial original.</p>
          </div>
        </div>
        {canRequest && (
          <button
            type="button"
            onClick={() => setShowForm((current) => !current)}
            className="inline-flex h-9 items-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            {showForm ? 'Cerrar captura' : 'Solicitar corrección'}
          </button>
        )}
      </div>

      {error && <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">{error}</div>}

      {showForm && (
        <div className="grid gap-3 border-b border-acsm-line p-4 lg:grid-cols-2">
          <label className="text-xs font-semibold uppercase text-acsm-muted">
            Factura afectada
            <select value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)} className="mt-1 h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm normal-case text-acsm-ink">
              <option value="">Seleccionar factura</option>
              {eligibleInvoices.map((invoice) => (
                <option key={invoice.id} value={invoice.id}>{invoice.invoice_number} · {invoice.purchase_order?.po_number ?? invoice.purchase_order_id} · {invoice.total}</option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold uppercase text-acsm-muted">
            Acción correctiva
            <select value={resolution} onChange={(event) => setResolution(event.target.value as Resolution)} className="mt-1 h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm normal-case text-acsm-ink">
              {Object.entries(resolutionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>

          {resolution === 'correct_invoice' && (
            <div className="grid gap-2 lg:col-span-2 sm:grid-cols-5">
              {[
                ['Subtotal corregido', correctedSubtotal, setCorrectedSubtotal],
                ['Descuento', correctedDiscount, setCorrectedDiscount],
                ['Impuestos trasladados', transferredTaxes, setTransferredTaxes],
                ['Impuestos retenidos', withheldTaxes, setWithheldTaxes],
                ['Total fiscal corregido', correctedTotal, setCorrectedTotal],
              ].map(([label, value, setter]) => (
                <label key={label as string} className="text-xs font-semibold uppercase text-acsm-muted">
                  {label as string}
                  <input type="number" min="0" step="0.01" value={value as string} onChange={(event) => (setter as (value: string) => void)(event.target.value)} className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm normal-case text-acsm-ink" />
                </label>
              ))}
            </div>
          )}
          {resolution === 'amend_purchase_order' && (
            <label className="text-xs font-semibold uppercase text-acsm-muted lg:col-span-2">
              Nuevo subtotal autorizado de la OC
              <input type="number" min="0" step="0.01" value={amendedSubtotal} onChange={(event) => setAmendedSubtotal(event.target.value)} className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm normal-case text-acsm-ink" />
            </label>
          )}
          {resolution === 'reverse_payment' && (
            <label className="text-xs font-semibold uppercase text-acsm-muted lg:col-span-2">
              Pago realizado a revertir
              <select value={paymentId} onChange={(event) => setPaymentId(event.target.value)} className="mt-1 h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm normal-case text-acsm-ink">
                <option value="">Seleccionar pago</option>
                {paidPayments.map((payment) => <option key={payment.id} value={payment.id}>{payment.reference || `Pago ${payment.id}`} · {payment.amount}</option>)}
              </select>
            </label>
          )}
          <label className="text-xs font-semibold uppercase text-acsm-muted lg:col-span-2">
            Motivo y evidencia de la corrección
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} placeholder="Describe qué ocurrió, qué comprobante lo demuestra y por qué procede la corrección." className="mt-1 w-full rounded-md border border-acsm-line px-3 py-2 text-sm normal-case text-acsm-ink" />
          </label>
          <div className="flex justify-end lg:col-span-2">
            <button type="button" onClick={() => void requestCase()} disabled={busy} className="inline-flex h-10 items-center gap-2 rounded-md bg-acsm-green px-5 text-sm font-semibold text-white disabled:opacity-60">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Enviar a autorización
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-acsm-line">
        {cases.map((item) => (
          <article
            id={`financial-reconciliation-${item.id}`}
            key={item.id}
            className={item.status === 'requested' ? 'scroll-mt-24 bg-amber-50/40 px-4 py-3' : 'scroll-mt-24 px-4 py-3'}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-bold text-acsm-ink">{item.case_number}</span>
                  <span className="rounded-full border border-acsm-line bg-white px-2 py-0.5 text-xs font-semibold text-acsm-muted">{statusLabels[item.status]}</span>
                </div>
                <div className="mt-1 text-sm font-semibold text-acsm-ink">{resolutionLabels[item.resolution_type]}</div>
                <div className="text-xs text-acsm-muted">{item.project_name} · {item.purchase_order_number} · {item.invoice_number}</div>
                <p className="mt-2 max-w-4xl text-sm text-acsm-muted">{item.reason}</p>
                <div className="mt-1 text-xs text-acsm-muted">Solicitó {item.requester_name ?? 'Usuario'} · {new Date(item.requested_at).toLocaleString('es-MX')}</div>
              </div>
              {item.status !== 'requested' && <div className="text-right text-xs text-acsm-muted">{item.decision_notes}<br />{item.decider_name}</div>}
            </div>
            {canApprove && item.status === 'requested' && (
              <div className="mt-3 flex flex-col gap-2 border-t border-amber-200 pt-3 sm:flex-row">
                <input value={decisionNotes[item.id] ?? ''} onChange={(event) => setDecisionNotes((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="Nota obligatoria de Administración" className="h-9 min-w-0 flex-1 rounded-md border border-acsm-line bg-white px-3 text-sm" />
                <button type="button" disabled={busy} onClick={() => void decide(item, 'rejected')} className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-red-200 bg-white px-3 text-sm font-semibold text-red-700"><XCircle className="h-4 w-4" />Rechazar</button>
                <button type="button" disabled={busy} onClick={() => void decide(item, 'approved')} className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-acsm-green px-3 text-sm font-semibold text-white"><CheckCircle2 className="h-4 w-4" />Autorizar y aplicar</button>
              </div>
            )}
          </article>
        ))}
        {!cases.length && <div className="px-4 py-6 text-center text-sm text-acsm-muted">No hay conciliaciones registradas para el proyecto seleccionado.</div>}
      </div>
    </section>
  )
}
