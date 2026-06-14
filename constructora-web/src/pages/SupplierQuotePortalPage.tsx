import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Building2, CheckCircle2, FileUp, ShieldCheck } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { apiRequest } from '../lib/api'
import { brand } from '../config/brand'

type PortalItem = {
  id: number
  description: string
  unit: string
  quantity: string
  notes?: string | null
}

type PortalUpload = {
  id: number
  quote_number?: string | null
  original_file_name: string
  file_size_bytes: number
  uploaded_at: string
  status: string
}

type PortalRFQ = {
  rfq_number: string
  title: string
  required_by?: string | null
  response_deadline?: string | null
  supplier_name: string
  items: PortalItem[]
  previous_uploads: PortalUpload[]
}

function formatDate(value?: string | null) {
  if (!value) return 'Sin fecha definida'
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return value
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  )
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('es-MX', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

export default function SupplierQuotePortalPage() {
  const { token = '' } = useParams()
  const [data, setData] = useState<PortalRFQ | null>(null)
  const [quoteNumber, setQuoteNumber] = useState('')
  const [notes, setNotes] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const sortedUploads = useMemo(
    () => [...(data?.previous_uploads ?? [])].sort((left, right) => right.id - left.id),
    [data?.previous_uploads],
  )

  async function loadPortal() {
    setLoading(true)
    setError('')
    try {
      const response = await apiRequest<PortalRFQ>(`/supplier-portal/quotes/${token}`)
      setData(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar la solicitud')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadPortal()
  }, [token])

  async function submitUpload() {
    if (!file) {
      setError('Selecciona un archivo PDF, XLS o XLSX.')
      return
    }
    setSubmitting(true)
    setError('')
    setMessage('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('quote_number', quoteNumber)
      formData.append('notes', notes)
      await apiRequest<PortalUpload>(`/supplier-portal/quotes/${token}/uploads`, {
        method: 'POST',
        body: formData,
      })
      setMessage('Cotizacion cargada correctamente. ACSM ya puede revisarla.')
      setQuoteNumber('')
      setNotes('')
      setFile(null)
      await loadPortal()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar el archivo')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_85%_10%,rgba(56,126,195,0.25),transparent_26rem),linear-gradient(135deg,#081321_0%,#0d2139_55%,#17212e_100%)] px-4 py-8 text-acsm-ink">
      <div className="mx-auto max-w-5xl space-y-5">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-white/15 bg-white/10 px-5 py-4 text-white shadow-panel backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/20 bg-white/10">
              <Building2 className="h-6 w-6" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-sky-200">
                Portal de proveedores
              </p>
              <h1 className="text-xl font-bold">{brand.appName}</h1>
            </div>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-300/40 bg-emerald-400/10 px-3 py-2 text-sm font-semibold text-emerald-100">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Carga segura
          </div>
        </header>

        {loading ? (
          <section className="rounded-[24px] border border-acsm-line bg-white p-8 text-center shadow-panel">
            Cargando solicitud...
          </section>
        ) : error && !data ? (
          <section className="rounded-[24px] border border-red-200 bg-red-50 p-8 text-red-700 shadow-panel">
            <div className="flex items-center gap-3 font-bold">
              <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              {error}
            </div>
          </section>
        ) : data ? (
          <>
            {message ? (
              <div className="rounded-[18px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-700">
                {message}
              </div>
            ) : null}
            {error ? (
              <div className="rounded-[18px] border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">
                {error}
              </div>
            ) : null}

            <section className="overflow-hidden rounded-[24px] border border-acsm-line bg-white shadow-panel">
              <div className="border-b border-acsm-line bg-acsm-paper px-5 py-4">
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">
                  Solicitud de cotizacion
                </p>
                <h2 className="mt-1 text-2xl font-bold">{data.title}</h2>
                <p className="text-sm text-acsm-muted">
                  {data.rfq_number} · Proveedor: <span className="font-semibold">{data.supplier_name}</span>
                </p>
              </div>
              <div className="grid gap-3 p-5 md:grid-cols-3">
                <div className="rounded-2xl border border-acsm-line bg-white p-4">
                  <p className="text-xs font-bold uppercase text-acsm-muted">Fecha requerida</p>
                  <p className="mt-1 font-bold">{formatDate(data.required_by)}</p>
                </div>
                <div className="rounded-2xl border border-acsm-line bg-white p-4">
                  <p className="text-xs font-bold uppercase text-acsm-muted">Limite de respuesta</p>
                  <p className="mt-1 font-bold">{formatDate(data.response_deadline)}</p>
                </div>
                <div className="rounded-2xl border border-acsm-line bg-white p-4">
                  <p className="text-xs font-bold uppercase text-acsm-muted">Partidas</p>
                  <p className="mt-1 font-bold">{data.items.length}</p>
                </div>
              </div>
            </section>

            <section className="overflow-hidden rounded-[24px] border border-acsm-line bg-white shadow-panel">
              <div className="border-b border-acsm-line bg-acsm-paper px-5 py-4">
                <h2 className="font-bold">Materiales solicitados</h2>
                <p className="text-sm text-acsm-muted">Cotiza cada partida con la unidad indicada.</p>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-[720px] w-full text-sm">
                  <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                    <tr>
                      <th className="px-4 py-3 text-left">Material</th>
                      <th className="px-4 py-3 text-left">Cantidad</th>
                      <th className="px-4 py-3 text-left">Unidad</th>
                      <th className="px-4 py-3 text-left">Notas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item) => (
                      <tr key={item.id} className="border-t border-acsm-line">
                        <td className="px-4 py-3 font-semibold">{item.description}</td>
                        <td className="px-4 py-3">{Number(item.quantity).toLocaleString('es-MX')}</td>
                        <td className="px-4 py-3">{item.unit}</td>
                        <td className="px-4 py-3 text-acsm-muted">{item.notes || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
              <div className="overflow-hidden rounded-[24px] border border-acsm-line bg-white shadow-panel">
                <div className="border-b border-acsm-line bg-acsm-paper px-5 py-4">
                  <h2 className="font-bold">Cargar cotizacion</h2>
                  <p className="text-sm text-acsm-muted">
                    Se aceptan PDF, XLS y XLSX. Maximo 15 MB. Archivos con macros, scripts o vinculos externos se rechazan.
                  </p>
                </div>
                <div className="space-y-4 p-5">
                  <label className="block text-sm font-semibold">
                    Folio de cotizacion
                    <input
                      value={quoteNumber}
                      onChange={(event) => setQuoteNumber(event.target.value)}
                      placeholder="Ej. COT-2026-001"
                      className="mt-1 h-11 w-full rounded-md border border-acsm-line px-3"
                    />
                  </label>
                  <label className="block text-sm font-semibold">
                    Archivo
                    <input
                      type="file"
                      accept=".pdf,.xls,.xlsx,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                      onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                      className="mt-1 w-full rounded-md border border-acsm-line px-3 py-2"
                    />
                  </label>
                  <label className="block text-sm font-semibold">
                    Notas
                    <textarea
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      placeholder="Comentarios opcionales para ACSM"
                      className="mt-1 min-h-24 w-full rounded-md border border-acsm-line px-3 py-2"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => void submitUpload()}
                    disabled={submitting || !file}
                    className="inline-flex h-11 items-center gap-2 rounded-md bg-acsm-green px-5 text-sm font-bold text-white hover:bg-acsm-green-hover disabled:opacity-60"
                  >
                    <FileUp className="h-4 w-4" aria-hidden="true" />
                    {submitting ? 'Cargando...' : 'Cargar cotizacion'}
                  </button>
                </div>
              </div>

              <aside className="overflow-hidden rounded-[24px] border border-acsm-line bg-white shadow-panel">
                <div className="border-b border-acsm-line bg-acsm-paper px-5 py-4">
                  <h2 className="font-bold">Cargas previas</h2>
                  <p className="text-sm text-acsm-muted">Historial de archivos recibidos en esta liga.</p>
                </div>
                <div className="divide-y divide-acsm-line">
                  {sortedUploads.map((upload) => (
                    <div key={upload.id} className="p-4">
                      <div className="flex items-start gap-2">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" aria-hidden="true" />
                        <div className="min-w-0">
                          <p className="break-words text-sm font-bold">{upload.original_file_name}</p>
                          <p className="text-xs text-acsm-muted">
                            {upload.quote_number || 'Sin folio'} · {formatBytes(upload.file_size_bytes)}
                          </p>
                          <p className="mt-1 text-xs text-acsm-muted">{formatDateTime(upload.uploaded_at)}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                  {!sortedUploads.length ? (
                    <div className="p-6 text-center text-sm text-acsm-muted">
                      Aun no hay archivos cargados.
                    </div>
                  ) : null}
                </div>
              </aside>
            </section>
          </>
        ) : null}
      </div>
    </main>
  )
}
