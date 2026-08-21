import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  FileText,
  PackageCheck,
  ReceiptText,
  ShieldCheck,
  Upload,
} from 'lucide-react'
import { useParams } from 'react-router-dom'

import MexicanNumberInput from '../components/MexicanNumberInput'
import { brand } from '../config/brand'
import { apiRequest } from '../lib/api'
import { formatMexicanMoney, formatMexicanNumber } from '../lib/numberFormat'

type PortalItem = {
  id: number
  description: string
  unit: string
  ordered: string
  received: string
  invoiced: string
  available: string
  unit_price: string
}

type PortalSubmission = {
  id: number
  invoice_number?: string | null
  submitted_at: string
  status: string
  total?: string | null
  validation_message?: string | null
  documents: { id: number; document_type: string; original_file_name: string; file_size: number }[]
}

type PortalOrder = {
  purchase_order_id: number
  po_number: string
  status: string
  supplier_name: string
  project_name: string
  issued_at: string
  subtotal: string
  currency: string
  items: PortalItem[]
  submissions: PortalSubmission[]
}

function formatDate(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return value
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(new Date(year, month - 1, day))
}

function submissionLabel(status: string) {
  if (status === 'registered') return 'Registrada'
  if (status === 'rejected') return 'Correccion solicitada'
  return 'En revision'
}

