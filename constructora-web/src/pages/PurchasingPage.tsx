import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  CircleDashed,
  ClipboardCheck,
  Clock,
  Eye,
  FileText,
  Plus,
  Printer,
  RefreshCw,
  Send,
  ShoppingCart,
  Trash2,
  X,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { API_BASE_URL, apiRequest, getStoredToken } from '../lib/api'
import { showActionNotice, type ActionNoticeKind } from '../lib/actionNotice'

type Project = {
  id: number
  client_id: number
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

type MaterialRequisitionItem = {
  id: number
  material_id?: number | null
  source_code?: string | null
  description: string
  unit: string
  requested_unit?: string | null
  requested_quantity: string
  approved_quantity?: string | null
  status: string
  notes?: string | null
}

type MaterialRequisition = {
  id: number
  project_id: number
  client_id: number
  house_model_id: number
  converted_rfq_id?: number | null
  requisition_number: string
  title: string
  status: string
  priority: string
  required_date?: string | null
  created_at: string
  notes?: string | null
  requested_by?: UserSummary | null
  items: MaterialRequisitionItem[]
}

type RFQItem = {
  id: number
  material_id?: number | null
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
  request_type?: string
  supplier_agreement_id?: number | null
  created_at: string
  created_by?: number | null
  creator?: UserSummary | null
  required_by?: string | null
  response_deadline?: string | null
  items: RFQItem[]
  supplier_links: RFQSupplierLink[]
}

type SupplierAgreement = {
  id: number
  supplier_id: number
  client_id: number
  house_model_id: number
  name: string
  status: string
  approval_status?: string
  valid_from?: string | null
  valid_until?: string | null
  payment_terms_days?: number | null
  average_delivery_days?: number | null
  supplier?: Supplier | null
  items: {
    id: number
    material_id: number
    description: string
    unit: string
    unit_price?: string | null
    delivery_days?: number | null
  }[]
}

type SupplierAgreementEligibility = {
  agreement: SupplierAgreement
  is_full_match: boolean
}

type ProjectSummary = {
  assigned_models: {
    house_model_id: number
  }[]
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
  decided_at?: string | null
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

type SupplierQuoteUpload = {
  id: number
  rfq_id: number
  supplier_id: number
  quote_number?: string | null
  original_file_name: string
  file_extension: string
  file_size_bytes: number
  status: string
  uploaded_at: string
  notes?: string | null
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

type NotificationFocusTarget =
  | 'work-requisitions'
  | 'rfq-form'
  | 'rfq-list'
  | 'quote-capture'
  | 'uploads'

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

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
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
    queued: 'En cola',
    sent: 'Enviada',
    email_error: 'Error de correo',
    missing_email: 'Sin correo',
    partially_quoted: 'Parcial',
    quoted: 'Cotizada',
    approval_pending: 'Pendiente aprobacion',
    approved_for_order: 'Aprobada para OC',
    purchase_order_ready: 'OC lista para enviar',
    awarded: 'Aprobada',
    cancelled: 'Cancelada',
    received: 'Recibida',
    approval_requested: 'Pendiente aprobacion',
    rejected: 'Rechazada',
    submitted: 'Pendiente',
    in_review: 'En revision',
    discarded: 'Descartada',
    approved: 'Aprobada',
    converted_to_rfq: 'Convertida a cotizacion',
    ordered_to_suppliers: 'Compras realizo el pedido a proveedores',
    normal: 'Normal',
    urgent: 'Urgente',
    high: 'Alta',
    low: 'Baja',
    issued: 'Emitida',
    partially_received: 'Parcial recibida',
    factured: 'Facturada',
    closed: 'Cerrada',
  }
  return labels[status] ?? status
}

type JourneyStepState = 'done' | 'current' | 'pending' | 'attention' | 'skipped'

type PurchaseJourneyStep = {
  key: string
  label: string
  detail: string
  state: JourneyStepState
}

type PurchaseJourney = {
  headline: string
  nextAction: string
  steps: PurchaseJourneyStep[]
}

const rfqSentStatuses = new Set([
  'sent',
  'partially_quoted',
  'quoted',
  'approval_pending',
  'approved_for_order',
  'purchase_order_ready',
  'awarded',
])

function completeQuoteRows(rows: ComparisonRow[]) {
  return rows.filter((row) => row.complete_items === row.total_items && row.total_items > 0)
}

function normalizeJourneySteps(steps: PurchaseJourneyStep[]) {
  const hasActiveStep = steps.some((step) => step.state === 'current' || step.state === 'attention')
  if (hasActiveStep) return steps

  const nextIndex = steps.findIndex((step) => step.state === 'pending')
  if (nextIndex < 0) return steps

  return steps.map((step, index) =>
    index === nextIndex ? { ...step, state: 'current' as JourneyStepState } : step,
  )
}

function buildPurchaseJourney({
  rfq,
  materialRequisitions,
  comparison,
  quoteUploads,
  readyOrders,
}: {
  rfq: SupplierRFQ
  materialRequisitions: MaterialRequisition[]
  comparison: ComparisonRow[]
  quoteUploads: SupplierQuoteUpload[]
  readyOrders: PurchaseOrder[]
}): PurchaseJourney {
  const sourceRequisition = materialRequisitions.find((entry) => entry.converted_rfq_id === rfq.id)
  const supplierCount = rfq.supplier_links.length
  const quoteTarget = rfq.request_type === 'agreement' ? 1 : 3
  const completedQuotes = completeQuoteRows(comparison)
  const hasAnyQuote = comparison.length > 0 || quoteUploads.length > 0
  const quotesCaptured =
    completedQuotes.length >= quoteTarget ||
    ['quoted', 'approval_pending', 'approved_for_order', 'purchase_order_ready', 'awarded'].includes(rfq.status)
  const approvalRequested =
    rfq.status === 'approval_pending' || comparison.some((row) => row.status === 'approval_requested')
  const approved =
    ['approved_for_order', 'purchase_order_ready', 'awarded'].includes(rfq.status) ||
    comparison.some((row) => row.status === 'approved')
  const hasOrderReady = approved && readyOrders.length > 0

  const requestTypeText =
    rfq.request_type === 'agreement'
      ? 'Cotizacion directa por convenio'
      : rfq.request_type === 'exception'
        ? 'Excepcion autorizada'
        : 'Terna de proveedores'

  const steps: PurchaseJourneyStep[] = [
    {
      key: 'obra',
      label: 'Origen',
      detail: sourceRequisition
        ? `Obra ${sourceRequisition.requisition_number}`
        : 'Solicitud creada en Compras',
      state: sourceRequisition ? 'done' : 'skipped',
    },
    {
      key: 'solicitud',
      label: 'Solicitud',
      detail: `${rfq.rfq_number} registrada`,
      state: 'done',
    },
    {
      key: 'proveedores',
      label: 'Proveedores',
      detail: `${supplierCount} invitado(s) · ${requestTypeText}`,
      state: supplierCount > 0 ? 'done' : 'attention',
    },
    {
      key: 'envio',
      label: 'Envio',
      detail: rfqSentStatuses.has(rfq.status)
        ? 'Correo o liga enviada'
        : 'Pendiente de enviar al proveedor',
      state: rfqSentStatuses.has(rfq.status) ? 'done' : 'current',
    },
    {
      key: 'cotizaciones',
      label: 'Cotizaciones',
      detail: quotesCaptured
        ? `${completedQuotes.length}/${quoteTarget} capturada(s)`
        : hasAnyQuote
          ? 'Documento recibido; falta capturar precios'
          : 'Esperando respuesta del proveedor',
      state: quotesCaptured ? 'done' : hasAnyQuote ? 'current' : 'pending',
    },
    {
      key: 'comparativo',
      label: 'Comparativo',
      detail: comparison.length
        ? `${completedQuotes.length}/${quoteTarget} lista(s) para revisar`
        : 'Sin cotizaciones capturadas',
      state: quotesCaptured ? 'done' : comparison.length ? 'attention' : 'pending',
    },
    {
      key: 'aprobacion',
      label: 'Aprobacion',
      detail: approved
        ? 'Gerencia aprobo proveedor'
        : approvalRequested
          ? 'En revision por gerencia'
          : quotesCaptured
            ? 'Lista para solicitar aprobacion'
            : 'Pendiente de comparativo',
      state: approved ? 'done' : approvalRequested ? 'current' : quotesCaptured ? 'current' : 'pending',
    },
    {
      key: 'orden',
      label: 'Orden de compra',
      detail: hasOrderReady ? 'OC lista para enviar' : approved ? 'Genera o envia la OC' : 'Esperando aprobacion',
      state: hasOrderReady ? 'current' : approved ? 'current' : 'pending',
    },
  ]

  const nextAction =
    supplierCount === 0
      ? 'Selecciona proveedores para poder continuar.'
      : !rfqSentStatuses.has(rfq.status)
        ? 'Envia la solicitud para que el proveedor cargue su cotizacion.'
        : !hasAnyQuote
          ? 'Da seguimiento a la respuesta del proveedor.'
          : !quotesCaptured
            ? 'Captura precios y tiempos de entrega para completar el comparativo.'
            : !approvalRequested && !approved
              ? 'Solicita aprobacion a gerencia.'
              : approvalRequested && !approved
                ? 'Esperando decision de gerencia.'
                : hasOrderReady
                  ? 'Orden aprobada lista para enviar al proveedor.'
                  : 'Proveedor aprobado; continua con la orden de compra.'

  return {
    headline: `${rfq.title} · ${statusLabel(rfq.status)}`,
    nextAction,
    steps: normalizeJourneySteps(steps),
  }
}

function buildDraftPurchaseJourney({
  title,
  activeMaterialRequisition,
  supplierCount,
  itemCount,
  needsException,
  pendingException,
  approvedException,
}: {
  title: string
  activeMaterialRequisition: MaterialRequisition | null
  supplierCount: number
  itemCount: number
  needsException: boolean
  pendingException: SupplierRFQException | null
  approvedException: SupplierRFQException | null
}): PurchaseJourney {
  const hasSource = Boolean(activeMaterialRequisition)
  const exceptionState: JourneyStepState = approvedException
    ? 'done'
    : pendingException
      ? 'current'
      : needsException
        ? 'attention'
        : 'skipped'
  const canCreateRequest = itemCount > 0 && supplierCount > 0 && (!needsException || Boolean(approvedException))

  return {
    headline: `${title || activeMaterialRequisition?.title || 'Solicitud'} · Preparacion`,
    nextAction: approvedException
      ? 'Excepcion aprobada; crea la solicitud de cotizacion para iniciar el flujo operativo.'
      : pendingException
        ? 'Esperando autorizacion de gerencia para poder crear la solicitud con menos de 3 proveedores.'
        : needsException
          ? 'Solicita excepcion o selecciona minimo 3 proveedores para continuar.'
          : canCreateRequest
            ? 'Crea la solicitud de cotizacion para iniciar el flujo con proveedores.'
            : 'Completa desarrollo, materiales y proveedores para iniciar el proceso.',
    steps: normalizeJourneySteps([
      {
        key: 'obra',
        label: 'Origen',
        detail: hasSource
          ? `Obra ${activeMaterialRequisition?.requisition_number}`
          : 'Captura directa en Compras',
        state: hasSource ? 'done' : 'skipped',
      },
      {
        key: 'preparacion',
        label: 'Preparacion',
        detail: `${itemCount} partida(s) · ${supplierCount} proveedor(es)`,
        state: itemCount > 0 && supplierCount > 0 ? 'done' : 'current',
      },
      {
        key: 'excepcion',
        label: 'Excepcion',
        detail: approvedException
          ? 'Autorizada por gerencia'
          : pendingException
            ? 'En revision por gerencia'
            : needsException
              ? 'Requiere autorizacion'
              : 'No requerida',
        state: exceptionState,
      },
      {
        key: 'solicitud',
        label: 'Solicitud',
        detail: canCreateRequest ? 'Lista para crear RFQ' : 'Pendiente de completar',
        state: canCreateRequest ? 'current' : 'pending',
      },
      {
        key: 'envio',
        label: 'Envio',
        detail: 'Pendiente de crear solicitud',
        state: 'pending',
      },
      {
        key: 'cotizaciones',
        label: 'Cotizaciones',
        detail: 'Pendiente',
        state: 'pending',
      },
      {
        key: 'aprobacion',
        label: 'Aprobacion',
        detail: 'Pendiente',
        state: 'pending',
      },
      {
        key: 'orden',
        label: 'Orden de compra',
        detail: 'Pendiente',
        state: 'pending',
      },
    ]),
  }
}

function JourneyMarker({ state }: { state: JourneyStepState }) {
  if (state === 'done') return <Check className="h-4 w-4" aria-hidden="true" />
  if (state === 'current') return <Clock className="h-4 w-4" aria-hidden="true" />
  if (state === 'attention') return <AlertTriangle className="h-4 w-4" aria-hidden="true" />
  return <CircleDashed className="h-4 w-4" aria-hidden="true" />
}

function PurchaseJourneyBar({ journey }: { journey: PurchaseJourney }) {
  return (
    <aside className="purchase-journey-panel">
      <div className="purchase-journey-header">
        <div>
          <p className="purchase-journey-eyebrow">Ruta</p>
          <h2>{journey.headline}</h2>
          <p>{journey.nextAction}</p>
        </div>
        <span className="purchase-journey-pill">Proceso activo</span>
      </div>
      <ol className="purchase-journey-steps" aria-label="Estado del proceso de compra">
        {journey.steps.map((step, index) => (
          <li
            key={step.key}
            className={`purchase-journey-step is-${step.state}`}
            title={`${String(index + 1).padStart(2, '0')} · ${step.label}: ${step.detail}`}
            aria-current={step.state === 'current' || step.state === 'attention' ? 'step' : undefined}
          >
            <span className={`purchase-journey-marker is-${step.state}`}>
              <JourneyMarker state={step.state} />
            </span>
            <div className="min-w-0">
              <span className="purchase-journey-number">{String(index + 1).padStart(2, '0')}</span>
              <h3>{step.label}</h3>
              <p>{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </aside>
  )
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
  const [searchParams] = useSearchParams()
  const [projects, setProjects] = useState<Project[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [rfqs, setRfqs] = useState<SupplierRFQ[]>([])
  const [rfqExceptions, setRfqExceptions] = useState<SupplierRFQException[]>([])
  const [eligibleAgreements, setEligibleAgreements] = useState<SupplierAgreementEligibility[]>([])
  const [allAgreements, setAllAgreements] = useState<SupplierAgreement[]>([])
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null)
  const [quotes, setQuotes] = useState<SupplierQuote[]>([])
  const [quoteUploads, setQuoteUploads] = useState<SupplierQuoteUpload[]>([])
  const [comparison, setComparison] = useState<ComparisonRow[]>([])
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [materialRequisitions, setMaterialRequisitions] = useState<MaterialRequisition[]>([])
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
  const [selectedAgreementId, setSelectedAgreementId] = useState('')
  const [supplierSearch, setSupplierSearch] = useState('')
  const [rfqSearch, setRfqSearch] = useState('')
  const [rfqDateFrom, setRfqDateFrom] = useState('')
  const [rfqDateTo, setRfqDateTo] = useState('')
  const [rfqSupplierFilter, setRfqSupplierFilter] = useState('')
  const [rfqBuyerFilter, setRfqBuyerFilter] = useState('')
  const [materialRequisitionSearch, setMaterialRequisitionSearch] = useState('')
  const [selectedMaterialRequisitionId, setSelectedMaterialRequisitionId] = useState<number | null>(null)
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
  const [rfqExceptionError, setRfqExceptionError] = useState('')
  const [rfqExceptionSubmitting, setRfqExceptionSubmitting] = useState(false)
  const [focusedPanel, setFocusedPanel] = useState<NotificationFocusTarget | null>(null)
  const materialRequisitionRef = useRef<HTMLElement | null>(null)
  const rfqFormRef = useRef<HTMLElement | null>(null)
  const rfqListRef = useRef<HTMLDivElement | null>(null)
  const quoteCaptureRef = useRef<HTMLElement | null>(null)
  const quoteUploadsRef = useRef<HTMLElement | null>(null)
  const handledNotificationTargetRef = useRef('')

  const selectedRfq = useMemo(
    () => rfqs.find((rfq) => rfq.id === selectedRfqId) ?? rfqs[0],
    [rfqs, selectedRfqId],
  )
  const notificationRfqId = useMemo(() => {
    const rawId = searchParams.get('rfq_id')
    const parsedId = rawId ? Number(rawId) : NaN
    return Number.isFinite(parsedId) && parsedId > 0 ? parsedId : null
  }, [searchParams])
  const notificationFocus = searchParams.get('focus')
  const notificationId = searchParams.get('notification_id')

  function notifySuccess(text: string, kind: ActionNoticeKind = 'success') {
    setMessage(text)
    showActionNotice(text, kind)
  }
  function focusClass(target: NotificationFocusTarget) {
    return focusedPanel === target ? 'acsm-notification-focus-target' : ''
  }

  function spotlightPanel(target: NotificationFocusTarget, element: HTMLElement | null | undefined) {
    if (!element) return
    setFocusedPanel(target)
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => setFocusedPanel((current) => (current === target ? null : current)), 2200)
  }
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
  const purchaseJourney = useMemo(
    () =>
      selectedRfq
        ? buildPurchaseJourney({
            rfq: selectedRfq,
            materialRequisitions,
            comparison,
            quoteUploads,
            readyOrders,
          })
        : null,
    [comparison, materialRequisitions, quoteUploads, readyOrders, selectedRfq],
  )
  const selectedAgreement = useMemo(
    () =>
      eligibleAgreements.find(
        (entry) => entry.agreement.id === Number(selectedAgreementId) && entry.is_full_match,
      )?.agreement ?? null,
    [eligibleAgreements, selectedAgreementId],
  )
  const fullMatchAgreements = useMemo(
    () => eligibleAgreements.filter((entry) => entry.is_full_match),
    [eligibleAgreements],
  )
  const selectedProject = useMemo(
    () => {
      const matchedProject = projects.find((project) => project.id === Number(projectId))
      if (matchedProject) return matchedProject
      const requisitionProject = materialRequisitions.find(
        (entry) => entry.project_id === Number(projectId),
      )
      return requisitionProject
        ? {
            id: requisitionProject.project_id,
            client_id: requisitionProject.client_id,
            name: `Desarrollo ${requisitionProject.project_id}`,
          }
        : null
    },
    [materialRequisitions, projectId, projects],
  )
  const projectNameById = useMemo(
    () => new Map(projects.map((project) => [project.id, project.name])),
    [projects],
  )
  const rfqProjectOptions = useMemo(() => {
    if (!projectId || projects.some((project) => project.id === Number(projectId))) return projects
    const requisitionProject = materialRequisitions.find(
      (entry) => entry.project_id === Number(projectId),
    )
    if (!requisitionProject) return projects
    return [
      ...projects,
      {
        id: requisitionProject.project_id,
        client_id: requisitionProject.client_id,
        name:
          projectNameById.get(requisitionProject.project_id) ??
          `Desarrollo ${requisitionProject.project_id}`,
      },
    ]
  }, [materialRequisitions, projectId, projectNameById, projects])
  const pendingMaterialRequisitions = useMemo(
    () =>
      materialRequisitions.filter(
        (entry) =>
          ['submitted', 'in_review', 'approved'].includes(entry.status) &&
          !entry.converted_rfq_id,
      ),
    [materialRequisitions],
  )
  const filteredMaterialRequisitions = useMemo(() => {
    const normalizedSearch = materialRequisitionSearch.trim().toLocaleLowerCase()
    return pendingMaterialRequisitions.filter((entry) => {
      if (!normalizedSearch) return true
      return [
        entry.requisition_number,
        entry.title,
        entry.notes ?? '',
        projectNameById.get(entry.project_id) ?? '',
        entry.requested_by?.full_name ?? '',
        entry.requested_by?.email ?? '',
      ]
        .join(' ')
        .toLocaleLowerCase()
        .includes(normalizedSearch)
    })
  }, [materialRequisitionSearch, pendingMaterialRequisitions, projectNameById])
  const activeMaterialRequisition = useMemo(
    () => materialRequisitions.find((entry) => entry.id === selectedMaterialRequisitionId) ?? null,
    [materialRequisitions, selectedMaterialRequisitionId],
  )
  const materialRequisitionsToShow = useMemo(
    () => filteredMaterialRequisitions.filter((entry) => entry.id !== selectedMaterialRequisitionId),
    [filteredMaterialRequisitions, selectedMaterialRequisitionId],
  )
  const selectedSupplierIdSet = useMemo(
    () => new Set(supplierIds.map(Number).filter(Boolean)),
    [supplierIds],
  )
  const projectAssignedModelIds = useMemo(
    () => new Set((projectSummary?.assigned_models ?? []).map((model) => model.house_model_id)),
    [projectSummary],
  )
  const agreementGuidance = useMemo(() => {
    if (!projectId || supplierIds.length === 0 || supplierIds.length >= 3 || selectedAgreement) return null

    const selectedSupplierNames = suppliers
      .filter((supplier) => selectedSupplierIdSet.has(supplier.id))
      .map((supplier) => supplier.name)
      .join(', ')
    const supplierAgreements = allAgreements.filter((agreement) =>
      selectedSupplierIdSet.has(agreement.supplier_id),
    )

    if (!supplierAgreements.length) {
      return {
        title: 'Proveedor sin convenio registrado',
        body: `${selectedSupplierNames || 'El proveedor seleccionado'} no tiene convenio registrado.`,
        steps: [
          'Selecciona minimo 3 proveedores para crear una solicitud normal.',
          'Si realmente no existen mas proveedores, solicita excepcion a gerencia.',
          'Si si tiene convenio, registralo en Compras / Convenios antes de crear la solicitud.',
        ],
      }
    }

    const projectClientAgreements = selectedProject
      ? supplierAgreements.filter((agreement) => agreement.client_id === selectedProject.client_id)
      : supplierAgreements

    if (!projectClientAgreements.length) {
      return {
        title: 'Convenio con otra inmobiliaria',
        body: 'El proveedor tiene convenio, pero no con la inmobiliaria del desarrollo seleccionado.',
        steps: [
          'Selecciona el desarrollo correcto.',
          'O registra un convenio para esta inmobiliaria y su modelo.',
        ],
      }
    }

    if (!projectAssignedModelIds.size) {
      return {
        title: 'Falta asignar modelo al desarrollo',
        body: 'El proveedor tiene convenio con esta inmobiliaria, pero el desarrollo no tiene modelo de casa asignado.',
        steps: [
          'Ve a Desarrollos y asigna el modelo de casa del convenio.',
          'Regresa a Compras y vuelve a seleccionar el desarrollo.',
        ],
      }
    }

    const modelAgreements = projectClientAgreements.filter((agreement) =>
      projectAssignedModelIds.has(agreement.house_model_id),
    )

    if (!modelAgreements.length) {
      return {
        title: 'Modelo del convenio no asignado',
        body: 'El proveedor tiene convenio con la inmobiliaria, pero el modelo del convenio no esta asignado a este desarrollo.',
        steps: [
          'Asigna al desarrollo el modelo indicado en el convenio.',
          'O crea un convenio para el modelo correcto.',
        ],
      }
    }

    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const unavailableAgreement = modelAgreements.find((agreement) => {
      const validFrom = agreement.valid_from ? new Date(`${agreement.valid_from}T00:00:00`) : null
      const validUntil = agreement.valid_until ? new Date(`${agreement.valid_until}T00:00:00`) : null
      return (
        agreement.approval_status !== 'approved' ||
        agreement.status !== 'active' ||
        Boolean(validFrom && validFrom > today) ||
        Boolean(validUntil && validUntil < today)
      )
    })

    if (unavailableAgreement) {
      if (unavailableAgreement.approval_status && unavailableAgreement.approval_status !== 'approved') {
        return {
          title: 'Convenio pendiente de autorizacion',
          body: `El convenio ${unavailableAgreement.name} existe, pero aun no esta autorizado por administracion.`,
          steps: [
            'Solicita a administracion aprobarlo en Compras / Aprobaciones.',
            'Mientras tanto selecciona minimo 3 proveedores o solicita excepcion.',
          ],
        }
      }
      if (unavailableAgreement.status !== 'active') {
        return {
          title: 'Convenio no activo',
          body: `El convenio ${unavailableAgreement.name} existe, pero esta ${statusLabel(
            unavailableAgreement.status,
          ).toLocaleLowerCase()}.`,
          steps: ['Activa el convenio o selecciona minimo 3 proveedores.'],
        }
      }
      if (
        unavailableAgreement.valid_from &&
        new Date(`${unavailableAgreement.valid_from}T00:00:00`) > today
      ) {
        return {
          title: 'Convenio aun no vigente',
          body: `El convenio ${unavailableAgreement.name} inicia el ${formatDate(
            unavailableAgreement.valid_from,
          )}.`,
          steps: [
            'Ajusta la fecha inicial del convenio si ya debe aplicar.',
            'Mientras tanto selecciona minimo 3 proveedores o solicita excepcion.',
          ],
        }
      }
      return {
        title: 'Convenio vencido',
        body: `El convenio ${unavailableAgreement.name} ya no esta vigente.`,
        steps: ['Actualiza la vigencia del convenio o selecciona minimo 3 proveedores.'],
      }
    }

    const availableAgreement = modelAgreements[0]
    return {
      title: 'Convenio disponible sin activar',
      body: `Existe el convenio ${availableAgreement.name}. Para usarlo debes seleccionarlo desde el bloque Convenio disponible.`,
      steps: [
        'Haz clic en el convenio disponible para activar la cotizacion directa.',
        'El sistema dejara de pedir excepcion cuando el convenio quede seleccionado.',
      ],
    }
  }, [
    allAgreements,
    projectAssignedModelIds,
    projectId,
    selectedAgreement,
    selectedProject,
    selectedSupplierIdSet,
    supplierIds.length,
    suppliers,
  ])
  const isAgreementRfq = selectedRfq?.request_type === 'agreement'
  const canRequestApproval =
    Boolean(selectedRfq) &&
    completeComparison.length >= (isAgreementRfq ? 1 : 3) &&
    !['approval_pending', 'awarded'].includes(selectedRfq?.status ?? '')
  const canRequestException =
    Boolean(selectedRfq) &&
    !isAgreementRfq &&
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
  const needsRfqException = supplierIds.length > 0 && supplierIds.length < 3 && !selectedAgreement
  const approvedUnusedRfqExceptions = useMemo(
    () => rfqExceptions.filter((entry) => entry.status === 'approved' && !entry.rfq_id),
    [rfqExceptions],
  )
  const pendingUnusedRfqExceptions = useMemo(
    () => rfqExceptions.filter((entry) => entry.status === 'requested' && !entry.rfq_id),
    [rfqExceptions],
  )
  const canCreateRfq =
    Boolean(projectId) &&
    Boolean(title.trim()) &&
    validRfqItems.length > 0 &&
    (supplierIds.length >= 3 || Boolean(approvedRfqException) || Boolean(selectedAgreement))
  const draftPurchaseJourney = useMemo(() => {
    if (selectedRfq) return null
    const hasDraftContext =
      Boolean(activeMaterialRequisition) ||
      Boolean(title.trim()) ||
      validRfqItems.length > 0 ||
      supplierIds.length > 0 ||
      Boolean(pendingRfqException) ||
      Boolean(approvedRfqException)
    if (!hasDraftContext) return null
    return buildDraftPurchaseJourney({
      title,
      activeMaterialRequisition,
      supplierCount: supplierIds.length,
      itemCount: validRfqItems.length,
      needsException: needsRfqException,
      pendingException: pendingRfqException,
      approvedException: approvedRfqException,
    })
  }, [
    activeMaterialRequisition,
    approvedRfqException,
    needsRfqException,
    pendingRfqException,
    selectedRfq,
    supplierIds.length,
    title,
    validRfqItems.length,
  ])
  const activePurchaseJourney = purchaseJourney ?? draftPurchaseJourney

  async function loadData(nextSelectedRfqId = selectedRfq?.id) {
    setLoading(true)
    setError('')
    try {
      const [
        projectData,
        materialData,
        supplierData,
        agreementData,
        rfqData,
        exceptionData,
        orderData,
        materialRequisitionData,
      ] = await Promise.all([
        apiRequest<Project[]>('/projects'),
        apiRequest<Material[]>('/materials'),
        apiRequest<Supplier[]>('/purchasing/suppliers'),
        apiRequest<SupplierAgreement[]>('/purchasing/supplier-agreements?limit=250'),
        apiRequest<SupplierRFQ[]>('/purchasing/supplier-rfqs'),
        apiRequest<SupplierRFQException[]>('/purchasing/supplier-rfq-exceptions?approval_status=all'),
        apiRequest<PurchaseOrder[]>('/purchasing/purchase-orders?limit=250'),
        apiRequest<MaterialRequisition[]>('/material-requisitions?limit=250'),
      ])
      setProjects(projectData)
      setMaterials(materialData)
      setSuppliers(supplierData)
      setAllAgreements(agreementData)
      setRfqs(rfqData)
      setRfqExceptions(exceptionData)
      setOrders(orderData)
      setMaterialRequisitions(materialRequisitionData)
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
      setQuoteUploads([])
      setComparison([])
      setQuoteRows([])
      return
    }
    try {
      const [quoteData, comparisonData, uploadData] = await Promise.all([
        apiRequest<SupplierQuote[]>(`/purchasing/supplier-rfqs/${rfqId}/quotes`),
        apiRequest<ComparisonRow[]>(`/purchasing/supplier-rfqs/${rfqId}/comparison`),
        apiRequest<SupplierQuoteUpload[]>(`/purchasing/supplier-rfqs/${rfqId}/quote-uploads`),
      ])
      setQuotes(quoteData)
      setComparison(comparisonData)
      setQuoteUploads(uploadData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar cotizaciones')
    }
  }

  useEffect(() => {
    void loadData(notificationRfqId ?? undefined)
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
    if (!notificationFocus) return
    const targetKey = `${notificationId ?? 'manual'}:${notificationRfqId ?? 'none'}:${notificationFocus}`
    if (handledNotificationTargetRef.current === targetKey) return

    const focusTargets: Record<string, { target: NotificationFocusTarget; ref: { current: HTMLElement | null } }> = {
      'work-requisitions': { target: 'work-requisitions', ref: materialRequisitionRef },
      'rfq-form': { target: 'rfq-form', ref: rfqFormRef },
      'rfq-list': { target: 'rfq-list', ref: rfqListRef },
      'quote-capture': { target: 'quote-capture', ref: quoteCaptureRef },
      uploads: { target: 'uploads', ref: quoteUploadsRef },
    }
    const focusTarget = focusTargets[notificationFocus] ?? focusTargets['rfq-form']

    if (notificationRfqId && rfqs.some((rfq) => rfq.id === notificationRfqId)) {
      setSelectedRfqId(notificationRfqId)
    } else if (notificationRfqId) {
      return
    }

    handledNotificationTargetRef.current = targetKey
    window.setTimeout(() => spotlightPanel(focusTarget.target, focusTarget.ref.current), 160)
  }, [notificationFocus, notificationId, notificationRfqId, rfqs])

  useEffect(() => {
    if (!filteredRfqs.length) return
    if (selectedRfqId && rfqs.some((rfq) => rfq.id === selectedRfqId)) return
    if (!selectedRfqId || !filteredRfqs.some((rfq) => rfq.id === selectedRfqId)) {
      setSelectedRfqId(filteredRfqs[0].id)
    }
  }, [filteredRfqs, rfqs, selectedRfqId])

  useEffect(() => {
    if (!projectId) {
      setEligibleAgreements([])
      setProjectSummary(null)
      setSelectedAgreementId('')
      return
    }
    const query = new URLSearchParams({
      project_id: projectId,
    })
    let cancelled = false
    Promise.all([
      apiRequest<SupplierAgreementEligibility[]>(
        `/purchasing/supplier-agreements/eligible?${query.toString()}`,
      ),
      apiRequest<ProjectSummary>(`/projects/${projectId}/summary`),
    ])
      .then(([agreementData, summaryData]) => {
        if (cancelled) return
        setEligibleAgreements(agreementData)
        setProjectSummary(summaryData)
        if (
          selectedAgreementId &&
          !agreementData.some((entry) => entry.agreement.id === Number(selectedAgreementId))
        ) {
          setSelectedAgreementId('')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setEligibleAgreements([])
          setProjectSummary(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [projectId, selectedAgreementId])

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
      const target = quoteUploadsRef.current ?? quoteCaptureRef.current
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 80)
  }

  function toggleSupplierSelection(supplierId: number, checked: boolean) {
    setSelectedAgreementId('')
    setSupplierIds((current) =>
      checked
        ? Array.from(new Set([...current, String(supplierId)]))
        : current.filter((value) => value !== String(supplierId)),
    )
  }

  function useAgreement(agreement: SupplierAgreement) {
    setSelectedAgreementId(String(agreement.id))
    setSupplierIds([String(agreement.supplier_id)])
    notifySuccess(`Convenio seleccionado: ${agreement.name}.`, 'info')
  }

  function loadRequisitionIntoRfq(requisition: MaterialRequisition) {
    setSelectedMaterialRequisitionId(requisition.id)
    setProjectId(String(requisition.project_id))
    setTitle(requisition.title)
    setRequiredBy(requisition.required_date?.slice(0, 10) ?? '')
    setResponseDeadline('')
    setSupplierIds([])
    setSelectedAgreementId('')
    setItems(
      requisition.items.map((item) => {
        const quantity = item.approved_quantity ?? item.requested_quantity ?? '0'
        const requestedUnit = item.requested_unit || item.unit
        const baseUnitNote =
          requestedUnit !== item.unit ? `Unidad base: ${item.unit}` : ''
        const notes = [item.notes, `Origen ${requisition.requisition_number}`, baseUnitNote]
          .filter(Boolean)
          .join('. ')
        return {
          material_id: item.material_id ? String(item.material_id) : '',
          material_search: item.description,
          description: item.description,
          unit: requestedUnit,
          quantity: String(Number(quantity) || quantity || '0'),
          notes,
        }
      }),
    )
    notifySuccess(`Requerimiento ${requisition.requisition_number} cargado para cotizar.`, 'info')
    window.setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 80)
  }

  function loadExceptionIntoRfq(exceptionRequest: SupplierRFQException) {
    const snapshot = exceptionRequest.payload_snapshot
    const originRequisitionNumber =
      snapshot.items
        .map((item) => item.notes?.match(/RO-\d{6}-\d{4}/)?.[0])
        .find(Boolean) ?? null
    const originRequisition = originRequisitionNumber
      ? materialRequisitions.find((entry) => entry.requisition_number === originRequisitionNumber) ?? null
      : null
    setProjectId(String(snapshot.project_id))
    setTitle(snapshot.title)
    setRequiredBy(snapshot.required_by?.slice(0, 10) ?? '')
    setResponseDeadline(snapshot.response_deadline?.slice(0, 10) ?? '')
    setSupplierIds(snapshot.supplier_ids.map(String))
    setSelectedAgreementId('')
    setSelectedMaterialRequisitionId(originRequisition?.id ?? null)
    setItems(
      snapshot.items.map((item) => ({
        material_id: item.material_id ? String(item.material_id) : '',
        material_search: item.description,
        description: item.description,
        unit: item.unit,
        quantity: String(Number(item.quantity) || item.quantity || '0'),
        notes: item.notes ?? '',
      })),
    )
    notifySuccess(
      originRequisition
        ? `Excepcion aprobada cargada desde ${originRequisition.requisition_number}.`
        : `Excepcion aprobada cargada: ${exceptionRequest.title}.`,
      'info',
    )
    window.setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 80)
  }

  function clearRequisitionOrigin() {
    setSelectedMaterialRequisitionId(null)
    notifySuccess('Origen de obra removido de la solicitud.', 'info')
  }

  async function createRfq() {
    setError('')
    setMessage('')
    if (supplierIds.length < 3 && !approvedRfqException && !selectedAgreement) {
      setError('Se requiere una excepcion aprobada o convenio activo para crear solicitud con menos de 3 proveedores.')
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
          exception_request_id: selectedAgreement ? null : (approvedRfqException?.id ?? null),
          supplier_agreement_id: selectedAgreement?.id ?? null,
          material_requisition_id: selectedMaterialRequisitionId,
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
      notifySuccess(`Solicitud ${created.rfq_number} creada. Estado: ${statusLabel(created.status)}.`)
      setTitle('')
      setSupplierIds([])
      setSelectedAgreementId('')
      setSelectedMaterialRequisitionId(null)
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
      notifySuccess(`Solicitud ${updated.rfq_number} procesada para envio por correo.`)
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
      notifySuccess('Datos guardados para su comparativo.')
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
      notifySuccess(
        isException
          ? 'Solicitud de aprobacion por excepcion enviada.'
          : selectedRfq.request_type === 'agreement'
            ? 'Cotizacion por convenio enviada a aprobacion.'
            : 'Solicitud de aprobacion enviada.',
        'info',
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
    setRfqExceptionError('')
    if (!projectId) {
      setRfqExceptionError('Selecciona el desarrollo antes de solicitar la excepcion.')
      return
    }
    if (!title.trim()) {
      setRfqExceptionError('Captura el nombre de la solicitud antes de solicitar la excepcion.')
      return
    }
    if (supplierIds.length === 0) {
      setRfqExceptionError('Selecciona al menos un proveedor para solicitar la excepcion.')
      return
    }
    if (supplierIds.length >= 3) {
      setRfqExceptionError('La excepcion solo aplica cuando hay menos de 3 proveedores.')
      return
    }
    if (validRfqItems.length === 0) {
      setRfqExceptionError('Agrega al menos una partida de material antes de solicitar la excepcion.')
      return
    }
    if (!rfqExceptionNotes.trim()) {
      setRfqExceptionError('Captura el motivo para solicitar la excepcion.')
      return
    }
    setRfqExceptionSubmitting(true)
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
      setRfqExceptionOpen(false)
      setRfqExceptionNotes('')
      setRfqExceptionError('')
      notifySuccess('Solicitud de excepcion enviada a aprobacion.', 'info')
      await loadData(selectedRfq?.id)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'No fue posible enviar la excepcion'
      setRfqExceptionError(message)
      showActionNotice(message, 'error')
    } finally {
      setRfqExceptionSubmitting(false)
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
      notifySuccess(
        `Cotizacion de ${row.supplier_name} borrada. Tienes que volver a seleccionar el proveedor y recapturar los datos.`,
        'warning',
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
      notifySuccess(`Orden ${updated.po_number} enviada al proveedor. Ya puedes consultarla en Ordenes de compra.`)
      await loadData(selectedRfq?.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la orden de compra')
    }
  }

  async function openSupplierQuoteUpload(uploadId: number) {
    setError('')
    try {
      const headers = new Headers()
      const token = getStoredToken()
      if (token) headers.set('Authorization', `Bearer ${token}`)
      const response = await fetch(`${API_BASE_URL}/purchasing/supplier-quote-uploads/${uploadId}/download`, {
        headers,
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(typeof data.detail === 'string' ? data.detail : 'No fue posible abrir el archivo')
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener,noreferrer')
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible abrir el archivo')
    }
  }

  return (
    <div className="space-y-5">
      {focusedPanel ? <div className="acsm-notification-focus-backdrop" aria-hidden="true" /> : null}
      {error && (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
        >
          {error}
        </div>
      )}

      <section
        ref={materialRequisitionRef}
        className={[
          'overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel',
          focusClass('work-requisitions'),
        ].join(' ')}
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-blue">
              <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-acsm-muted">
                Entrada de obra
              </p>
              <h2 className="font-semibold text-acsm-ink">Requerimientos de obra pendientes</h2>
              <p className="text-xs text-acsm-muted">
                Selecciona un requerimiento para cargarlo en la solicitud. Se cerrara al crear la cotizacion.
              </p>
            </div>
          </div>
          <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
            {activeMaterialRequisition ? '1 en captura' : `${materialRequisitionsToShow.length} pendientes`}
          </span>
        </div>
        <div className="border-b border-acsm-line bg-acsm-paper/60 px-4 py-3">
          <input
            value={materialRequisitionSearch}
            onChange={(event) => setMaterialRequisitionSearch(event.target.value)}
            placeholder="Buscar folio, material, desarrollo o solicitante"
            className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
          />
        </div>
        {activeMaterialRequisition ? (
          <div className="border-b border-acsm-line bg-blue-50 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-blue-200 bg-white px-3 py-2">
              <div>
                <p className="text-xs font-bold uppercase text-blue-700">Cargado en la solicitud</p>
                <p className="text-sm font-bold text-acsm-ink">
                  {activeMaterialRequisition.title} · {activeMaterialRequisition.requisition_number}
                </p>
                <p className="text-xs text-acsm-muted">
                  Ya se copio al formulario de cotizacion. Al crear la solicitud dejara de aparecer como pendiente.
                </p>
              </div>
              <button
                type="button"
                onClick={clearRequisitionOrigin}
                className="inline-flex h-9 items-center rounded-md border border-blue-200 bg-blue-50 px-3 text-sm font-bold text-blue-700 hover:bg-blue-100"
              >
                Quitar de captura
              </button>
            </div>
          </div>
        ) : null}
        <div className="max-h-[320px] divide-y divide-acsm-line overflow-y-auto">
          {materialRequisitionsToShow.map((requisition) => (
            <div
              key={requisition.id}
              className="grid gap-3 bg-white px-4 py-3 text-sm transition hover:bg-acsm-paper lg:grid-cols-[minmax(220px,0.9fr)_minmax(300px,1.3fr)_170px_190px]"
            >
              <div>
                <p className="font-bold text-acsm-ink">{requisition.title}</p>
                <p className="font-bold text-acsm-blue">{requisition.requisition_number}</p>
                <span className="mt-2 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700">
                  {statusLabel(requisition.status)}
                </span>
              </div>
              <div>
                <p className="text-xs font-bold uppercase text-acsm-muted">Desarrollo</p>
                <p className="font-semibold text-acsm-ink">
                  {projectNameById.get(requisition.project_id) ?? `Proyecto ${requisition.project_id}`}
                </p>
                <p className="text-xs text-acsm-muted">
                  {requisition.items.length} partidas ·{' '}
                  {requisition.requested_by?.full_name ?? 'Sin solicitante'}
                </p>
              </div>
              <div>
                <p className="text-xs font-bold uppercase text-acsm-muted">Requerida</p>
                <p className="font-semibold text-acsm-ink">{formatDate(requisition.required_date)}</p>
                <p className="text-xs text-acsm-muted">{statusLabel(requisition.priority)}</p>
              </div>
              <div className="flex items-center justify-end">
                <button
                  type="button"
                  onClick={() => loadRequisitionIntoRfq(requisition)}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border border-blue-200 bg-white px-3 text-sm font-bold text-acsm-blue hover:bg-blue-50"
                >
                  <Send className="h-4 w-4" aria-hidden="true" />
                  Cargar a solicitud
                </button>
              </div>
            </div>
          ))}
          {!materialRequisitionsToShow.length ? (
            <div className="px-4 py-10 text-center text-sm text-acsm-muted">
              {activeMaterialRequisition
                ? 'No hay mas requerimientos pendientes. Termina la solicitud cargada o quitala de captura.'
                : 'No hay requerimientos de obra pendientes para convertir en cotizacion.'}
            </div>
          ) : null}
        </div>
      </section>

      <section
        ref={rfqFormRef}
        className={[
          'overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel',
          focusClass('rfq-form'),
        ].join(' ')}
      >
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
            {activeMaterialRequisition ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
                <span>
                  Origen de obra:{' '}
                  <strong>{activeMaterialRequisition.requisition_number}</strong> ·{' '}
                  {activeMaterialRequisition.title}
                </span>
                <button
                  type="button"
                  onClick={clearRequisitionOrigin}
                  className="inline-flex h-8 items-center rounded-md border border-blue-200 bg-white px-3 text-xs font-bold text-blue-700 hover:bg-blue-50"
                >
                  Quitar origen
                </button>
              </div>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm font-semibold text-acsm-ink">
                Desarrollo
                <select
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                  className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                >
                  {rfqProjectOptions.map((project) => (
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
                    onChange={(event) => toggleSupplierSelection(supplier.id, event.target.checked)}
                  />
                </label>
              ))}
              {!filteredSuppliers.length ? (
                <div className="rounded-md border border-acsm-line bg-white px-3 py-4 text-center text-sm text-acsm-muted">
                  No hay proveedores que coincidan con la busqueda.
                </div>
              ) : null}
            </div>
            {fullMatchAgreements.length ? (
              <div className="mt-3 rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
                <div className="font-bold">Convenio disponible</div>
                <p className="mt-1">
                  Puedes solicitar cotizacion directa a un proveedor con convenio para este desarrollo.
                </p>
                <div className="mt-3 space-y-2">
                  {fullMatchAgreements.map(({ agreement }) => (
                    <button
                      key={agreement.id}
                      type="button"
                      onClick={() => useAgreement(agreement)}
                      className={[
                        'block w-full rounded-md border px-3 py-2 text-left transition',
                        selectedAgreement?.id === agreement.id
                          ? 'border-acsm-blue bg-white ring-1 ring-acsm-blue'
                          : 'border-blue-200 bg-white hover:bg-sky-50',
                      ].join(' ')}
                    >
                      <span className="block font-bold text-acsm-ink">{agreement.supplier?.name ?? 'Proveedor'}</span>
                      <span className="block text-acsm-muted">{agreement.name}</span>
                      <span className="mt-1 inline-flex rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 font-bold text-blue-700">
                        Cotizacion directa sin excepcion
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ) : agreementGuidance ? (
              <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <div>
                    <div className="font-bold">{agreementGuidance.title}</div>
                    <p className="mt-1">{agreementGuidance.body}</p>
                    <ul className="mt-2 list-disc space-y-1 pl-4">
                      {agreementGuidance.steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ) : projectId ? (
              <div className="mt-3 rounded-md border border-acsm-line bg-white p-3 text-xs text-acsm-muted">
                No hay convenio activo para la inmobiliaria y modelo de este desarrollo.
              </div>
            ) : null}
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
                    onClick={() => {
                      setRfqExceptionError('')
                      setRfqExceptionOpen(true)
                    }}
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
        {(approvedUnusedRfqExceptions.length || pendingUnusedRfqExceptions.length) ? (
          <div className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-amber-50 px-5 py-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-amber-700">
                  Control de excepciones
                </p>
                <h2 className="text-lg font-bold text-acsm-ink">
                  Excepciones para crear solicitudes
                </h2>
                <p className="text-sm text-acsm-muted">
                  Cuando gerencia aprueba una excepcion, cargala aqui para crear la solicitud con los datos autorizados.
                </p>
              </div>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">
                {approvedUnusedRfqExceptions.length} aprobada(s)
              </span>
            </div>
            <div className="divide-y divide-acsm-line">
              {approvedUnusedRfqExceptions.map((entry) => (
                <div
                  key={entry.id}
                  className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(220px,0.9fr)_minmax(320px,1fr)_220px]"
                >
                  <div>
                    <div className="font-bold text-acsm-ink">{entry.title}</div>
                    <div className="mt-1 text-xs font-semibold text-acsm-muted">
                      {entry.supplier_count} proveedor(es) · {entry.item_count} partida(s)
                    </div>
                  </div>
                  <div className="text-sm text-acsm-muted">
                    <span className="font-semibold text-acsm-ink">
                      Desarrollo:
                    </span>{' '}
                    {projectNameById.get(entry.project_id) ?? `Desarrollo ${entry.project_id}`}
                    <span className="mx-2 text-acsm-muted/60">·</span>
                    <span className="font-semibold text-acsm-ink">Aprobada:</span>{' '}
                    {formatDateTime(entry.decided_at ?? entry.requested_at)}
                  </div>
                  <div className="flex items-center justify-end">
                    <button
                      type="button"
                      onClick={() => loadExceptionIntoRfq(entry)}
                      className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white shadow-button hover:bg-acsm-green-hover"
                    >
                      <Check className="h-4 w-4" aria-hidden="true" />
                      Continuar solicitud
                    </button>
                  </div>
                </div>
              ))}
              {pendingUnusedRfqExceptions.map((entry) => (
                <div
                  key={entry.id}
                  className="grid gap-4 bg-amber-50/50 px-5 py-4 lg:grid-cols-[minmax(220px,0.9fr)_minmax(320px,1fr)_220px]"
                >
                  <div>
                    <div className="font-bold text-acsm-ink">{entry.title}</div>
                    <div className="mt-1 text-xs font-semibold text-amber-800">
                      En revision · {entry.supplier_count} proveedor(es) · {entry.item_count} partida(s)
                    </div>
                  </div>
                  <div className="text-sm text-acsm-muted">
                    Gerencia debe aprobar esta excepcion antes de poder crear la solicitud.
                  </div>
                  <div className="flex items-center justify-end">
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800">
                      Pendiente de aprobacion
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div
          ref={rfqListRef}
          className={[
            'overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel',
            focusClass('rfq-list'),
          ].join(' ')}
        >
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
                      {rfq.request_type === 'agreement' ? (
                        <span className="ml-2 mt-3 inline-flex max-w-full whitespace-normal rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold leading-tight text-emerald-800 sm:text-[11px]">
                          Convenio
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

        <div className={activePurchaseJourney ? 'purchase-workflow-shell' : 'purchase-workflow-shell without-journey'}>
          {activePurchaseJourney && <PurchaseJourneyBar journey={activePurchaseJourney} />}
          <div className="purchase-workflow-content">
        {!selectedRfq && draftPurchaseJourney ? (
          <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
            <div className="border-b border-acsm-line bg-gradient-to-r from-white to-blue-50 px-5 py-4">
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-blue-700">
                Proceso de compras
              </p>
              <h2 className="text-lg font-bold text-acsm-ink">Solicitud pendiente de crear</h2>
              <p className="mt-1 text-sm text-acsm-muted">
                La ruta ya muestra el avance de preparacion. Al crear la solicitud se activan envio a proveedor,
                captura de cotizaciones, comparativo, aprobacion y orden de compra.
              </p>
            </div>
            <div className="grid gap-3 p-5 md:grid-cols-3">
              <div className="rounded-2xl border border-acsm-line bg-white px-4 py-3">
                <p className="text-xs font-bold uppercase text-acsm-muted">Materiales</p>
                <p className="mt-1 text-2xl font-bold text-acsm-ink">{validRfqItems.length}</p>
              </div>
              <div className="rounded-2xl border border-acsm-line bg-white px-4 py-3">
                <p className="text-xs font-bold uppercase text-acsm-muted">Proveedores</p>
                <p className="mt-1 text-2xl font-bold text-acsm-ink">{supplierIds.length}</p>
              </div>
              <div
                className={[
                  'rounded-2xl border px-4 py-3',
                  approvedRfqException
                    ? 'border-emerald-200 bg-emerald-50'
                    : pendingRfqException
                      ? 'border-amber-200 bg-amber-50'
                      : needsRfqException
                        ? 'border-amber-200 bg-amber-50'
                        : 'border-acsm-line bg-white',
                ].join(' ')}
              >
                <p className="text-xs font-bold uppercase text-acsm-muted">Autorizacion</p>
                <p className="mt-1 text-base font-bold text-acsm-ink">
                  {approvedRfqException
                    ? 'Excepcion aprobada'
                    : pendingRfqException
                      ? 'Excepcion en revision'
                      : needsRfqException
                        ? 'Requiere excepcion'
                        : 'Regla normal'}
                </p>
              </div>
            </div>
            <div className="border-t border-acsm-line px-5 py-4">
              <button
                type="button"
                onClick={() => void createRfq()}
                disabled={loading || !canCreateRfq}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
                Crear solicitud de cotizacion
              </button>
            </div>
          </section>
        ) : null}
        {selectedRfq && (
          <section
            ref={quoteCaptureRef}
            className={[
              'purchase-capture-section overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel',
              focusClass('quote-capture'),
            ].join(' ')}
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

        {selectedRfq && (
          <section
            ref={quoteUploadsRef}
            className={[
              'purchase-documents-section overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel',
              focusClass('uploads'),
            ].join(' ')}
          >
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-acsm-line bg-acsm-paper text-acsm-green">
                  <FileText className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <h2 className="font-bold text-acsm-ink">Documentos recibidos de proveedores</h2>
                  <p className="text-sm text-acsm-muted">
                    Archivos cargados desde la liga enviada por correo para {selectedRfq.rfq_number}.
                  </p>
                </div>
              </div>
              <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
                {quoteUploads.length} archivos
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-[860px] w-full text-sm">
                <thead className="bg-acsm-paper text-xs uppercase text-acsm-muted">
                  <tr>
                    <th className="px-4 py-3 text-left">Proveedor</th>
                    <th className="px-4 py-3 text-left">Folio</th>
                    <th className="px-4 py-3 text-left">Archivo</th>
                    <th className="px-4 py-3 text-left">Recibido</th>
                    <th className="px-4 py-3 text-left">Tamano</th>
                    <th className="px-4 py-3 text-right">Accion</th>
                  </tr>
                </thead>
                <tbody>
                  {quoteUploads.map((upload) => (
                    <tr key={upload.id} className="border-t border-acsm-line">
                      <td className="px-4 py-3 font-semibold text-acsm-ink">
                        {upload.supplier?.name ?? `Proveedor ${upload.supplier_id}`}
                      </td>
                      <td className="px-4 py-3 text-acsm-muted">{upload.quote_number || '-'}</td>
                      <td className="max-w-[320px] px-4 py-3">
                        <span className="block truncate font-semibold text-acsm-ink" title={upload.original_file_name}>
                          {upload.original_file_name}
                        </span>
                        <span className="text-xs uppercase text-acsm-muted">{upload.file_extension}</span>
                      </td>
                      <td className="px-4 py-3 text-acsm-muted">{formatDateTime(upload.uploaded_at)}</td>
                      <td className="px-4 py-3 text-acsm-muted">{formatBytes(upload.file_size_bytes)}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => void openSupplierQuoteUpload(upload.id)}
                          className="inline-flex h-9 items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 text-xs font-bold text-blue-800 hover:bg-blue-100"
                        >
                          <Eye className="h-4 w-4" aria-hidden="true" />
                          Abrir archivo
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!quoteUploads.length && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-sm text-acsm-muted">
                        Aun no hay archivos cargados por proveedores para esta solicitud.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
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
                {isAgreementRfq
                  ? `${completeComparison.length} cotizacion completa de 1 requerida por convenio`
                  : `${completeComparison.length} cotizaciones completas de 3 requeridas`}
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
          </div>
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
                  disabled={rfqExceptionSubmitting}
                  rows={5}
                  className="mt-2 w-full rounded-xl border border-acsm-line px-3 py-2 text-sm"
                  placeholder="Ej. Solo existe un proveedor autorizado para este material, no hay tres proveedores activos, entrega urgente..."
                />
              </label>
              {rfqExceptionError ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
                  {rfqExceptionError}
                </div>
              ) : null}
              <div className="flex flex-wrap justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setRfqExceptionOpen(false)}
                  disabled={rfqExceptionSubmitting}
                  className="inline-flex h-10 items-center rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void requestCreateRfqException()}
                  disabled={rfqExceptionSubmitting || !rfqExceptionNotes.trim()}
                  className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white shadow-button hover:bg-acsm-green-hover disabled:opacity-60"
                >
                  {rfqExceptionSubmitting ? (
                    <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                  )}
                  {rfqExceptionSubmitting ? 'Enviando...' : 'Enviar excepcion a aprobacion'}
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
