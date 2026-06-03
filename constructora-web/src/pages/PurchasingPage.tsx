import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  ClipboardCheck,
  Eye,
  Plus,
  Printer,
  RefreshCw,
  Send,
  ShoppingCart,
  Trash2,
  X,
} from 'lucide-react'

import { apiRequest } from '../lib/api'

type Project = {
  id: number
  name: string
}

type Material = {
  id: number
  name: string
  unit: string
}

type Supplier = {
  id: number
  name: string
  payment_terms_days: number
  average_delivery_days?: number | null
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

type RFQSupplierLink = {
  supplier_id: number
  status: string
  supplier?: Supplier | null
}

type SupplierRFQ = {
  id: number
  project_id: number
  rfq_number: string
  title: string
  status: string
  created_at: string
  created_by?: number | null
  creator?: UserSummary | null
  required_by?: string | null
  response_deadline?: string | null
  items: RFQItem[]
  supplier_links: RFQSupplierLink[]
}

type SupplierRFQException = {
  id: number
  project_id: number
  rfq_id?: number | null
  title: string
  status: string
  required_by?: string | null
  response_deadline?: string | null
  supplier_count: number
  item_count: number
  payload_snapshot: {
    project_id: number
    title: string
    required_by?: string | null
    response_deadline?: string | null
    supplier_ids: number[]
    items: {
      material_id?: number | null
      source_code?: string | null
      description: string
      unit: string
      quantity: string
      notes?: string | null
    }[]
  }
  request_notes: string
  decision_notes?: string | null
  requested_at: string
  requester?: UserSummary | null
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
}

type ComparisonRow = {
  supplier_quote_id: number
  supplier_id: number
  supplier_name: string
  subtotal: string
  delivery_days?: number | null
  payment_terms_days: number
  status: string
  complete_items: number
  total_items: number
}

type PurchaseOrder = {
  id: number
  supplier_id: number
  po_number: string
  status: string
  issued_at: string
  expected_delivery_date?: string | null
  subtotal: string
  supplier?: Supplier | null
  items: {
    id: number
    description: string
    quantity_ordered: string
    received_quantity: string
    unit: string
    status: string
  }[]
}

type RFQDraftItem = {
  material_id: string
  material_search: string
  description: string
  unit: string
  quantity: string
  notes: string
}

type QuoteDraftItem = {
  rfq_item_id: number
  unit_price: string
  delivery_days: string
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

function formatDate(value?: string | null) {
  if (!value) return '-'
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return value
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  )
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
      .join(',')}}`
  }
  return JSON.stringify(value)
}

function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function printRfqDocument(rfq: SupplierRFQ) {
  const popup = window.open('', '_blank', 'width=920,height=720')
  if (!popup) return
  const suppliers = rfq.supplier_links
    .map(
      (link) => `
        <tr>
          <td>${escapeHtml(link.supplier?.name ?? `Proveedor ${link.supplier_id}`)}</td>
          <td>${escapeHtml(link.supplier?.payment_terms_days ?? 0)} dias credito</td>
          <td>${escapeHtml(statusLabel(link.status))}</td>
        </tr>
      `,
    )
    .join('')
  const items = rfq.items
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.description)}</td>
          <td>${escapeHtml(Number(item.quantity).toLocaleString('es-MX'))}</td>
          <td>${escapeHtml(item.unit)}</td>
        </tr>
      `,
    )
    .join('')
  popup.document.write(`
    <!doctype html>
    <html>
      <head>
        <title>${escapeHtml(rfq.rfq_number)}</title>
        <style>
          body { font-family: Arial, sans-serif; color: #172033; margin: 32px; }
          h1 { margin: 0 0 4px; font-size: 22px; }
          .muted { color: #53657d; font-size: 13px; }
          .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 22px 0; }
          .box { border: 1px solid #cbdced; border-radius: 10px; padding: 12px; }
          .label { color: #53657d; font-size: 11px; font-weight: 700; text-transform: uppercase; }
          table { width: 100%; border-collapse: collapse; margin-top: 12px; }
          th { text-align: left; background: #eaf3fb; color: #324a63; font-size: 12px; text-transform: uppercase; }
          th, td { border: 1px solid #cbdced; padding: 9px; font-size: 13px; }
          section { margin-top: 22px; }
        </style>
      </head>
      <body>
        <h1>Solicitud de cotizacion</h1>
        <div class="muted">${escapeHtml(rfq.rfq_number)} · ${escapeHtml(statusLabel(rfq.status))}</div>
        <div class="grid">
          <div class="box"><div class="label">Solicitud</div><strong>${escapeHtml(rfq.title)}</strong></div>
          <div class="box"><div class="label">Creada</div><strong>${escapeHtml(formatDateTime(rfq.created_at))}</strong></div>
          <div class="box"><div class="label">Comprador</div><strong>${escapeHtml(rfq.creator?.full_name ?? 'Sin usuario')}</strong><br><span class="muted">${escapeHtml(rfq.creator?.email ?? '')}</span></div>
        </div>
        <section>
          <h2>Proveedores invitados</h2>
          <table>
            <thead><tr><th>Proveedor</th><th>Credito</th><th>Estado</th></tr></thead>
            <tbody>${suppliers}</tbody>
          </table>
        </section>
        <section>
          <h2>Partidas solicitadas</h2>
          <table>
            <thead><tr><th>Material</th><th>Cantidad</th><th>Unidad</th></tr></thead>
            <tbody>${items}</tbody>
          </table>
        </section>
      </body>
    </html>
  `)
  popup.document.close()
  popup.focus()
  popup.print()
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: 'Borrador',
    sent: 'Enviada',
    email_error: 'Error de correo',
    missing_email: 'Sin correo',
    partially_quoted: 'Parcial',
    quoted: 'Cotizada',
    approval_pending: 'Pendiente aprobacion',
    awarded: 'Aprobada',
    cancelled: 'Cancelada',
    received: 'Recibida',
    approval_requested: 'Pendiente aprobacion',
    rejected: 'Rechazada',
    discarded: 'Descartada',
    approved: 'Aprobada',
    issued: 'Emitida',
    partially_received: 'Parcial recibida',
    factured: 'Facturada',
    closed: 'Cerrada',
  }
  return labels[status] ?? status
}

const emptyItem: RFQDraftItem = {
  material_id: '',
  material_search: '',
  description: '',
  unit: '',
  quantity: '1',
  notes: '',
}