export default function SupplierInvoicePortalPage() {
  const { token = '' } = useParams()
  const [data, setData] = useState<PortalOrder | null>(null)
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [invoiceDate, setInvoiceDate] = useState('')
  const [currency, setCurrency] = useState('MXN')
  const [subtotal, setSubtotal] = useState('')
  const [total, setTotal] = useState('')
  const [notes, setNotes] = useState('')
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [xmlFile, setXmlFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [fileKey, setFileKey] = useState(0)

  const availableAmount = useMemo(
    () => data?.items.reduce(
      (sum, item) => sum + Number(item.available || 0) * Number(item.unit_price || 0),
      0,
    ) ?? 0,
    [data],
  )

  async function loadPortal() {
    setLoading(true)
    setError('')
    try {
      setData(await apiRequest<PortalOrder>(`/supplier-invoice-portal/${token}`))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible abrir la orden de compra')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadPortal()
  }, [token])

  async function submitInvoice() {
    if (!pdfFile && !xmlFile) {
      setError('Adjunta al menos el PDF o el XML de la factura.')
      return
    }
    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      const formData = new FormData()
      if (invoiceNumber.trim()) formData.append('invoice_number', invoiceNumber.trim())
      if (invoiceDate) formData.append('invoice_date', invoiceDate)
      formData.append('currency', currency)
      if (subtotal) formData.append('subtotal', subtotal)
      if (total) formData.append('total', total)
      if (notes.trim()) formData.append('notes', notes.trim())
      if (pdfFile) formData.append('pdf_file', pdfFile)
      if (xmlFile) formData.append('xml_file', xmlFile)
      await apiRequest(`/supplier-invoice-portal/${token}/submissions`, {
        method: 'POST',
        body: formData,
      })
      setMessage('Documentos recibidos. Compras fue notificado y revisara la factura antes de registrarla.')
      setInvoiceNumber('')
      setInvoiceDate('')
      setSubtotal('')
      setTotal('')
      setNotes('')
      setPdfFile(null)
      setXmlFile(null)
      setFileKey((current) => current + 1)
      await loadPortal()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la factura')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#09192a] px-4 py-7 text-acsm-ink">
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-md border border-sky-200 bg-white px-5 py-4 shadow-panel">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-md border border-sky-200 bg-sky-50 text-sky-700">
              <Building2 className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-sky-700">Portal de proveedores</p>
              <h1 className="text-xl font-bold">{brand.appName}</h1>
            </div>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Envio seguro
          </span>
        </header>

        {loading ? (
          <section className="rounded-md border border-acsm-line bg-white p-8 text-center shadow-panel">Cargando orden...</section>
        ) : error && !data ? (
          <section className="rounded-md border border-red-200 bg-red-50 p-6 text-red-700 shadow-panel">
            <div className="flex items-center gap-2 font-bold"><AlertTriangle className="h-5 w-5" />{error}</div>
          </section>
        ) : data ? (
          <>
            {message && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800">{message}</div>}
            {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>}

            <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-acsm-paper px-5 py-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-acsm-muted">Orden autorizada</p>
                  <h2 className="mt-1 text-xl font-bold">{data.po_number}</h2>
                  <p className="text-sm text-acsm-muted">{data.supplier_name} · {data.project_name}</p>
                </div>
                <div className="text-right text-sm">
                  <div className="font-bold">{formatMexicanMoney(data.subtotal)}</div>
                  <div className="text-acsm-muted">Emitida {formatDate(data.issued_at)}</div>
                </div>
              </div>
              <div className="grid gap-3 p-4 sm:grid-cols-3">
                <div className="rounded-md border border-acsm-line p-3"><p className="text-xs font-bold uppercase text-acsm-muted">Partidas</p><p className="mt-1 text-lg font-bold">{data.items.length}</p></div>
                <div className="rounded-md border border-blue-200 bg-blue-50 p-3"><p className="text-xs font-bold uppercase text-blue-700">Disponible para facturar</p><p className="mt-1 text-lg font-bold text-blue-950">{formatMexicanMoney(availableAmount)}</p></div>
                <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3"><p className="text-xs font-bold uppercase text-emerald-700">Entregas fiscales</p><p className="mt-1 text-lg font-bold text-emerald-900">{data.submissions.length}</p></div>
              </div>
              <div className="overflow-x-auto border-t border-acsm-line">
                <table className="min-w-[760px] w-full text-sm">
                  <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted"><tr><th className="px-4 py-3 text-left">Material</th><th className="px-4 py-3 text-right">Ordenado</th><th className="px-4 py-3 text-right">Recibido</th><th className="px-4 py-3 text-right">Facturado</th><th className="px-4 py-3 text-right">Disponible</th></tr></thead>
                  <tbody>{data.items.map((item) => <tr key={item.id} className="border-t border-acsm-line"><td className="px-4 py-3 font-semibold">{item.description}</td><td className="px-4 py-3 text-right">{formatMexicanNumber(item.ordered)} {item.unit}</td><td className="px-4 py-3 text-right">{formatMexicanNumber(item.received)} {item.unit}</td><td className="px-4 py-3 text-right">{formatMexicanNumber(item.invoiced)} {item.unit}</td><td className="px-4 py-3 text-right font-bold text-blue-800">{formatMexicanNumber(item.available)} {item.unit}</td></tr>)}</tbody>
                </table>
              </div>
            </section>

            <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
              <div className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
                <div className="border-b border-acsm-line bg-acsm-paper px-5 py-4">
                  <h2 className="flex items-center gap-2 font-bold"><ReceiptText className="h-5 w-5 text-sky-700" />Enviar factura</h2>
                  <p className="text-sm text-acsm-muted">Adjunta PDF, XML o ambos. El XML alimenta los datos fiscales cuando esta disponible.</p>
                </div>
                <div className="grid gap-3 p-5 sm:grid-cols-2">
                  <label className="text-sm font-semibold">Folio<input value={invoiceNumber} onChange={(event) => setInvoiceNumber(event.target.value)} className="mt-1 h-11 w-full rounded-md border border-acsm-line px-3" /></label>
                  <label className="text-sm font-semibold">Fecha<input type="date" value={invoiceDate} onChange={(event) => setInvoiceDate(event.target.value)} className="mt-1 h-11 w-full rounded-md border border-acsm-line px-3" /></label>
                  <label className="text-sm font-semibold">Moneda<select value={currency} onChange={(event) => setCurrency(event.target.value)} className="mt-1 h-11 w-full rounded-md border border-acsm-line bg-white px-3"><option value="MXN">MXN</option><option value="USD">USD</option></select></label>
                  <label className="text-sm font-semibold">Subtotal<MexicanNumberInput min="0" step="0.01" value={subtotal} onChange={(event) => setSubtotal(event.target.value)} className="mt-1 h-11 w-full rounded-md border border-acsm-line px-3" /></label>
                  <label className="text-sm font-semibold sm:col-start-2">Total<MexicanNumberInput min="0" step="0.01" value={total} onChange={(event) => setTotal(event.target.value)} className="mt-1 h-11 w-full rounded-md border border-acsm-line px-3" /></label>
                  <label className="flex min-h-20 cursor-pointer items-center gap-3 rounded-md border border-dashed border-red-200 bg-red-50 px-4 py-3"><FileText className="h-5 w-5 text-red-600" /><span className="min-w-0"><span className="block font-bold">Factura PDF</span><span className="block truncate text-xs text-acsm-muted">{pdfFile?.name ?? 'Seleccionar PDF'}</span></span><input key={`pdf-${fileKey}`} type="file" accept="application/pdf,.pdf" className="sr-only" onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)} /></label>
                  <label className="flex min-h-20 cursor-pointer items-center gap-3 rounded-md border border-dashed border-blue-200 bg-blue-50 px-4 py-3"><Upload className="h-5 w-5 text-blue-700" /><span className="min-w-0"><span className="block font-bold">Factura XML</span><span className="block truncate text-xs text-acsm-muted">{xmlFile?.name ?? 'Seleccionar XML'}</span></span><input key={`xml-${fileKey}`} type="file" accept="application/xml,text/xml,.xml" className="sr-only" onChange={(event) => setXmlFile(event.target.files?.[0] ?? null)} /></label>
                  <label className="text-sm font-semibold sm:col-span-2">Notas<textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} className="mt-1 w-full rounded-md border border-acsm-line p-3" placeholder="Referencia, entrega o aclaracion para Compras" /></label>
                  <button type="button" onClick={() => void submitInvoice()} disabled={submitting || (!pdfFile && !xmlFile)} className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-sky-700 px-5 font-bold text-white hover:bg-sky-800 disabled:opacity-60 sm:col-span-2"><Upload className="h-4 w-4" />{submitting ? 'Enviando...' : 'Enviar documentos a Compras'}</button>
                </div>
              </div>

              <aside className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
                <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3"><h2 className="flex items-center gap-2 font-bold"><PackageCheck className="h-4 w-4 text-emerald-700" />Historial</h2></div>
                <div className="divide-y divide-acsm-line">
                  {data.submissions.map((submission) => (
                    <div key={submission.id} className="p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-bold">{submission.invoice_number || 'Sin folio'}</p>
                          <p className="text-xs text-acsm-muted">
                            {new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(submission.submitted_at))}
                          </p>
                        </div>
                        <span className="rounded-full border border-acsm-line px-2 py-1 text-[11px] font-bold">
                          {submissionLabel(submission.status)}
                        </span>
                      </div>
                      {submission.status === 'rejected' && submission.validation_message && (
                        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                          <strong>Correccion solicitada:</strong> {submission.validation_message}
                        </div>
                      )}
                      <div className="mt-2 space-y-1 text-xs text-acsm-muted">
                        {submission.documents.map((document) => (
                          <div key={document.id}>
                            {document.document_type.toUpperCase()} · {document.original_file_name}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                  {!data.submissions.length && <div className="p-6 text-center text-sm text-acsm-muted"><CheckCircle2 className="mx-auto mb-2 h-5 w-5" />Aun no hay documentos enviados.</div>}
                </div>
              </aside>
            </section>
          </>
        ) : null}
      </div>
    </main>
  )
}