export default function PurchasingPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [rfqs, setRfqs] = useState<SupplierRFQ[]>([])
  const [rfqExceptions, setRfqExceptions] = useState<SupplierRFQException[]>([])
  const [quotes, setQuotes] = useState<SupplierQuote[]>([])
  const [comparison, setComparison] = useState<ComparisonRow[]>([])
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [selectedRfqId, setSelectedRfqId] = useState<number | null>(null)
  const [detailRfqId, setDetailRfqId] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [projectId, setProjectId] = useState('')
  const [title, setTitle] = useState('')
  const [requiredBy, setRequiredBy] = useState('')
  const [responseDeadline, setResponseDeadline] = useState('')
  const [supplierIds, setSupplierIds] = useState<string[]>([])
  const [supplierSearch, setSupplierSearch] = useState('')
  const [rfqSearch, setRfqSearch] = useState('')
  const [rfqDateFrom, setRfqDateFrom] = useState('')
  const [rfqDateTo, setRfqDateTo] = useState('')
  const [rfqSupplierFilter, setRfqSupplierFilter] = useState('')
  const [rfqBuyerFilter, setRfqBuyerFilter] = useState('')
  const [items, setItems] = useState<RFQDraftItem[]>([{ ...emptyItem }])

  const [quoteSupplierId, setQuoteSupplierId] = useState('')
  const [quoteNumber, setQuoteNumber] = useState('')
  const [deliveryDays, setDeliveryDays] = useState('')
  const [paymentTermsDays, setPaymentTermsDays] = useState('30')
  const [quoteRows, setQuoteRows] = useState<QuoteDraftItem[]>([])
  const [exceptionOpen, setExceptionOpen] = useState(false)
  const [exceptionNotes, setExceptionNotes] = useState('')
  const [rfqExceptionOpen, setRfqExceptionOpen] = useState(false)
  const [rfqExceptionNotes, setRfqExceptionNotes] = useState('')
  const quoteCaptureRef = useRef<HTMLElement | null>(null)

  const selectedRfq = useMemo(
    () => rfqs.find((rfq) => rfq.id === selectedRfqId) ?? rfqs[0],
    [rfqs, selectedRfqId],
  )
  const detailRfq = useMemo(
    () => rfqs.find((rfq) => rfq.id === detailRfqId) ?? null,
    [detailRfqId, rfqs],
  )
  const sortedMaterials = useMemo(
    () =>
      [...materials].sort((left, right) =>
        left.name.localeCompare(right.name, 'es', { sensitivity: 'base' }),
      ),
    [materials],
  )
  const filteredSuppliers = useMemo(() => {
    const normalizedSearch = supplierSearch.trim().toLocaleLowerCase()
    return [...suppliers]
      .sort((left, right) => left.name.localeCompare(right.name, 'es', { sensitivity: 'base' }))
      .filter((supplier) => {
        if (!normalizedSearch) return true
        return [
          supplier.name,
          String(supplier.payment_terms_days),
          String(supplier.average_delivery_days ?? ''),
        ]
          .join(' ')
          .toLocaleLowerCase()
          .includes(normalizedSearch)
      })
  }, [supplierSearch, suppliers])
  const rfqBuyers = useMemo(() => {
    const buyers = new Map<string, UserSummary>()
    rfqs.forEach((rfq) => {
      if (rfq.creator) buyers.set(String(rfq.creator.id), rfq.creator)
    })
    return [...buyers.values()].sort((left, right) =>
      left.full_name.localeCompare(right.full_name, 'es', { sensitivity: 'base' }),
    )
  }, [rfqs])
  const filteredRfqs = useMemo(() => {
    const normalizedSearch = rfqSearch.trim().toLocaleLowerCase()
    const normalizedSupplier = rfqSupplierFilter.trim().toLocaleLowerCase()
    const normalizedBuyer = rfqBuyerFilter.trim().toLocaleLowerCase()

    return rfqs.filter((rfq) => {
      const createdDate = rfq.created_at.slice(0, 10)
      if (rfqDateFrom && createdDate < rfqDateFrom) return false
      if (rfqDateTo && createdDate > rfqDateTo) return false
      if (normalizedSearch) {
        const searchText = [rfq.title, rfq.rfq_number, statusLabel(rfq.status)].join(' ').toLocaleLowerCase()
        if (!searchText.includes(normalizedSearch)) return false
      }
      if (normalizedSupplier) {
        const supplierText = rfq.supplier_links
          .map((link) => link.supplier?.name ?? '')
          .join(' ')
          .toLocaleLowerCase()
        if (!supplierText.includes(normalizedSupplier)) return false
      }
      if (normalizedBuyer) {
        const buyerText = [rfq.creator?.full_name, rfq.creator?.email].join(' ').toLocaleLowerCase()
        if (!buyerText.includes(normalizedBuyer)) return false
      }
      return true
    })
  }, [rfqBuyerFilter, rfqDateFrom, rfqDateTo, rfqSearch, rfqSupplierFilter, rfqs])
  const readyOrders = useMemo(
    () => orders.filter((order) => order.status === 'issued'),
    [orders],
  )
  const completeComparison = useMemo(
    () =>
      comparison.filter(
        (row) =>
          row.complete_items === row.total_items &&
          row.total_items > 0 &&
          ['received', 'rejected', 'approval_requested'].includes(row.status),
      ),
    [comparison],
  )
  const canRequestApproval =
    Boolean(selectedRfq) &&
    completeComparison.length >= 3 &&
    !['approval_pending', 'awarded'].includes(selectedRfq?.status ?? '')
  const canRequestException =
    Boolean(selectedRfq) &&
    completeComparison.length > 0 &&
    completeComparison.length < 3 &&
    !['approval_pending', 'awarded'].includes(selectedRfq?.status ?? '')
  const validRfqItems = useMemo(
    () => items.filter((item) => item.description && item.unit && Number(item.quantity) > 0),
    [items],
  )
  const rfqDraftSnapshot = useMemo(
    () => ({
      project_id: Number(projectId),
      title: title.trim(),
      required_by: requiredBy || null,
      response_deadline: responseDeadline || null,
      supplier_ids: supplierIds.map(Number).sort((left, right) => left - right),
      items: validRfqItems.map((item) => ({
        material_id: item.material_id ? Number(item.material_id) : null,
        source_code: null,
        description: item.description.trim(),
        unit: item.unit.trim(),
        quantity: String(Number(item.quantity)),
        notes: item.notes || null,
      })),
    }),
    [projectId, requiredBy, responseDeadline, supplierIds, title, validRfqItems],
  )
  const approvedRfqException = useMemo(
    () =>
      rfqExceptions.find(
        (entry) =>
          entry.status === 'approved' &&
          !entry.rfq_id &&
          stableStringify(entry.payload_snapshot) === stableStringify(rfqDraftSnapshot),
      ) ?? null,
    [rfqDraftSnapshot, rfqExceptions],
  )
  const pendingRfqException = useMemo(
    () =>
      rfqExceptions.find(
        (entry) =>
          entry.status === 'requested' &&
          stableStringify(entry.payload_snapshot) === stableStringify(rfqDraftSnapshot),
      ) ?? null,
    [rfqDraftSnapshot, rfqExceptions],
  )
  const needsRfqException = supplierIds.length > 0 && supplierIds.length < 3
  const canCreateRfq =
    Boolean(projectId) &&
    Boolean(title.trim()) &&
    validRfqItems.length > 0 &&
    (supplierIds.length >= 3 || Boolean(approvedRfqException))

  async function loadData(nextSelectedRfqId = selectedRfq?.id) {
    setLoading(true)
    setError('')
    try {
      const [projectData, materialData, supplierData, rfqData, exceptionData, orderData] = await Promise.all([
        apiRequest<Project[]>('/projects'),
        apiRequest<Material[]>('/materials'),
        apiRequest<Supplier[]>('/purchasing/suppliers'),
        apiRequest<SupplierRFQ[]>('/purchasing/supplier-rfqs'),
        apiRequest<SupplierRFQException[]>('/purchasing/supplier-rfq-exceptions?approval_status=all'),
        apiRequest<PurchaseOrder[]>('/purchasing/purchase-orders?limit=250'),
      ])
      setProjects(projectData)
      setMaterials(materialData)
      setSuppliers(supplierData)
      setRfqs(rfqData)
      setRfqExceptions(exceptionData)
      setOrders(orderData)
      if (!projectId && projectData[0]) setProjectId(String(projectData[0].id))
      const nextId = nextSelectedRfqId ?? rfqData[0]?.id ?? null
      setSelectedRfqId(nextId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar compras')
    } finally {
      setLoading(false)
    }
  }

  async function loadRfqDetails(rfqId: number | undefined) {
    if (!rfqId) {
      setQuotes([])
      setComparison([])
      setQuoteRows([])
      return
    }
    try {
      const [quoteData, comparisonData] = await Promise.all([
        apiRequest<SupplierQuote[]>(`/purchasing/supplier-rfqs/${rfqId}/quotes`),
        apiRequest<ComparisonRow[]>(`/purchasing/supplier-rfqs/${rfqId}/comparison`),
      ])
      setQuotes(quoteData)
      setComparison(comparisonData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar cotizaciones')
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  function emptyQuoteRowsFor(rfq: SupplierRFQ | undefined) {
    return (rfq?.items ?? []).map((item) => ({
      rfq_item_id: item.id,
      unit_price: '',
      delivery_days: '',
    }))
  }

  function resetQuoteCapture(rfq = selectedRfq) {
    setQuoteSupplierId('')
    setQuoteNumber('')
    setDeliveryDays('')
    setPaymentTermsDays('30')
    setQuoteRows(emptyQuoteRowsFor(rfq))
  }

  useEffect(() => {
    void loadRfqDetails(selectedRfq?.id)
    resetQuoteCapture(selectedRfq)
  }, [selectedRfq?.id])

  useEffect(() => {
    if (!filteredRfqs.length) return
    if (!selectedRfqId || !filteredRfqs.some((rfq) => rfq.id === selectedRfqId)) {
      setSelectedRfqId(filteredRfqs[0].id)
    }
  }, [filteredRfqs, selectedRfqId])

  function updateItem(index: number, patch: Partial<RFQDraftItem>) {
    setItems((current) =>
      current.map((item, itemIndex) => {
        if (itemIndex !== index) return item
        const next = { ...item, ...patch }
        if (patch.material_id) {
          const material = sortedMaterials.find((entry) => entry.id === Number(patch.material_id))
          if (material) {
            next.material_search = material.name
            next.description = material.name
            next.unit = material.unit
          }
        }
        return next
      }),
    )
  }

  function updateMaterialSearch(index: number, value: string) {
    const material = sortedMaterials.find(
      (entry) => entry.name.toLocaleLowerCase() === value.toLocaleLowerCase(),
    )
    if (material) {
      updateItem(index, {
        material_id: String(material.id),
        material_search: material.name,
      })
      return
    }
    updateItem(index, {
      material_id: '',
      material_search: value,
    })
  }

  function selectRfqForQuote(rfqId: number) {
    setSelectedRfqId(rfqId)
    window.setTimeout(() => {
      quoteCaptureRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 80)
  }

  async function createRfq() {
    setError('')
    setMessage('')
    if (supplierIds.length < 3 && !approvedRfqException) {
      setError('Se requiere una excepcion aprobada para crear solicitud con menos de 3 proveedores.')
      return
    }
    try {
      const created = await apiRequest<SupplierRFQ>('/purchasing/supplier-rfqs', {
        method: 'POST',
        body: JSON.stringify({
          project_id: Number(projectId),
          title,
          required_by: requiredBy || null,
          response_deadline: responseDeadline || null,
          supplier_ids: supplierIds.map(Number),
          exception_request_id: approvedRfqException?.id ?? null,
          items: validRfqItems
            .map((item) => ({
              material_id: item.material_id ? Number(item.material_id) : null,
              description: item.description,
              unit: item.unit,
              quantity: Number(item.quantity),
              notes: item.notes || null,
            })),
        }),
      })
      setMessage(`Solicitud ${created.rfq_number} creada. Estado: ${statusLabel(created.status)}.`)
      setTitle('')
      setSupplierIds([])
      setItems([{ ...emptyItem }])
      setRfqExceptionNotes('')
      await loadData(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible crear la solicitud')
    }
  }

  async function sendRfq(rfqId: number) {
    setError('')
    setMessage('')
    try {
      const updated = await apiRequest<SupplierRFQ>(`/purchasing/supplier-rfqs/${rfqId}/send`, {
        method: 'POST',
      })
      setMessage(`Solicitud ${updated.rfq_number} procesada para envio por correo.`)
      await loadData(rfqId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la solicitud')
    }
  }

  async function createSupplierQuote() {
    if (!selectedRfq) return
    setError('')
    setMessage('')
    if (!quoteNumber.trim()) {
      setError('Captura el folio de la cotizacion del proveedor.')
      return
    }
    try {
      await apiRequest<SupplierQuote>(`/purchasing/supplier-rfqs/${selectedRfq.id}/quotes`, {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: Number(quoteSupplierId),
          quote_number: quoteNumber.trim(),
          delivery_days: deliveryDays ? Number(deliveryDays) : null,
          payment_terms_days: Number(paymentTermsDays || 30),
          items: quoteRows
            .filter((row) => row.unit_price !== '')
            .map((row) => ({
              rfq_item_id: row.rfq_item_id,
              unit_price: Number(row.unit_price),
              delivery_days: row.delivery_days ? Number(row.delivery_days) : null,
            })),
        }),
      })
      setMessage('Datos guardados para su comparativo.')
      resetQuoteCapture(selectedRfq)
      await loadRfqDetails(selectedRfq.id)
      await loadData(selectedRfq.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible registrar la cotizacion')
    }
  }

  async function requestRfqApproval(isException = false) {
    if (!selectedRfq) return
    setError('')
    setMessage('')
    try {
      await apiRequest(
        `/purchasing/supplier-rfqs/${selectedRfq.id}/request-approval`,
        {
          method: 'POST',
          body: JSON.stringify({
            is_exception: isException,
            request_notes: isException ? exceptionNotes.trim() : null,
          }),
        },
      )
      setMessage(
        isException
          ? 'Solicitud de aprobacion por excepcion enviada.'
          : 'Solicitud de aprobacion enviada.',
      )
      setExceptionOpen(false)
      setExceptionNotes('')
      await loadData(selectedRfq?.id)
      if (selectedRfq?.id) await loadRfqDetails(selectedRfq.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la solicitud de aprobacion')
    }
  }

  async function requestCreateRfqException() {
    setError('')
    setMessage('')
    if (!rfqExceptionNotes.trim()) {
      setError('Captura el motivo para solicitar la excepcion.')
      return
    }
    try {
      await apiRequest<SupplierRFQException>('/purchasing/supplier-rfq-exceptions', {
        method: 'POST',
        body: JSON.stringify({
          project_id: Number(projectId),
          title: title.trim(),
          required_by: requiredBy || null,
          response_deadline: responseDeadline || null,
          supplier_ids: supplierIds.map(Number),
          items: validRfqItems.map((item) => ({
            material_id: item.material_id ? Number(item.material_id) : null,
            description: item.description,
            unit: item.unit,
            quantity: Number(item.quantity),
            notes: item.notes || null,
          })),
          request_notes: rfqExceptionNotes.trim(),
        }),
      })
      setMessage('Solicitud de excepcion enviada a aprobacion.')
      setRfqExceptionOpen(false)
      setRfqExceptionNotes('')
      await loadData(selectedRfq?.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la excepcion')
    }
  }

  async function deleteSupplierQuoteForRecapture(row: ComparisonRow) {
    setError('')
    setMessage('')
    try {
      await apiRequest<void>(`/purchasing/supplier-quotes/${row.supplier_quote_id}`, {
        method: 'DELETE',
      })
      resetQuoteCapture(selectedRfq)
      setMessage(
        `Cotizacion de ${row.supplier_name} borrada. Tienes que volver a seleccionar el proveedor y recapturar los datos.`,
      )
      await loadData(selectedRfq?.id)
      if (selectedRfq?.id) await loadRfqDetails(selectedRfq.id)
      window.setTimeout(() => {
        quoteCaptureRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 80)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible borrar la cotizacion')
    }
  }

  async function sendOrder(orderId: number) {
    setError('')
    setMessage('')
    try {
      const updated = await apiRequest<PurchaseOrder>(`/purchasing/purchase-orders/${orderId}/send`, {
        method: 'POST',
      })
      setMessage(`Orden ${updated.po_number} enviada al proveedor. Ya puedes consultarla en Ordenes de compra.`)
      await loadData(selectedRfq?.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la orden de compra')
    }
  }

  return (
    <div className="space-y-5">
      {(message || error) && (
        <div
          className={[
            'rounded-md border px-4 py-3 text-sm font-medium',
            error
              ? 'border-red-200 bg-red-50 text-red-700'
              : 'border-blue-200 bg-blue-50 text-blue-800',
          ].join(' ')}
        >
          {error || message}
        </div>
      )}

      <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex items-center justify-between border-b border-acsm-line px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-green">
              <ShoppingCart className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <h2 className="font-semibold text-acsm-ink">Solicitud de cotizacion a proveedores</h2>
              <p className="text-xs text-acsm-muted">
                Arma una lista de materiales y enviala minimo a 3 proveedores.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadData(selectedRfq?.id)}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Actualizar
          </button>
        </div>

        <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm font-semibold text-acsm-ink">
                Desarrollo
                <select
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                  className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-semibold text-acsm-ink">
                Nombre de solicitud
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Ej. Acero y concreto etapa 1"
                  className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                />
              </label>
              <label className="text-sm font-semibold text-acsm-ink">
                Fecha requerida
                <input
                  type="date"
                  value={requiredBy}
                  onChange={(event) => setRequiredBy(event.target.value)}
                  className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                />
              </label>
              <label className="text-sm font-semibold text-acsm-ink">
                Limite de respuesta
                <input
                  type="date"
                  value={responseDeadline}
                  onChange={(event) => setResponseDeadline(event.target.value)}
                  className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                />
              </label>
            </div>

            <div className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-sm">
              <div className="flex items-center justify-between gap-3 border-b border-acsm-line bg-acsm-paper px-3 py-2">
                <div>
                  <h3 className="text-sm font-semibold text-acsm-ink">Materiales a cotizar</h3>
                  <p className="text-xs text-acsm-muted">Puedes capturar libre o partir del catalogo.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setItems((current) => [...current, { ...emptyItem }])}
                  className="inline-flex h-8 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Renglon
                </button>
              </div>
              <div className="p-2">
                <datalist id="material-catalog-options">
                  {sortedMaterials.map((material) => (
                    <option key={material.id} value={material.name}>
                      {material.unit}
                    </option>
                  ))}
                </datalist>
                <table className="w-full table-fixed overflow-hidden rounded-md border border-acsm-line text-sm">
                  <colgroup>
                    <col className="w-[19%]" />
                    <col className="w-[21%]" />
                    <col className="w-[15%]" />
                    <col className="w-[19%]" />
                    <col className="w-[21%]" />
                    <col className="w-[5%]" />
                  </colgroup>
                  <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                    <tr>
                      <th className="px-2 py-2 text-left">Catalogo</th>
                      <th className="px-2 py-2 text-left">Material</th>
                      <th className="px-2 py-2 text-left">Unidad</th>
                      <th className="px-2 py-2 text-left">Cantidad</th>
                      <th className="px-2 py-2 text-left">Notas</th>
                      <th className="w-12 px-2 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, index) => (
                      <tr key={index} className="border-t border-acsm-line">
                        <td className="px-2 py-2">
                          <input
                            list="material-catalog-options"
                            value={item.material_search}
                            onChange={(event) => updateMaterialSearch(index, event.target.value)}
                            placeholder="Buscar material..."
                            className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2"
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            value={item.description}
                            onChange={(event) => updateItem(index, { description: event.target.value })}
                            className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2"
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            value={item.unit}
                            onChange={(event) => updateItem(index, { unit: event.target.value })}
                            className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2"
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            type="number"
                            step="0.0001"
                            value={item.quantity}
                            onChange={(event) => updateItem(index, { quantity: event.target.value })}
                            className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2"
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            value={item.notes}
                            onChange={(event) => updateItem(index, { notes: event.target.value })}
                            className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2"
                          />
                        </td>
                        <td className="px-2 py-2 text-right">
                          <button
                            type="button"
                            onClick={() =>
                              setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))
                            }
                            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-red-200 text-red-600 hover:bg-red-50"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <aside className="rounded-md border border-acsm-line bg-acsm-paper p-3">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-acsm-ink">Proveedores invitados</h3>
              <p className="text-xs text-acsm-muted">Minimo 3 para poder comparar.</p>
            </div>
            <input
              value={supplierSearch}
              onChange={(event) => setSupplierSearch(event.target.value)}
              placeholder="Buscar proveedor..."
              className="mb-3 h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
            />
            <div className="max-h-[260px] space-y-2 overflow-y-auto pr-1">
              {filteredSuppliers.map((supplier) => (
                <label
                  key={supplier.id}
                  className="flex items-center justify-between gap-3 rounded-md border border-acsm-line bg-white px-3 py-2 text-sm"
                >
                  <span>
                    <span className="block font-semibold text-acsm-ink">{supplier.name}</span>
                    <span className="text-xs text-acsm-muted">{supplier.payment_terms_days} dias credito</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={supplierIds.includes(String(supplier.id))}
                    onChange={(event) => {
                      setSupplierIds((current) =>
                        event.target.checked
                          ? [...current, String(supplier.id)]
                          : current.filter((value) => value !== String(supplier.id)),
                      )
                    }}
                  />
                </label>
              ))}
              {!filteredSuppliers.length ? (
                <div className="rounded-md border border-acsm-line bg-white px-3 py-4 text-center text-sm text-acsm-muted">
                  No hay proveedores que coincidan con la busqueda.
                </div>
              ) : null}
            </div>
            {needsRfqException ? (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <div className="font-bold">
                  {approvedRfqException
                    ? 'Excepcion aprobada'
                    : pendingRfqException
                      ? 'Excepcion en revision'
                      : 'Requiere excepcion'}
                </div>
                <p className="mt-1">
                  {approvedRfqException
                    ? 'Ya puedes crear esta solicitud con menos de 3 proveedores.'
                    : pendingRfqException
                      ? 'Gerencia debe aprobarla para activar Crear solicitud.'
                      : 'Solicita autorizacion si no existen 3 proveedores para este material.'}
                </p>
                {!approvedRfqException && !pendingRfqException ? (
                  <button
                    type="button"
                    onClick={() => setRfqExceptionOpen(true)}
                    disabled={!projectId || !title.trim() || validRfqItems.length === 0}
                    className="mt-3 inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border border-amber-300 bg-white px-3 text-sm font-bold text-amber-900 hover:bg-amber-100 disabled:opacity-60"
                  >
                    <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                    Solicitar excepcion
                  </button>
                ) : null}
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => void createRfq()}
              disabled={loading || !canCreateRfq}
              className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
            >
              <Send className="h-4 w-4" aria-hidden="true" />
              Crear solicitud
            </button>
          </aside>
        </div>
      </section>

      <section className="space-y-5">
        <div className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
          <div className="border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">Control de compras</p>
                <h2 className="text-lg font-bold text-acsm-ink">Solicitudes de cotizacion</h2>
                <p className="text-sm text-acsm-muted">
                  Revisa quien genero cada solicitud, fecha, proveedores invitados y estado actual.
                </p>
              </div>
              <div className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800">
                {filteredRfqs.length} de {rfqs.length} solicitudes
              </div>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(260px,1fr)_170px_170px_220px_220px]">
              <label className="text-xs font-bold uppercase text-acsm-muted">
                Solicitud
                <input
                  value={rfqSearch}
                  onChange={(event) => setRfqSearch(event.target.value)}
                  placeholder="Buscar folio, nombre o estado"
                  className="mt-1 h-10 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold normal-case text-acsm-ink"
                />
              </label>
              <label className="text-xs font-bold uppercase text-acsm-muted">
                Desde
                <input
                  type="date"
                  value={rfqDateFrom}
                  onChange={(event) => setRfqDateFrom(event.target.value)}
                  className="mt-1 h-10 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold normal-case text-acsm-ink"
                />
              </label>
              <label className="text-xs font-bold uppercase text-acsm-muted">
                Hasta
                <input
                  type="date"
                  value={rfqDateTo}
                  onChange={(event) => setRfqDateTo(event.target.value)}
                  className="mt-1 h-10 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold normal-case text-acsm-ink"
                />
              </label>
              <label className="text-xs font-bold uppercase text-acsm-muted">
                Proveedor
                <input
                  value={rfqSupplierFilter}
                  onChange={(event) => setRfqSupplierFilter(event.target.value)}
                  placeholder="Nombre proveedor"
                  className="mt-1 h-10 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold normal-case text-acsm-ink"
                />
              </label>
              <label className="text-xs font-bold uppercase text-acsm-muted">
                Comprador
                <select
                  value={rfqBuyerFilter}
                  onChange={(event) => setRfqBuyerFilter(event.target.value)}
                  className="mt-1 h-10 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm font-semibold normal-case text-acsm-ink"
                >
                  <option value="">Todos</option>
                  {rfqBuyers.map((buyer) => (
                    <option key={buyer.id} value={buyer.email}>
                      {buyer.full_name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="max-h-[520px] overflow-y-auto">
            <div className="divide-y divide-acsm-line">
              {filteredRfqs.map((rfq) => {
                const suppliersText = rfq.supplier_links
                  .map((link) => link.supplier?.name ?? `Proveedor ${link.supplier_id}`)
                  .join(', ')
                return (
                  <div
                    key={rfq.id}
                    className={[
                      'grid w-full grid-cols-1 overflow-hidden border-l-4 text-left transition lg:grid-cols-[minmax(260px,0.9fr)_minmax(420px,1.7fr)_220px]',
                      selectedRfq?.id === rfq.id
                        ? 'border-blue-600 bg-blue-50 shadow-[inset_0_0_0_1px_rgba(47,120,189,0.18)]'
                        : 'border-transparent bg-white hover:border-blue-200 hover:bg-slate-50/70',
                    ].join(' ')}
                  >
                    <div className="min-w-0 border-b border-acsm-line/80 px-4 py-4 lg:border-b-0 lg:border-r lg:px-5">
                      <div className="min-w-0">
                        <span className="block whitespace-normal break-words text-sm font-bold leading-snug text-acsm-ink">
                          {rfq.title}
                        </span>
                        <span className="mt-1 block break-all text-xs font-semibold leading-snug text-blue-800">
                          {rfq.rfq_number}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setDetailRfqId(rfq.id)}
                        className="mt-3 inline-flex h-9 items-center gap-2 rounded-xl border border-blue-200 bg-white px-3 text-xs font-bold text-blue-800 shadow-sm transition hover:border-blue-300 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                        title="Abrir detalle de la solicitud"
                      >
                        <Eye className="h-4 w-4" aria-hidden="true" />
                        Ver detalle
                      </button>
                      {selectedRfq?.id === rfq.id ? (
                        <span className="ml-2 mt-3 inline-flex max-w-full whitespace-normal rounded-full border border-blue-200 bg-white px-2 py-0.5 text-[10px] font-bold leading-tight text-blue-800 sm:text-[11px]">
                          Activa para captura
                        </span>
                      ) : null}
                    </div>

                    <div className="grid min-w-0 gap-4 px-4 py-4 text-sm md:grid-cols-2 xl:grid-cols-[170px_190px_minmax(260px,1fr)_120px]">
                      <div>
                        <span className="block text-xs font-bold uppercase text-acsm-muted">Creada</span>
                        <span className="font-semibold text-acsm-ink">{formatDateTime(rfq.created_at)}</span>
                      </div>
                      <div className="min-w-0">
                        <span className="block text-xs font-bold uppercase text-acsm-muted">Comprador</span>
                        <span className="block truncate font-semibold text-acsm-ink">
                          {rfq.creator?.full_name ?? 'Sin usuario'}
                        </span>
                        <span className="block truncate text-xs text-acsm-muted">{rfq.creator?.email}</span>
                      </div>
                      <div className="min-w-0">
                        <span className="block text-xs font-bold uppercase text-acsm-muted">
                          Proveedores seleccionados
                        </span>
                        <span className="block truncate font-semibold text-acsm-ink" title={suppliersText}>
                          {suppliersText || 'Sin proveedores'}
                        </span>
                        <span className="mt-1 block text-xs text-acsm-muted">
                          {rfq.supplier_links.length} proveedores · {rfq.items.length} partidas
                        </span>
                      </div>
                      <div>
                        <span className="block text-xs font-bold uppercase text-acsm-muted">Estado</span>
                        <span className="mt-1 inline-flex rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800">
                          {statusLabel(rfq.status)}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-start border-t border-acsm-line/80 bg-[linear-gradient(180deg,#f8fbff_0%,#eaf4fb_100%)] px-4 py-4 lg:justify-center lg:border-l lg:border-t-0">
                      <button
                        type="button"
                        onClick={() => selectRfqForQuote(rfq.id)}
                        className={[
                          'inline-flex h-11 w-full max-w-[190px] items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold shadow-button transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600',
                          selectedRfq?.id === rfq.id
                            ? 'border border-blue-300 bg-white text-blue-800 hover:bg-blue-50'
                            : 'bg-acsm-green text-white hover:bg-acsm-green-hover',
                        ].join(' ')}
                        title="Seleccionar esta solicitud para capturar la cotizacion recibida"
                      >
                        <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
                        {selectedRfq?.id === rfq.id ? 'Captura activa' : 'Capturar cotizacion'}
                      </button>
                    </div>
                  </div>
                )
              })}
              {!filteredRfqs.length && (
                <div className="px-5 py-12 text-center text-sm text-acsm-muted">
                  No hay solicitudes con los filtros actuales.
                </div>
              )}
            </div>
          </div>
        </div>

        {selectedRfq && (
          <section
            ref={quoteCaptureRef}
            className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel"
          >
            <div className="border-b border-acsm-line px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-bold text-acsm-ink">Capturar cotizacion recibida</h2>
                  <p className="text-sm leading-relaxed text-acsm-muted">
                    Solicitud activa: <span className="font-semibold text-acsm-ink">{selectedRfq.title}</span>{' '}
                    · {selectedRfq.rfq_number}
                  </p>
                </div>
                <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800">
                  {selectedRfq.items.length} partidas
                </span>
              </div>
            </div>
            <div className="space-y-3 p-5">
              <div className="grid gap-3 md:grid-cols-4">
                <label className="text-xs font-bold uppercase text-acsm-muted">
                  Proveedor cotizante
                  <select
                    value={quoteSupplierId}
                    onChange={(event) => {
                      setQuoteSupplierId(event.target.value)
                      setQuoteNumber('')
                      setDeliveryDays('')
                      setQuoteRows(emptyQuoteRowsFor(selectedRfq))
                    }}
                    className="mt-1 h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold normal-case text-acsm-ink"
                  >
                    <option value="">Seleccionar proveedor</option>
                    {selectedRfq.supplier_links.map((link) => (
                      <option key={link.supplier_id} value={link.supplier_id}>
                        {link.supplier?.name ?? link.supplier_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-bold uppercase text-acsm-muted">
                  Folio de cotizacion
                  <input
                    value={quoteNumber}
                    onChange={(event) => setQuoteNumber(event.target.value)}
                    placeholder="Ej. COT-1234 *"
                    required
                    className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm font-semibold normal-case text-acsm-ink"
                  />
                </label>
                <label className="text-xs font-bold uppercase text-acsm-muted">
                  Dias de entrega general
                  <input
                    type="number"
                    value={deliveryDays}
                    onChange={(event) => setDeliveryDays(event.target.value)}
                    placeholder="Ej. 5 dias"
                    className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm font-semibold normal-case text-acsm-ink"
                  />
                </label>
                <label className="text-xs font-bold uppercase text-acsm-muted">
                  Dias de credito / pago
                  <input
                    type="number"
                    value={paymentTermsDays}
                    onChange={(event) => setPaymentTermsDays(event.target.value)}
                    placeholder="Ej. 30 dias"
                    className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm font-semibold normal-case text-acsm-ink"
                  />
                </label>
              </div>

              <div className="overflow-x-auto rounded-md border border-acsm-line">
                <table className="min-w-[760px] w-full text-sm">
                  <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                    <tr>
                      <th className="px-3 py-2 text-left">Material</th>
                      <th className="px-3 py-2 text-left">Cantidad</th>
                      <th className="px-3 py-2 text-left">Precio unitario</th>
                      <th className="px-3 py-2 text-left">Dias entrega partida</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRfq.items.map((item, index) => (
                      <tr key={item.id} className="border-t border-acsm-line">
                        <td className="px-3 py-2">{item.description}</td>
                        <td className="px-3 py-2 text-acsm-muted">
                          {Number(item.quantity).toLocaleString('es-MX')} {item.unit}
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.0001"
                            value={quoteRows[index]?.unit_price ?? ''}
                            onChange={(event) =>
                              setQuoteRows((current) =>
                                current.map((row) =>
                                  row.rfq_item_id === item.id ? { ...row, unit_price: event.target.value } : row,
                                ),
                              )
                            }
                            className="h-9 w-full rounded-md border border-acsm-line px-2"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            value={quoteRows[index]?.delivery_days ?? ''}
                            onChange={(event) =>
                              setQuoteRows((current) =>
                                current.map((row) =>
                                  row.rfq_item_id === item.id ? { ...row, delivery_days: event.target.value } : row,
                                ),
                              )
                            }
                            className="h-9 w-full rounded-md border border-acsm-line px-2"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                type="button"
                onClick={() => void createSupplierQuote()}
                disabled={!quoteSupplierId || !quoteNumber.trim()}
                className="inline-flex h-10 items-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
              >
                <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
                Guardar cotizacion
              </button>
            </div>
          </section>
        )}

        <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line px-5 py-4">
            <div>
              <h2 className="font-bold text-acsm-ink">Comparativo</h2>
              <p className="text-sm text-acsm-muted">
                Costo, entrega y credito para mandar el paquete completo a aprobacion.
              </p>
              <p className="mt-1 text-xs font-semibold text-acsm-muted">
                {completeComparison.length} cotizaciones completas de 3 requeridas
              </p>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => void requestRfqApproval(false)}
                disabled={!canRequestApproval}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white shadow-button hover:bg-acsm-green-hover disabled:opacity-60"
              >
                <Check className="h-4 w-4" aria-hidden="true" />
                Solicitar aprobacion
              </button>
              <button
                type="button"
                onClick={() => setExceptionOpen(true)}
                disabled={!canRequestException}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 text-sm font-bold text-amber-800 hover:bg-amber-100 disabled:opacity-60"
              >
                <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                Solicitar excepcion
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-[980px] w-full text-sm">
              <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                <tr>
                  <th className="px-4 py-3 text-left">Proveedor</th>
                  <th className="px-4 py-3 text-left">Subtotal</th>
                  <th className="px-4 py-3 text-left">Entrega</th>
                  <th className="px-4 py-3 text-left">Credito</th>
                  <th className="px-4 py-3 text-left">Partidas</th>
                  <th className="px-4 py-3 text-left">Estado</th>
                  <th className="px-4 py-3 text-right">Correccion</th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((row) => {
                  const isComplete = row.complete_items === row.total_items && row.total_items > 0
                  const canCorrectQuote =
                    row.status === 'received' && !['approval_pending', 'awarded'].includes(selectedRfq?.status ?? '')
                  return (
                    <tr key={row.supplier_quote_id} className="border-t border-acsm-line">
                      <td className="px-4 py-3 font-semibold">{row.supplier_name}</td>
                      <td className="px-4 py-3">{formatMoney(row.subtotal)}</td>
                      <td className="px-4 py-3">{row.delivery_days ?? '-'} dias</td>
                      <td className="px-4 py-3">{row.payment_terms_days} dias</td>
                      <td className="px-4 py-3">
                        {row.complete_items}/{row.total_items}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={[
                            'inline-flex rounded-full border px-3 py-1 text-xs font-bold',
                            isComplete
                              ? 'border-blue-200 bg-blue-50 text-blue-700'
                              : 'border-amber-200 bg-amber-50 text-amber-800',
                          ].join(' ')}
                        >
                          {isComplete ? statusLabel(row.status) : 'Incompleta'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => void deleteSupplierQuoteForRecapture(row)}
                          disabled={!canCorrectQuote}
                          className="inline-flex h-9 items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 text-xs font-bold text-red-700 hover:bg-red-100 disabled:opacity-50"
                          title="Borrar esta captura para volver a registrar la cotizacion"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                          Volver a registrar
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {!comparison.length && (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-acsm-muted">
                      Sin cotizaciones recibidas.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-acsm-paper text-acsm-green">
              <Send className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">
                Siguiente paso
              </p>
              <h2 className="font-bold text-acsm-ink">Ordenes aprobadas listas para enviar</h2>
              <p className="text-sm text-acsm-muted">
                Son cotizaciones aprobadas por gerencia; compras solo confirma el envio de la OC al proveedor.
              </p>
            </div>
          </div>
          <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
            {readyOrders.length} pendientes
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-[860px] w-full text-sm">
            <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
              <tr>
                <th className="px-4 py-3 text-left">Orden</th>
                <th className="px-4 py-3 text-left">Proveedor autorizado</th>
                <th className="px-4 py-3 text-left">Emitida</th>
                <th className="px-4 py-3 text-left">Subtotal</th>
                <th className="px-4 py-3 text-left">Partidas</th>
                <th className="px-4 py-3 text-right">Accion</th>
              </tr>
            </thead>
            <tbody>
              {readyOrders.map((order) => (
                <tr key={order.id} className="border-t border-acsm-line bg-white hover:bg-sky-50/70">
                  <td className="px-4 py-4 align-top font-bold text-acsm-ink">{order.po_number}</td>
                  <td className="px-4 py-4 align-top">
                    <div className="font-bold text-acsm-ink">
                      {order.supplier?.name ?? `Proveedor ${order.supplier_id}`}
                    </div>
                    <div className="text-xs text-acsm-muted">{order.supplier?.payment_terms_days ?? 0} dias credito</div>
                  </td>
                  <td className="px-4 py-4 align-top font-semibold">{formatDate(order.issued_at)}</td>
                  <td className="px-4 py-4 align-top font-semibold">{formatMoney(order.subtotal)}</td>
                  <td className="px-4 py-4 align-top">{order.items.length}</td>
                  <td className="px-4 py-4 text-right align-top">
                    <button
                      type="button"
                      onClick={() => void sendOrder(order.id)}
                      className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white shadow-button hover:bg-acsm-green-hover"
                    >
                      <Send className="h-4 w-4" aria-hidden="true" />
                      Enviar OC al proveedor
                    </button>
                  </td>
                </tr>
              ))}
              {!readyOrders.length && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-acsm-muted">
                    No hay ordenes aprobadas pendientes de envio. Cuando gerencia apruebe una cotizacion,
                    aparecera aqui para cerrar el flujo de compra.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {rfqExceptionOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={() => setRfqExceptionOpen(false)}
        >
          <div
            className="w-full max-w-2xl overflow-hidden rounded-[24px] border border-white/20 bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-acsm-line bg-gradient-to-r from-white to-amber-50 px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-amber-700">
                  Excepcion para solicitud
                </p>
                <h2 className="text-xl font-bold text-acsm-ink">
                  Crear solicitud con menos de 3 proveedores
                </h2>
                <p className="mt-1 text-sm text-acsm-muted">
                  Gerencia debe autorizar esta captura antes de poder enviar la solicitud a proveedores.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setRfqExceptionOpen(false)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper"
                aria-label="Cerrar"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <div className="space-y-4 p-6">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <div className="text-xs font-bold uppercase text-amber-800">Proveedores</div>
                  <div className="mt-1 text-lg font-bold text-amber-950">{supplierIds.length}</div>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <div className="text-xs font-bold uppercase text-amber-800">Partidas</div>
                  <div className="mt-1 text-lg font-bold text-amber-950">{validRfqItems.length}</div>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <div className="text-xs font-bold uppercase text-amber-800">Regla normal</div>
                  <div className="mt-1 text-lg font-bold text-amber-950">3 proveedores</div>
                </div>
              </div>
              <label className="block text-sm font-bold text-acsm-ink">
                Motivo de excepcion
                <textarea
                  value={rfqExceptionNotes}
                  onChange={(event) => setRfqExceptionNotes(event.target.value)}
                  rows={5}
                  className="mt-2 w-full rounded-xl border border-acsm-line px-3 py-2 text-sm"
                  placeholder="Ej. Solo existe un proveedor autorizado para este material, no hay tres proveedores activos, entrega urgente..."
                />
              </label>
              <div className="flex flex-wrap justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setRfqExceptionOpen(false)}
                  className="inline-flex h-10 items-center rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void requestCreateRfqException()}
                  disabled={!rfqExceptionNotes.trim()}
                  className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white shadow-button hover:bg-acsm-green-hover disabled:opacity-60"
                >
                  <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                  Enviar excepcion a aprobacion
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {exceptionOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={() => setExceptionOpen(false)}
        >
          <div
            className="w-full max-w-2xl overflow-hidden rounded-[24px] border border-white/20 bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-acsm-line bg-gradient-to-r from-white to-amber-50 px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-amber-700">
                  Excepcion de compras
                </p>
                <h2 className="text-xl font-bold text-acsm-ink">Solicitar aprobacion con menos de 3 cotizaciones</h2>
                <p className="mt-1 text-sm text-acsm-muted">
                  Explica por que se pide revisar el comparativo incompleto. Gerencia vera esta nota en Aprobaciones.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setExceptionOpen(false)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper"
                aria-label="Cerrar"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <div className="space-y-4 p-6">
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900">
                Cotizaciones completas disponibles: {completeComparison.length}. El minimo normal es 3.
              </div>
              <label className="block text-sm font-bold text-acsm-ink">
                Motivo de excepcion
                <textarea
                  value={exceptionNotes}
                  onChange={(event) => setExceptionNotes(event.target.value)}
                  rows={5}
                  className="mt-2 w-full rounded-xl border border-acsm-line px-3 py-2 text-sm"
                  placeholder="Ej. Un proveedor no respondio, material urgente para obra, precio vigente por pocas horas..."
                />
              </label>
              <div className="flex flex-wrap justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setExceptionOpen(false)}
                  className="inline-flex h-10 items-center rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void requestRfqApproval(true)}
                  disabled={!exceptionNotes.trim()}
                  className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white shadow-button hover:bg-acsm-green-hover disabled:opacity-60"
                >
                  <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                  Enviar excepcion a aprobacion
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {detailRfq ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={() => setDetailRfqId(null)}
        >
          <div
            className="max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-[24px] border border-white/20 bg-white shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">
                  Detalle de solicitud
                </p>
                <h2 className="text-xl font-bold text-acsm-ink">{detailRfq.title}</h2>
                <p className="text-sm text-acsm-muted">
                  {detailRfq.rfq_number} · {statusLabel(detailRfq.status)} · Creada por{' '}
                  {detailRfq.creator?.full_name ?? 'Sin usuario'} el {formatDateTime(detailRfq.created_at)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => printRfqDocument(detailRfq)}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 text-sm font-bold text-blue-800 hover:bg-blue-100"
                >
                  <Printer className="h-4 w-4" aria-hidden="true" />
                  Imprimir / PDF
                </button>
                <button
                  type="button"
                  onClick={() => setDetailRfqId(null)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-white text-acsm-ink hover:bg-acsm-paper"
                  aria-label="Cerrar"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            <div className="max-h-[calc(90vh-96px)] overflow-y-auto p-6">
              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-xl border border-acsm-line bg-slate-50 p-3">
                  <div className="text-xs font-bold uppercase text-acsm-muted">Folio</div>
                  <div className="mt-1 font-bold text-acsm-ink">{detailRfq.rfq_number}</div>
                </div>
                <div className="rounded-xl border border-acsm-line bg-slate-50 p-3">
                  <div className="text-xs font-bold uppercase text-acsm-muted">Estado</div>
                  <div className="mt-1 font-bold text-acsm-ink">{statusLabel(detailRfq.status)}</div>
                </div>
                <div className="rounded-xl border border-acsm-line bg-slate-50 p-3">
                  <div className="text-xs font-bold uppercase text-acsm-muted">Proveedores</div>
                  <div className="mt-1 font-bold text-acsm-ink">{detailRfq.supplier_links.length}</div>
                </div>
                <div className="rounded-xl border border-acsm-line bg-slate-50 p-3">
                  <div className="text-xs font-bold uppercase text-acsm-muted">Partidas</div>
                  <div className="mt-1 font-bold text-acsm-ink">{detailRfq.items.length}</div>
                </div>
              </div>

              <div className="mt-5 grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
                <section className="overflow-hidden rounded-xl border border-acsm-line">
                  <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3 text-sm font-bold">
                    Proveedores invitados
                  </div>
                  <div className="divide-y divide-acsm-line">
                    {detailRfq.supplier_links.map((link) => (
                      <div key={link.supplier_id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                        <div className="min-w-0">
                          <span className="block truncate font-semibold text-acsm-ink">
                            {link.supplier?.name ?? `Proveedor ${link.supplier_id}`}
                          </span>
                          <span className="text-xs text-acsm-muted">
                            {link.supplier?.payment_terms_days ?? 0} dias credito
                          </span>
                        </div>
                        <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                          {statusLabel(link.status)}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="overflow-hidden rounded-xl border border-acsm-line">
                  <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3 text-sm font-bold">
                    Partidas solicitadas
                  </div>
                  <div className="max-h-[420px] overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-white text-xs uppercase text-acsm-muted">
                        <tr>
                          <th className="px-4 py-3 text-left">Material</th>
                          <th className="px-4 py-3 text-right">Cantidad</th>
                          <th className="px-4 py-3 text-left">Unidad</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detailRfq.items.map((item) => (
                          <tr key={item.id} className="border-t border-acsm-line">
                            <td className="px-4 py-3 font-semibold text-acsm-ink">{item.description}</td>
                            <td className="px-4 py-3 text-right text-acsm-muted">
                              {Number(item.quantity).toLocaleString('es-MX')}
                            </td>
                            <td className="px-4 py-3 text-acsm-muted">{item.unit}</td>
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
