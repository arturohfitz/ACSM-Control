import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDollarSign,
  ClipboardCheck,
  Clock3,
  CreditCard,
  Download,
  FileCheck2,
  FileText,
  ListChecks,
  PackageCheck,
  RefreshCw,
  Search,
  Upload,
} from 'lucide-react'

import { API_BASE_URL, apiRequest, getStoredToken } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'
import { useAuth } from '../auth/AuthContext'
import FinancialReconciliationPanel from '../components/FinancialReconciliationPanel'

type Supplier = {
  id: number
  name: string
}

type PurchaseOrder = {
  id: number
  project_id: number
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
    line_total: string
    unit: string
    status: string
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
  subtotal?: string | null
  total: string
  currency: string
  status: string
  fiscal_uuid?: string | null
  issuer_tax_id?: string | null
  receiver_tax_id?: string | null
  fiscal_status: string
  fiscal_validation_message?: string | null
  document_name?: string | null
  notes?: string | null
  supplier?: Supplier | null
  purchase_order?: PurchaseOrder | null
  items: SupplierInvoiceItem[]
  documents: SupplierInvoiceDocument[]
}

type SupplierInvoiceDocument = {
  id: number
  document_type: 'pdf' | 'xml' | string
  original_file_name: string
  file_size: number
  validation_status: string
  is_active: boolean
}

type XMLAnalysis = {
  validation_status: string
  validation_message?: string | null
  parsed_data: Record<string, string>
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

type ProjectFinancialProgress = {
  project_id: number
  project_name: string
  client_name: string
  houses_count: string
  models_count: number
  baseline_id?: number | null
  baseline_revision?: number | null
  baseline_approved_at?: string | null
  budget_amount: string
  committed_amount: string
  received_amount: string
  invoiced_amount: string
  paid_amount: string
  available_amount: string
  over_budget_amount: string
  committed_percent: string
  received_percent: string
  invoiced_percent: string
  paid_percent: string
  purchase_orders_count: number
  invoices_count: number
  payments_count: number
  integrity_issues: string[]
}

type ProjectFinancialMaterial = {
  baseline_item_id: number
  house_model_name: string
  source_code?: string | null
  description: string
  unit: string
  budget_quantity: string
  ordered_quantity: string
  received_quantity: string
  budget_amount: string
  committed_amount: string
  invoiced_amount: string
  paid_amount: string
  available_amount: string
  committed_percent: string
  status: string
}

type ProjectFinancialResponse = {
  projects: ProjectFinancialProgress[]
  selected_project_id?: number | null
  materials: ProjectFinancialMaterial[]
}

type PaymentWorkspaceTab = 'pending' | 'invoices' | 'reconciliations' | 'payments' | 'progress'

const workspaceTabs = new Set<PaymentWorkspaceTab>([
  'pending',
  'invoices',
  'reconciliations',
  'payments',
])

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
    document_pending: 'Documentos pendientes',
    fiscal_review: 'Revision fiscal',
    blocked: 'Bloqueada por faltantes',
    approved_for_payment: 'Aprobada para pago',
    scheduled: 'Pago programado',
    paid: 'Pagada',
    reversed: 'Revertida',
    rejected: 'Rechazada',
    pending: 'Pendiente',
    pending_manual: 'Revision manual',
    review_required: 'Requiere revision',
    valid: 'XML validado',
    manual_validated: 'Validada manualmente',
    legacy_validated: 'Registro historico',
  }
  return labels[status] ?? status
}

function percent(value: number, total: number) {
  if (!total) return 0
  return Math.min(100, Math.max(0, (value / total) * 100))
}

function formatQuantity(value: number) {
  return value.toLocaleString('es-MX', { maximumFractionDigits: 4 })
}

function statusPillClass(status: string) {
  if (['closed', 'paid'].includes(status)) return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (['received', 'approved_for_payment', 'scheduled', 'factured'].includes(status)) {
    return 'border-blue-200 bg-blue-50 text-blue-700'
  }
  if (['partially_received', 'blocked'].includes(status)) return 'border-amber-200 bg-amber-50 text-amber-700'
  if (['document_pending', 'fiscal_review'].includes(status)) return 'border-amber-200 bg-amber-50 text-amber-700'
  if (['cancelled', 'rejected', 'reversed'].includes(status)) return 'border-red-200 bg-red-50 text-red-700'
  return 'border-acsm-line bg-white text-acsm-muted'
}

export default function SupplierPaymentsPage() {
  const { hasPermission } = useAuth()
  const canViewInvoices = hasPermission('supplier_invoices:view')
  const canUploadInvoices = hasPermission('supplier_invoices:upload')
  const canValidateInvoices = hasPermission('supplier_invoices:validate')
  const canViewPayments = hasPermission('supplier_payments:view')
  const canSchedulePayments = hasPermission('supplier_payments:schedule')
  const canMarkPaymentsPaid = hasPermission('supplier_payments:pay')
  const canViewProjectFinancials = hasPermission('project_financials:view')
  const canApproveMaterialBudget = hasPermission('project_material_budgets:approve')
  const canViewReconciliations = hasPermission('financial_reconciliations:view')
  const canRequestReconciliations = hasPermission('financial_reconciliations:request')
  const canApproveReconciliations = hasPermission('financial_reconciliations:approve')
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [invoices, setInvoices] = useState<SupplierInvoice[]>([])
  const [payments, setPayments] = useState<SupplierPayment[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [financialData, setFinancialData] = useState<ProjectFinancialResponse>({ projects: [], materials: [] })
  const [selectedProjectId, setSelectedProjectId] = useState(
    () => new URLSearchParams(window.location.search).get('project_id') ?? '',
  )
  const [approvingBudget, setApprovingBudget] = useState(false)
  const [activeView, setActiveView] = useState<PaymentWorkspaceTab>(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('reconciliation_id')) return 'reconciliations'
    const requestedView = params.get('view') as PaymentWorkspaceTab | null
    return requestedView && workspaceTabs.has(requestedView) ? requestedView : 'pending'
  })
  const [materialSearch, setMaterialSearch] = useState('')
  const [materialStatus, setMaterialStatus] = useState('all')
  const [showMaterialDetail, setShowMaterialDetail] = useState(false)
  const [showAllMaterials, setShowAllMaterials] = useState(false)

  const [purchaseOrderId, setPurchaseOrderId] = useState(
    () => new URLSearchParams(window.location.search).get('purchase_order_id') ?? '',
  )
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [invoiceDate, setInvoiceDate] = useState('')
  const [subtotal, setSubtotal] = useState('')
  const [total, setTotal] = useState('')
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [xmlFile, setXmlFile] = useState<File | null>(null)
  const [xmlAnalysis, setXmlAnalysis] = useState<XMLAnalysis | null>(null)
  const [analyzingXML, setAnalyzingXML] = useState(false)
  const [uploadingDocumentKey, setUploadingDocumentKey] = useState('')
  const [invoiceRows, setInvoiceRows] = useState<Record<number, { quantity: string; unit_price: string }>>({})

  const [invoiceToPay, setInvoiceToPay] = useState('')
  const [scheduledDate, setScheduledDate] = useState('')
  const [reference, setReference] = useState('')
  const [paymentAmount, setPaymentAmount] = useState('')

  const invoiceMap = useMemo(
    () => new Map(invoices.map((invoice) => [invoice.id, invoice])),
    [invoices],
  )
  const committedPaymentByInvoice = useMemo(() => {
    const totals = new Map<number, number>()
    for (const payment of payments) {
      if (!['scheduled', 'paid'].includes(payment.status)) continue
      totals.set(
        payment.supplier_invoice_id,
        (totals.get(payment.supplier_invoice_id) ?? 0) + Number(payment.amount || 0),
      )
    }
    return totals
  }, [payments])
  const activeInvoiceStatuses = useMemo(
    () => new Set(['received', 'approved_for_payment', 'scheduled', 'paid']),
    [],
  )
  const selectedOrder = useMemo(
    () => orders.find((order) => String(order.id) === purchaseOrderId) ?? null,
    [orders, purchaseOrderId],
  )
  const selectedOrderInvoices = useMemo(() => {
    if (!selectedOrder) return []
    return invoices.filter((invoice) => invoice.purchase_order_id === selectedOrder.id)
  }, [invoices, selectedOrder])
  const selectedOrderPayments = useMemo(() => {
    if (!selectedOrder) return []
    const invoiceIds = new Set(selectedOrderInvoices.map((invoice) => invoice.id))
    return payments.filter((payment) => invoiceIds.has(payment.supplier_invoice_id))
  }, [payments, selectedOrder, selectedOrderInvoices])
  const invoicedQuantityByItem = useMemo(() => {
    const totals = new Map<number, number>()
    for (const invoice of invoices) {
      if (!activeInvoiceStatuses.has(invoice.status)) continue
      for (const item of invoice.items ?? []) {
        totals.set(
          item.purchase_order_item_id,
          (totals.get(item.purchase_order_item_id) ?? 0) + Number(item.quantity || 0),
        )
      }
    }
    return totals
  }, [activeInvoiceStatuses, invoices])
  const paidQuantityByItem = useMemo(() => {
    const totals = new Map<number, number>()
    for (const invoice of invoices) {
      if (invoice.status !== 'paid') continue
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
  const selectedOrderSummary = useMemo(() => {
    if (!selectedOrder) return null
    const orderedAmount = selectedOrder.items.reduce(
      (sum, item) => sum + Number(item.line_total || 0),
      0,
    )
    const receivedAmount = selectedOrder.items.reduce((sum, item) => {
      const ordered = Number(item.quantity_ordered || 0)
      const received = Math.min(Number(item.received_quantity || 0), ordered)
      return sum + received * Number(item.unit_price || 0)
    }, 0)
    const invoicedAmount = selectedOrderInvoices
      .filter((invoice) => activeInvoiceStatuses.has(invoice.status))
      .reduce((sum, invoice) => sum + Number(invoice.total || 0), 0)
    const paidAmount = selectedOrderPayments
      .filter((payment) => payment.status === 'paid')
      .reduce((sum, payment) => sum + Number(payment.amount || 0), 0)
    const scheduledAmount = selectedOrderPayments
      .filter((payment) => payment.status === 'scheduled')
      .reduce((sum, payment) => sum + Number(payment.amount || 0), 0)
    const blockedInvoices = selectedOrderInvoices.filter((invoice) => invoice.status === 'blocked').length
    const approvedInvoices = selectedOrderInvoices.filter((invoice) => invoice.status === 'approved_for_payment').length
    const orderedLines = selectedOrder.items.length
    const receivedLines = selectedOrder.items.filter(
      (item) => Number(item.received_quantity || 0) >= Number(item.quantity_ordered || 0),
    ).length
    const partialLines = selectedOrder.items.filter((item) => {
      const received = Number(item.received_quantity || 0)
      return received > 0 && received < Number(item.quantity_ordered || 0)
    }).length
    return {
      orderedAmount,
      receivedAmount,
      invoicedAmount,
      paidAmount,
      scheduledAmount,
      blockedInvoices,
      approvedInvoices,
      orderedLines,
      receivedLines,
      partialLines,
      pendingReceiveAmount: Math.max(orderedAmount - receivedAmount, 0),
      pendingPaymentAmount: Math.max(invoicedAmount - paidAmount, 0),
      receptionPercent: percent(receivedAmount, orderedAmount),
      invoicePercent: percent(invoicedAmount, orderedAmount),
      paymentPercent: percent(paidAmount, orderedAmount),
    }
  }, [activeInvoiceStatuses, selectedOrder, selectedOrderInvoices, selectedOrderPayments])
  const selectedOrderItemRows = useMemo(() => {
    if (!selectedOrder) return []
    return selectedOrder.items.map((item) => {
      const ordered = Number(item.quantity_ordered || 0)
      const received = Number(item.received_quantity || 0)
      const invoiced = invoicedQuantityByItem.get(item.id) ?? 0
      const paid = paidQuantityByItem.get(item.id) ?? 0
      const pendingToReceive = Math.max(ordered - received, 0)
      const pendingToInvoice = Math.max(received - invoiced, 0)
      return {
        ...item,
        ordered,
        received,
        invoiced,
        paid,
        pendingToReceive,
        pendingToInvoice,
        receptionPercent: percent(received, ordered),
        invoicePercent: percent(invoiced, ordered),
        paymentPercent: percent(paid, ordered),
      }
    })
  }, [invoicedQuantityByItem, paidQuantityByItem, selectedOrder])
  const selectedProjectFinancial = useMemo(
    () => financialData.projects.find((project) => String(project.project_id) === selectedProjectId) ?? null,
    [financialData.projects, selectedProjectId],
  )
  const selectedProjectInvoices = useMemo(() => {
    if (!selectedProjectId) return invoices
    return invoices.filter((invoice) => {
      const projectId = invoice.purchase_order?.project_id
        ?? orders.find((order) => order.id === invoice.purchase_order_id)?.project_id
      return String(projectId ?? '') === selectedProjectId
    })
  }, [invoices, orders, selectedProjectId])
  const selectedProjectInvoiceIds = useMemo(
    () => new Set(selectedProjectInvoices.map((invoice) => invoice.id)),
    [selectedProjectInvoices],
  )
  const selectedProjectPayments = useMemo(
    () => payments.filter((payment) => selectedProjectInvoiceIds.has(payment.supplier_invoice_id)),
    [payments, selectedProjectInvoiceIds],
  )
  const invoiceAttentionCount = selectedProjectInvoices.filter((invoice) =>
    ['document_pending', 'fiscal_review', 'blocked'].includes(invoice.status),
  ).length
  const projectPayableCount = selectedProjectInvoices.filter((invoice) =>
    invoice.status === 'approved_for_payment',
  ).length
  const projectScheduledCount = selectedProjectPayments.filter((payment) => payment.status === 'scheduled').length
  const projectPaidCount = selectedProjectPayments.filter((payment) => payment.status === 'paid').length
  const reconciliationIssueCount = selectedProjectFinancial?.integrity_issues.length ?? 0
  const hasPendingReception = Boolean(
    selectedProjectFinancial
    && Number(selectedProjectFinancial.committed_amount) > Number(selectedProjectFinancial.received_amount),
  )
  const pendingActionCount =
    (selectedProjectFinancial && !selectedProjectFinancial.baseline_id ? 1 : 0)
    + (hasPendingReception ? 1 : 0)
    + invoiceAttentionCount
    + reconciliationIssueCount
    + projectPayableCount
    + projectScheduledCount
  const filteredFinancialMaterials = useMemo(() => {
    const query = materialSearch.trim().toLocaleLowerCase('es-MX')
    return financialData.materials.filter((material) => {
      const matchesSearch = !query || [material.description, material.source_code, material.house_model_name]
        .some((value) => value?.toLocaleLowerCase('es-MX').includes(query))
      const matchesStatus = materialStatus === 'all' || material.status === materialStatus
      return matchesSearch && matchesStatus
    })
  }, [financialData.materials, materialSearch, materialStatus])
  const visibleFinancialMaterials = showAllMaterials
    ? filteredFinancialMaterials
    : filteredFinancialMaterials.slice(0, 10)

  function openWorkspace(view: PaymentWorkspaceTab) {
    setActiveView(view)
    const url = new URL(window.location.href)
    url.searchParams.set('view', view)
    if (selectedProjectId) url.searchParams.set('project_id', selectedProjectId)
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
    window.requestAnimationFrame(() => {
      document.getElementById(`payments-view-${view}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [orderData, invoiceData, paymentData, projectFinancialData] = await Promise.all([
        apiRequest<PurchaseOrder[]>('/purchasing/purchase-orders'),
        canViewInvoices
          ? apiRequest<SupplierInvoice[]>('/purchasing/supplier-invoices')
          : Promise.resolve([] as SupplierInvoice[]),
        canViewPayments
          ? apiRequest<SupplierPayment[]>('/purchasing/supplier-payments')
          : Promise.resolve([] as SupplierPayment[]),
        canViewProjectFinancials
          ? apiRequest<ProjectFinancialResponse>(
              `/purchasing/project-financial-progress${selectedProjectId ? `?project_id=${selectedProjectId}` : ''}`,
            )
          : Promise.resolve({ projects: [], materials: [] } as ProjectFinancialResponse),
      ])
      setOrders(orderData)
      setInvoices(invoiceData)
      setPayments(paymentData)
      setFinancialData(projectFinancialData)
      if (!purchaseOrderId && orderData[0]) setPurchaseOrderId(String(orderData[0].id))
      if (!selectedProjectId && projectFinancialData.projects[0]) {
        setSelectedProjectId(String(projectFinancialData.projects[0].project_id))
      }
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
    if (!canViewProjectFinancials || !selectedProjectId) return
    setShowAllMaterials(false)
    void apiRequest<ProjectFinancialResponse>(
      `/purchasing/project-financial-progress?project_id=${selectedProjectId}`,
    )
      .then(setFinancialData)
      .catch((err) => setError(err instanceof Error ? err.message : 'No fue posible cargar el avance financiero'))
  }, [canViewProjectFinancials, selectedProjectId])

  useEffect(() => {
    const url = new URL(window.location.href)
    if (selectedProjectId) url.searchParams.set('project_id', selectedProjectId)
    else url.searchParams.delete('project_id')
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
  }, [selectedProjectId])

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

  useEffect(() => {
    const invoice = invoiceMap.get(Number(invoiceToPay))
    if (!invoice) {
      setPaymentAmount('')
      return
    }
    const remaining = Math.max(
      Number(invoice.total || 0) - (committedPaymentByInvoice.get(invoice.id) ?? 0),
      0,
    )
    setPaymentAmount(remaining.toFixed(2))
  }, [committedPaymentByInvoice, invoiceMap, invoiceToPay])

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

  async function analyzeXML(file: File | null) {
    setXmlFile(file)
    setXmlAnalysis(null)
    if (!file) return
    setAnalyzingXML(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const analysis = await apiRequest<XMLAnalysis>(
        '/purchasing/supplier-invoice-documents/analyze-xml',
        { method: 'POST', body: formData },
      )
      setXmlAnalysis(analysis)
      const parsed = analysis.parsed_data
      const fiscalFolio = [parsed.series, parsed.folio].filter(Boolean).join('-')
      if (fiscalFolio) setInvoiceNumber(fiscalFolio)
      if (parsed.issue_datetime) setInvoiceDate(parsed.issue_datetime.slice(0, 10))
      if (parsed.subtotal) setSubtotal(parsed.subtotal)
      if (parsed.total) setTotal(parsed.total)
    } catch (err) {
      setXmlFile(null)
      setError(err instanceof Error ? err.message : 'No fue posible analizar el XML')
    } finally {
      setAnalyzingXML(false)
    }
  }

  async function downloadInvoiceDocument(document: SupplierInvoiceDocument) {
    setError('')
    try {
      const token = getStoredToken()
      const response = await fetch(
        `${API_BASE_URL}/purchasing/supplier-invoice-documents/${document.id}/download`,
        { headers: token ? { Authorization: `Bearer ${token}` } : undefined },
      )
      if (!response.ok) throw new Error('No fue posible descargar el documento')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = window.document.createElement('a')
      link.href = url
      link.download = document.original_file_name
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible descargar el documento')
    }
  }

  async function uploadInvoiceDocument(
    invoice: SupplierInvoice,
    documentType: 'pdf' | 'xml',
    file: File | null,
  ) {
    if (!file) return
    const uploadKey = `${invoice.id}:${documentType}`
    setUploadingDocumentKey(uploadKey)
    setMessage('')
    setError('')
    try {
      const formData = new FormData()
      formData.append('document_type', documentType)
      formData.append('file', file)
      const updated = await apiRequest<SupplierInvoice>(
        `/purchasing/supplier-invoices/${invoice.id}/documents`,
        { method: 'POST', body: formData },
      )
      const successMessage = `${documentType.toUpperCase()} de la factura ${updated.invoice_number} actualizado.`
      setMessage(successMessage)
      showActionNotice(successMessage)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible adjuntar el documento')
    } finally {
      setUploadingDocumentKey('')
    }
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
      const invoiceSubtotal = selectedOrderIsPartial
        ? Number(partialTotal.toFixed(2))
        : xmlAnalysis?.parsed_data.subtotal
          ? Number(xmlAnalysis.parsed_data.subtotal)
          : Number(subtotal)
      const payload = {
        purchase_order_id: Number(purchaseOrderId),
        invoice_number: invoiceNumber,
        invoice_date: invoiceDate,
        subtotal: invoiceSubtotal,
        discount: xmlAnalysis?.parsed_data.discount ? Number(xmlAnalysis.parsed_data.discount) : null,
        transferred_taxes: xmlAnalysis?.parsed_data.transferred_taxes
          ? Number(xmlAnalysis.parsed_data.transferred_taxes)
          : null,
        withheld_taxes: xmlAnalysis?.parsed_data.withheld_taxes
          ? Number(xmlAnalysis.parsed_data.withheld_taxes)
          : null,
        total: Number(total || partialTotal.toFixed(2)),
        currency: xmlAnalysis?.parsed_data.currency || 'MXN',
        exchange_rate: xmlAnalysis?.parsed_data.exchange_rate
          ? Number(xmlAnalysis.parsed_data.exchange_rate)
          : null,
        fiscal_uuid: xmlAnalysis?.parsed_data.fiscal_uuid || null,
        series: xmlAnalysis?.parsed_data.series || null,
        issuer_tax_id: xmlAnalysis?.parsed_data.issuer_tax_id || null,
        receiver_tax_id: xmlAnalysis?.parsed_data.receiver_tax_id || null,
        payment_method: xmlAnalysis?.parsed_data.payment_method || null,
        payment_form: xmlAnalysis?.parsed_data.payment_form || null,
        items: selectedOrderIsPartial ? partialItems : [],
      }
      const formData = new FormData()
      formData.append('payload_json', JSON.stringify(payload))
      if (pdfFile) formData.append('pdf_file', pdfFile)
      if (xmlFile) formData.append('xml_file', xmlFile)
      const created = await apiRequest<SupplierInvoice>('/purchasing/supplier-invoices/register', {
        method: 'POST',
        body: formData,
      })
      const successMessage = `Factura ${created.invoice_number} registrada como ${statusLabel(created.status)}.`
      setMessage(successMessage)
      showActionNotice(successMessage)
      setInvoiceNumber('')
      setSubtotal('')
      setTotal('')
      setPdfFile(null)
      setXmlFile(null)
      setXmlAnalysis(null)
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
          amount: Number(paymentAmount),
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
      setPaymentAmount('')
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

  async function approveMaterialBudget() {
    if (!selectedProjectFinancial) return
    setApprovingBudget(true)
    setError('')
    setMessage('')
    try {
      await apiRequest(
        `/purchasing/projects/${selectedProjectFinancial.project_id}/material-budget-baselines`,
        { method: 'POST', body: JSON.stringify({ notes: 'Linea base aprobada desde Pagos a proveedores' }) },
      )
      const successMessage = `Presupuesto de materiales aprobado para ${selectedProjectFinancial.project_name}.`
      setMessage(successMessage)
      showActionNotice(successMessage)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible aprobar el presupuesto de materiales')
    } finally {
      setApprovingBudget(false)
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
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-acsm-line px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-green">
              <CircleDollarSign className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-acsm-muted">
                Control financiero
              </div>
              <h2 className="font-semibold text-acsm-ink">Pagos a proveedores</h2>
              <p className="text-xs text-acsm-muted">Selecciona un desarrollo y atiende el siguiente paso del proceso.</p>
            </div>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto">
            {canViewProjectFinancials && (
              <select
                aria-label="Desarrollo financiero"
                value={selectedProjectId}
                onChange={(event) => setSelectedProjectId(event.target.value)}
                className="h-9 min-w-0 flex-1 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink sm:min-w-[320px]"
              >
                <option value="">Seleccionar desarrollo</option>
                {financialData.projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.project_name} · {project.client_name}
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper disabled:opacity-60"
              title="Actualizar centro financiero"
            >
              <RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} aria-hidden="true" />
              Actualizar
            </button>
          </div>
        </div>

        {selectedProjectFinancial ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line bg-acsm-paper px-4 py-3">
              <div>
                <div className="font-bold text-acsm-ink">{selectedProjectFinancial.project_name}</div>
                <div className="text-xs text-acsm-muted">
                  {selectedProjectFinancial.client_name} · {formatQuantity(Number(selectedProjectFinancial.houses_count))} viviendas ·{' '}
                  {selectedProjectFinancial.models_count} modelo(s)
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="rounded-full border border-acsm-line bg-white px-2 py-1 font-semibold text-acsm-muted">
                  {selectedProjectFinancial.purchase_orders_count} OC
                </span>
                <span className="rounded-full border border-acsm-line bg-white px-2 py-1 font-semibold text-acsm-muted">
                  {selectedProjectFinancial.invoices_count} facturas
                </span>
                <span className="rounded-full border border-acsm-line bg-white px-2 py-1 font-semibold text-acsm-muted">
                  {selectedProjectFinancial.payments_count} pagos
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 border-b border-acsm-line sm:grid-cols-3 xl:grid-cols-6">
              {[
                {
                  label: 'Recepcion',
                  detail: `${selectedProjectFinancial.received_percent}% recibido`,
                  icon: PackageCheck,
                  attention: hasPendingReception,
                  action: () => window.location.assign(`/inventory/material-receiving?project_id=${selectedProjectId}`),
                },
                {
                  label: 'Factura',
                  detail: `${selectedProjectInvoices.length} registrada(s)`,
                  icon: FileText,
                  attention: selectedProjectInvoices.length === 0 && Number(selectedProjectFinancial.received_amount) > 0,
                  action: () => openWorkspace('invoices'),
                },
                {
                  label: 'Validacion',
                  detail: invoiceAttentionCount ? `${invoiceAttentionCount} por revisar` : 'Sin bloqueos',
                  icon: ClipboardCheck,
                  attention: invoiceAttentionCount > 0,
                  action: () => openWorkspace('invoices'),
                },
                {
                  label: 'Conciliacion',
                  detail: reconciliationIssueCount ? `${reconciliationIssueCount} diferencia(s)` : 'Sin diferencias',
                  icon: ListChecks,
                  attention: reconciliationIssueCount > 0,
                  action: () => openWorkspace('reconciliations'),
                },
                {
                  label: 'Programacion',
                  detail: projectPayableCount ? `${projectPayableCount} lista(s)` : `${projectScheduledCount} programado(s)`,
                  icon: Clock3,
                  attention: projectPayableCount > 0,
                  action: () => openWorkspace('payments'),
                },
                {
                  label: 'Pagado',
                  detail: `${selectedProjectFinancial.paid_percent}% · ${projectPaidCount} pago(s)`,
                  icon: CheckCircle2,
                  attention: false,
                  action: () => openWorkspace('payments'),
                },
              ].map((stage, index) => {
                const StageIcon = stage.icon
                return (
                  <button
                    key={stage.label}
                    type="button"
                    onClick={stage.action}
                    className="group flex min-h-20 items-center gap-3 border-b border-acsm-line px-4 py-3 text-left hover:bg-acsm-paper sm:border-r xl:border-b-0"
                  >
                    <span className={[
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-bold',
                      stage.attention
                        ? 'border-amber-300 bg-amber-50 text-amber-800'
                        : 'border-emerald-200 bg-emerald-50 text-emerald-700',
                    ].join(' ')}>
                      <StageIcon className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[10px] font-bold uppercase text-acsm-muted">Etapa {index + 1}</span>
                      <span className="block text-sm font-bold text-acsm-ink">{stage.label}</span>
                      <span className={stage.attention ? 'block text-xs font-semibold text-amber-800' : 'block text-xs text-acsm-muted'}>
                        {stage.detail}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          </>
        ) : (
          <div className="border-b border-acsm-line px-4 py-6 text-center text-sm text-acsm-muted">
            Selecciona o registra un desarrollo para consultar su proceso financiero.
          </div>
        )}

        <div className="overflow-x-auto border-b border-acsm-line bg-white px-2 pt-2">
          <div className="flex min-w-max gap-1" role="tablist" aria-label="Vistas de pagos a proveedores">
            {[
              { id: 'pending' as const, label: 'Pendientes', count: pendingActionCount, icon: AlertTriangle, allowed: true },
              { id: 'invoices' as const, label: 'Facturas', count: selectedProjectInvoices.length, icon: FileCheck2, allowed: canViewInvoices },
              { id: 'reconciliations' as const, label: 'Conciliaciones', count: reconciliationIssueCount, icon: ListChecks, allowed: canViewReconciliations },
              { id: 'payments' as const, label: 'Pagos', count: selectedProjectPayments.length, icon: CreditCard, allowed: canViewPayments },
            ].filter((tab) => tab.allowed).map((tab) => {
              const TabIcon = tab.icon
              const active = activeView === tab.id
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => openWorkspace(tab.id)}
                  className={[
                    'inline-flex h-10 items-center gap-2 border-b-2 px-3 text-sm font-semibold',
                    active
                      ? 'border-acsm-green text-acsm-green'
                      : 'border-transparent text-acsm-muted hover:border-acsm-line hover:text-acsm-ink',
                  ].join(' ')}
                >
                  <TabIcon className="h-4 w-4" aria-hidden="true" />
                  {tab.label}
                  <span className={active ? 'rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700' : 'rounded-full bg-acsm-paper px-2 py-0.5 text-xs'}>
                    {tab.count}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {activeView === 'pending' && (
          <div id="payments-view-pending" role="tabpanel">
            <div className="flex items-center justify-between gap-3 px-4 py-3">
              <div>
                <h3 className="font-semibold text-acsm-ink">Siguiente paso</h3>
                <p className="text-xs text-acsm-muted">Atiende primero los registros que detienen el flujo de pago.</p>
              </div>
              <span className={pendingActionCount ? 'rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800' : 'rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700'}>
                {pendingActionCount ? `${pendingActionCount} por atender` : 'Sin pendientes'}
              </span>
            </div>
            <div className="border-t border-acsm-line">
              {selectedProjectFinancial && !selectedProjectFinancial.baseline_id && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" aria-hidden="true" />
                    <div>
                      <div className="text-sm font-bold text-acsm-ink">Aprobar presupuesto de materiales</div>
                      <div className="text-xs text-acsm-muted">Define la linea base antes de medir compras y pagos del desarrollo.</div>
                    </div>
                  </div>
                  <button type="button" onClick={() => window.location.assign(`/dashboard/projects/${selectedProjectId}?focus=baseline`)} className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold hover:bg-acsm-paper">
                    Abrir control ejecutivo <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}
              {hasPendingReception && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
                  <div className="flex items-start gap-3">
                    <PackageCheck className="mt-0.5 h-4 w-4 text-blue-700" aria-hidden="true" />
                    <div>
                      <div className="text-sm font-bold text-acsm-ink">Material pendiente de recibir</div>
                      <div className="text-xs text-acsm-muted">Inventarios debe registrar las entregas antes de validar la factura.</div>
                    </div>
                  </div>
                  <button type="button" onClick={() => window.location.assign(`/inventory/material-receiving?project_id=${selectedProjectId}`)} className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold hover:bg-acsm-paper">
                    Ir a recepcion <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}
              {invoiceAttentionCount > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
                  <div className="flex items-start gap-3">
                    <FileCheck2 className="mt-0.5 h-4 w-4 text-amber-700" aria-hidden="true" />
                    <div>
                      <div className="text-sm font-bold text-acsm-ink">{invoiceAttentionCount} factura(s) requieren revision</div>
                      <div className="text-xs text-acsm-muted">Completa documentos, validacion fiscal o faltantes de recepcion.</div>
                    </div>
                  </div>
                  <button type="button" onClick={() => openWorkspace('invoices')} className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold hover:bg-acsm-paper">
                    Revisar facturas <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}
              {reconciliationIssueCount > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-red-100 bg-red-50 px-4 py-3">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-red-700" aria-hidden="true" />
                    <div>
                      <div className="text-sm font-bold text-red-900">{reconciliationIssueCount} diferencia(s) requieren conciliacion</div>
                      <div className="text-xs text-red-800">Corrige el documento o solicita un ajuste controlado antes de pagar.</div>
                    </div>
                  </div>
                  <button type="button" onClick={() => openWorkspace('reconciliations')} className="inline-flex h-9 items-center gap-2 rounded-md border border-red-200 bg-white px-3 text-sm font-semibold text-red-800 hover:bg-red-100">
                    Conciliar <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}
              {projectPayableCount > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
                  <div className="flex items-start gap-3">
                    <CreditCard className="mt-0.5 h-4 w-4 text-emerald-700" aria-hidden="true" />
                    <div>
                      <div className="text-sm font-bold text-acsm-ink">{projectPayableCount} factura(s) listas para programar</div>
                      <div className="text-xs text-acsm-muted">La validacion concluyo; define fecha, monto y referencia del pago.</div>
                    </div>
                  </div>
                  <button type="button" onClick={() => openWorkspace('payments')} className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold hover:bg-acsm-paper">
                    Programar pago <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}
              {projectScheduledCount > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
                  <div className="flex items-start gap-3">
                    <Clock3 className="mt-0.5 h-4 w-4 text-blue-700" aria-hidden="true" />
                    <div>
                      <div className="text-sm font-bold text-acsm-ink">{projectScheduledCount} pago(s) esperan confirmacion</div>
                      <div className="text-xs text-acsm-muted">Confirma el pago realizado para cerrar la etapa financiera.</div>
                    </div>
                  </div>
                  <button type="button" onClick={() => openWorkspace('payments')} className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold hover:bg-acsm-paper">
                    Ver pagos <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}
              {!pendingActionCount && (
                <div className="flex items-center gap-3 px-4 py-6">
                  <CheckCircle2 className="h-5 w-5 text-emerald-700" aria-hidden="true" />
                  <div>
                    <div className="text-sm font-bold text-acsm-ink">El desarrollo no tiene acciones financieras pendientes</div>
                    <div className="text-xs text-acsm-muted">Consulta las facturas, conciliaciones y pagos realizados desde las pestañas superiores.</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {canViewProjectFinancials && activeView === 'progress' && (
        <section id="payments-view-progress" className="scroll-mt-4 overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-green">
                <Building2 className="h-4 w-4" aria-hidden="true" />
              </div>
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-acsm-muted">
                  Control financiero de materiales
                </div>
                <h2 className="font-semibold text-acsm-ink">Avance por desarrollo</h2>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={selectedProjectId}
                onChange={(event) => setSelectedProjectId(event.target.value)}
                className="h-9 min-w-[280px] rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink"
              >
                <option value="">Seleccionar desarrollo</option>
                {financialData.projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.project_name} · {project.client_name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => void loadData()}
                className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
                title="Actualizar avance financiero"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Actualizar
              </button>
            </div>
          </div>

          {!selectedProjectFinancial && (
            <div className="px-4 py-8 text-center text-sm text-acsm-muted">
              No hay desarrollos disponibles para consultar.
            </div>
          )}

          {selectedProjectFinancial && !selectedProjectFinancial.baseline_id && (
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-amber-200 bg-amber-50 px-4 py-3">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden="true" />
                <div>
                  <div className="text-sm font-bold text-amber-900">Falta aprobar el presupuesto de materiales</div>
                  <p className="text-xs text-amber-800">
                    La explosion integrada sera la linea base contra la que se mediran compras y pagos.
                  </p>
                </div>
              </div>
              {canApproveMaterialBudget && (
                <button
                  type="button"
                  onClick={() => void approveMaterialBudget()}
                  disabled={approvingBudget}
                  className="inline-flex h-9 items-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
                >
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  {approvingBudget ? 'Aprobando...' : 'Aprobar linea base'}
                </button>
              )}
            </div>
          )}

          {selectedProjectFinancial && (
            <div>
              <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <h3 className="text-base font-bold text-acsm-ink">{selectedProjectFinancial.project_name}</h3>
                    <p className="text-xs text-acsm-muted">
                      {selectedProjectFinancial.client_name} · {formatQuantity(Number(selectedProjectFinancial.houses_count))} viviendas ·{' '}
                      {selectedProjectFinancial.models_count} modelo(s)
                    </p>
                  </div>
                  <div className="text-right text-xs text-acsm-muted">
                    {selectedProjectFinancial.baseline_revision
                      ? `Linea base revision ${selectedProjectFinancial.baseline_revision}`
                      : 'Sin linea base aprobada'}
                    <div className="font-semibold text-acsm-ink">
                      {selectedProjectFinancial.purchase_orders_count} orden(es) · {selectedProjectFinancial.invoices_count} factura(s) ·{' '}
                      {selectedProjectFinancial.payments_count} pago(s)
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid gap-px border-b border-acsm-line bg-acsm-line sm:grid-cols-2 xl:grid-cols-6">
                {[
                  [
                    'Presupuesto',
                    selectedProjectFinancial.budget_amount,
                    selectedProjectFinancial.baseline_id ? 'Base aprobada' : 'Sin base aprobada',
                  ],
                  ['Comprometido', selectedProjectFinancial.committed_amount, `${selectedProjectFinancial.committed_percent}%`],
                  ['Recibido', selectedProjectFinancial.received_amount, `${selectedProjectFinancial.received_percent}%`],
                  ['Facturado', selectedProjectFinancial.invoiced_amount, `${selectedProjectFinancial.invoiced_percent}%`],
                  [
                    'Pagado material',
                    selectedProjectFinancial.paid_amount,
                    `Neto sin impuestos · ${selectedProjectFinancial.paid_percent}%`,
                  ],
                  [
                    selectedProjectFinancial.baseline_id && Number(selectedProjectFinancial.over_budget_amount) > 0
                      ? 'Excedente'
                      : 'Disponible',
                    Number(selectedProjectFinancial.over_budget_amount) > 0
                      ? selectedProjectFinancial.over_budget_amount
                      : selectedProjectFinancial.available_amount,
                    !selectedProjectFinancial.baseline_id
                      ? 'Sin linea base'
                      : Number(selectedProjectFinancial.over_budget_amount) > 0
                        ? 'Requiere atencion'
                        : 'Por ejercer',
                  ],
                ].map(([label, amount, detail]) => (
                  <div key={label} className="bg-white px-4 py-3">
                    <div className="text-[11px] font-bold uppercase text-acsm-muted">{label}</div>
                    <div className="mt-1 text-lg font-bold text-acsm-ink">{formatMoney(amount)}</div>
                    <div className="text-xs text-acsm-muted">{detail}</div>
                  </div>
                ))}
              </div>

              <div className="border-b border-acsm-line px-4 py-4">
                <div className="grid gap-3 md:grid-cols-4">
                  {[
                    ['Ordenado', selectedProjectFinancial.committed_percent],
                    ['Recibido', selectedProjectFinancial.received_percent],
                    ['Facturado', selectedProjectFinancial.invoiced_percent],
                    ['Pagado', selectedProjectFinancial.paid_percent],
                  ].map(([label, rawPercent]) => {
                    const value = Number(rawPercent)
                    return (
                      <div key={label}>
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span className="font-semibold text-acsm-ink">{label}</span>
                          <span className="text-acsm-muted">{value.toLocaleString('es-MX')}%</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={value > 100 ? 'h-full bg-red-500' : 'h-full bg-acsm-green'}
                            style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {!!selectedProjectFinancial.integrity_issues.length && (
                <div className="border-b border-red-200 bg-red-50 px-4 py-3">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-700" aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-bold text-red-900">Requiere conciliacion</div>
                      {selectedProjectFinancial.integrity_issues.map((issue) => (
                        <p key={issue} className="mt-1 text-xs text-red-800">{issue}</p>
                      ))}
                    </div>
                    {canRequestReconciliations && (
                      <button
                        type="button"
                        onClick={() => openWorkspace('reconciliations')}
                        className="shrink-0 rounded-md border border-red-200 bg-white px-3 py-2 text-xs font-bold text-red-800 hover:bg-red-100"
                      >
                        Iniciar correccion
                      </button>
                    )}
                  </div>
                </div>
              )}

              {!!financialData.materials.length && (
                <div className="border-t border-acsm-line">
                  <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                    <div>
                      <h4 className="text-sm font-bold text-acsm-ink">Detalle por material</h4>
                      <p className="text-xs text-acsm-muted">
                        {financialData.materials.length} partidas de la linea base. Se muestran 10 al abrir el detalle.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowMaterialDetail((current) => !current)}
                      aria-expanded={showMaterialDetail}
                      className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
                    >
                      {showMaterialDetail ? <ChevronUp className="h-4 w-4" aria-hidden="true" /> : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
                      {showMaterialDetail ? 'Ocultar detalle' : 'Mostrar detalle'}
                    </button>
                  </div>

                  {showMaterialDetail && (
                    <div className="border-t border-acsm-line">
                      <div className="grid gap-2 bg-acsm-paper px-4 py-3 md:grid-cols-[minmax(240px,1fr)_220px_auto]">
                        <label className="relative">
                          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-acsm-muted" aria-hidden="true" />
                          <input
                            value={materialSearch}
                            onChange={(event) => {
                              setMaterialSearch(event.target.value)
                              setShowAllMaterials(false)
                            }}
                            placeholder="Buscar material, codigo o modelo"
                            className="h-9 w-full rounded-md border border-acsm-line bg-white pl-9 pr-3 text-sm"
                          />
                        </label>
                        <select
                          aria-label="Estado financiero del material"
                          value={materialStatus}
                          onChange={(event) => {
                            setMaterialStatus(event.target.value)
                            setShowAllMaterials(false)
                          }}
                          className="h-9 rounded-md border border-acsm-line bg-white px-3 text-sm"
                        >
                          <option value="all">Todos los estados</option>
                          <option value="pending">Pendiente</option>
                          <option value="in_progress">En proceso</option>
                          <option value="complete">Completo</option>
                          <option value="over_budget">Excedido</option>
                        </select>
                        <div className="flex h-9 items-center text-xs font-semibold text-acsm-muted">
                          {filteredFinancialMaterials.length} resultado(s)
                        </div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="min-w-[1100px] w-full text-xs">
                          <thead className="bg-acsm-paper uppercase text-acsm-muted">
                            <tr>
                              <th className="px-4 py-3 text-left">Material</th>
                              <th className="px-3 py-3 text-right">Presupuesto</th>
                              <th className="px-3 py-3 text-right">Ordenado</th>
                              <th className="px-3 py-3 text-right">Recibido</th>
                              <th className="px-3 py-3 text-right">Facturado</th>
                              <th className="px-3 py-3 text-right">Pagado</th>
                              <th className="px-4 py-3 text-right">Disponible</th>
                            </tr>
                          </thead>
                          <tbody>
                            {visibleFinancialMaterials.map((material) => (
                              <tr key={material.baseline_item_id} className="border-t border-acsm-line">
                                <td className="px-4 py-3">
                                  <div className="font-semibold text-acsm-ink">{material.description}</div>
                                  <div className="text-acsm-muted">
                                    {material.source_code || 'Sin codigo'} · {material.house_model_name} ·{' '}
                                    {formatQuantity(Number(material.ordered_quantity))} de {formatQuantity(Number(material.budget_quantity))} {material.unit}
                                  </div>
                                </td>
                                <td className="px-3 py-3 text-right font-semibold">{formatMoney(material.budget_amount)}</td>
                                <td className="px-3 py-3 text-right">{formatMoney(material.committed_amount)}</td>
                                <td className="px-3 py-3 text-right">{formatQuantity(Number(material.received_quantity))} {material.unit}</td>
                                <td className="px-3 py-3 text-right">{formatMoney(material.invoiced_amount)}</td>
                                <td className="px-3 py-3 text-right">{formatMoney(material.paid_amount)}</td>
                                <td className={material.status === 'over_budget' ? 'px-4 py-3 text-right font-bold text-red-700' : 'px-4 py-3 text-right font-semibold'}>
                                  {formatMoney(material.available_amount)}
                                </td>
                              </tr>
                            ))}
                            {!visibleFinancialMaterials.length && (
                              <tr>
                                <td colSpan={7} className="px-4 py-8 text-center text-acsm-muted">No hay materiales con estos filtros.</td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                      {filteredFinancialMaterials.length > 10 && (
                        <div className="flex justify-center border-t border-acsm-line px-4 py-3">
                          <button
                            type="button"
                            onClick={() => setShowAllMaterials((current) => !current)}
                            className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-4 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
                          >
                            {showAllMaterials ? 'Mostrar solo 10' : `Ver todos (${filteredFinancialMaterials.length})`}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {activeView === 'reconciliations' && (
        <div id="payments-view-reconciliations" className="scroll-mt-4">
          <FinancialReconciliationPanel
            invoices={invoices}
            payments={payments}
            selectedProjectId={selectedProjectId}
            canView={canViewReconciliations}
            canRequest={canRequestReconciliations}
            canApprove={canApproveReconciliations}
            onApplied={loadData}
          />
        </div>
      )}

      <section id="payments-view-invoices" className={canViewInvoices && activeView === 'invoices' ? 'scroll-mt-4 overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel' : 'hidden'}>
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

        <div className={canUploadInvoices ? 'grid gap-4 p-4 lg:grid-cols-[420px_minmax(0,1fr)]' : 'p-4'}>
          <div className={canUploadInvoices ? 'rounded-md border border-acsm-line bg-acsm-paper p-3' : 'hidden'}>
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
              <div className="rounded-md border border-acsm-line bg-white p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div>
                    <div className="text-xs font-bold uppercase text-acsm-muted">Documentos fiscales</div>
                    <div className="text-xs text-acsm-muted">Adjunta al menos PDF o XML.</div>
                  </div>
                  {xmlAnalysis && (
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] font-bold text-emerald-700">
                      XML leido
                    </span>
                  )}
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="flex min-h-16 cursor-pointer items-center gap-3 rounded-md border border-dashed border-acsm-line bg-acsm-paper px-3 py-2 hover:border-blue-300">
                    <FileText className="h-5 w-5 shrink-0 text-red-600" aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block text-xs font-bold text-acsm-ink">Factura PDF</span>
                      <span className="block truncate text-xs text-acsm-muted">
                        {pdfFile?.name ?? 'Seleccionar PDF'}
                      </span>
                    </span>
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)}
                      className="sr-only"
                    />
                  </label>
                  <label className="flex min-h-16 cursor-pointer items-center gap-3 rounded-md border border-dashed border-acsm-line bg-acsm-paper px-3 py-2 hover:border-blue-300">
                    <Upload className="h-5 w-5 shrink-0 text-blue-700" aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block text-xs font-bold text-acsm-ink">Factura XML</span>
                      <span className="block truncate text-xs text-acsm-muted">
                        {analyzingXML ? 'Analizando...' : xmlFile?.name ?? 'Seleccionar XML'}
                      </span>
                    </span>
                    <input
                      type="file"
                      accept="application/xml,text/xml,.xml"
                      onChange={(event) => void analyzeXML(event.target.files?.[0] ?? null)}
                      className="sr-only"
                    />
                  </label>
                </div>
                {xmlAnalysis && (
                  <div className="mt-2 grid gap-2 rounded-md border border-blue-100 bg-blue-50 p-2 text-xs sm:grid-cols-2">
                    <div>
                      <span className="font-semibold text-blue-900">UUID:</span>{' '}
                      <span className="break-all text-blue-800">{xmlAnalysis.parsed_data.fiscal_uuid}</span>
                    </div>
                    <div>
                      <span className="font-semibold text-blue-900">RFC emisor:</span>{' '}
                      <span className="text-blue-800">{xmlAnalysis.parsed_data.issuer_tax_id}</span>
                    </div>
                  </div>
                )}
              </div>
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
                                onChange={(event) => {
                                  const rawValue = Number(event.target.value || 0)
                                  const nextValue = Math.max(0, Math.min(rawValue, row.available))
                                  patchInvoiceRow(row.id, {
                                    quantity: event.target.value === '' ? '' : String(nextValue),
                                  })
                                }}
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
                  <div className="border-t border-acsm-line p-3">
                    <label className="mb-1 block text-xs font-semibold uppercase text-acsm-muted">
                      Total fiscal de la factura
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={total}
                      onChange={(event) => setTotal(event.target.value)}
                      placeholder={`Base ${formatMoney(partialTotal)}; agrega impuestos si aplica`}
                      className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                    />
                  </div>
                </div>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-semibold uppercase text-acsm-muted">
                      Subtotal materiales
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={subtotal}
                      onChange={(event) => setSubtotal(event.target.value)}
                      placeholder="Importe antes de impuestos"
                      className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-semibold uppercase text-acsm-muted">
                      Total fiscal
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={total}
                      onChange={(event) => setTotal(event.target.value)}
                      placeholder="Total con impuestos"
                      className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
                    />
                  </div>
                </div>
              )}
              <button
                type="button"
                onClick={() => void createInvoice()}
                disabled={
                  loading ||
                  !purchaseOrderId ||
                  !invoiceNumber ||
                  !invoiceDate ||
                  (!pdfFile && !xmlFile) ||
                  analyzingXML ||
                  (selectedOrderIsPartial ? partialTotal <= 0 : !subtotal || !total)
                }
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
              >
                <FileCheck2 className="h-4 w-4" aria-hidden="true" />
                Guardar factura
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {selectedOrder && selectedOrderSummary && (
              <div className="overflow-hidden rounded-md border border-acsm-line bg-white">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-acsm-line bg-acsm-paper px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-white text-acsm-green">
                      <BarChart3 className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-acsm-muted">
                        Control de orden
                      </div>
                      <h3 className="text-base font-semibold text-acsm-ink">
                        {selectedOrder.po_number} · {selectedOrder.supplier?.name ?? 'Proveedor'}
                      </h3>
                    </div>
                  </div>
                  <div
                    className={[
                      'rounded-full border px-3 py-1 text-xs font-bold',
                      statusPillClass(selectedOrder.status),
                    ].join(' ')}
                  >
                    {statusLabel(selectedOrder.status)}
                  </div>
                </div>

                <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-md border border-acsm-line bg-white p-3">
                    <div className="text-xs font-semibold uppercase text-acsm-muted">Pedido</div>
                    <div className="mt-1 text-lg font-bold text-acsm-ink">
                      {formatMoney(selectedOrderSummary.orderedAmount)}
                    </div>
                    <div className="text-xs text-acsm-muted">
                      {selectedOrderSummary.orderedLines} partidas
                    </div>
                  </div>
                  <div className="rounded-md border border-blue-100 bg-blue-50 p-3">
                    <div className="text-xs font-semibold uppercase text-blue-700">Recibido</div>
                    <div className="mt-1 text-lg font-bold text-blue-900">
                      {selectedOrderSummary.receptionPercent.toFixed(0)}%
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-white">
                      <div
                        className="h-2 rounded-full bg-blue-500"
                        style={{ width: `${selectedOrderSummary.receptionPercent}%` }}
                      />
                    </div>
                    <div className="mt-2 text-xs text-blue-800">
                      {selectedOrderSummary.receivedLines} completas · {selectedOrderSummary.partialLines} parciales
                    </div>
                  </div>
                  <div className="rounded-md border border-cyan-100 bg-cyan-50 p-3">
                    <div className="text-xs font-semibold uppercase text-cyan-700">Facturado</div>
                    <div className="mt-1 text-lg font-bold text-cyan-900">
                      {formatMoney(selectedOrderSummary.invoicedAmount)}
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-white">
                      <div
                        className="h-2 rounded-full bg-cyan-500"
                        style={{ width: `${selectedOrderSummary.invoicePercent}%` }}
                      />
                    </div>
                    <div className="mt-2 text-xs text-cyan-800">
                      {selectedOrderSummary.approvedInvoices} listas · {selectedOrderSummary.blockedInvoices} bloqueadas
                    </div>
                  </div>
                  <div className="rounded-md border border-emerald-100 bg-emerald-50 p-3">
                    <div className="text-xs font-semibold uppercase text-emerald-700">Pagado</div>
                    <div className="mt-1 text-lg font-bold text-emerald-900">
                      {formatMoney(selectedOrderSummary.paidAmount)}
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-white">
                      <div
                        className="h-2 rounded-full bg-emerald-500"
                        style={{ width: `${selectedOrderSummary.paymentPercent}%` }}
                      />
                    </div>
                    <div className="mt-2 text-xs text-emerald-800">
                      {formatMoney(selectedOrderSummary.pendingPaymentAmount)} pendiente
                    </div>
                  </div>
                </div>

                <div className="border-t border-acsm-line px-4 py-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h4 className="text-sm font-semibold text-acsm-ink">Partidas de la orden</h4>
                      <p className="text-xs text-acsm-muted">
                        Cantidades contra recepcion, facturacion y pago.
                      </p>
                    </div>
                    <div className="text-xs font-semibold text-acsm-muted">
                      Pendiente por recibir: {formatMoney(selectedOrderSummary.pendingReceiveAmount)}
                    </div>
                  </div>
                  <div className="overflow-x-auto rounded-md border border-acsm-line">
                    <table className="min-w-[920px] w-full text-xs">
                      <thead className="bg-acsm-paper uppercase text-acsm-muted">
                        <tr>
                          <th className="px-3 py-2 text-left">Material</th>
                          <th className="px-3 py-2 text-right">Pedido</th>
                          <th className="px-3 py-2 text-right">Recibido</th>
                          <th className="px-3 py-2 text-right">Facturado</th>
                          <th className="px-3 py-2 text-right">Pagado</th>
                          <th className="px-3 py-2 text-left">Avance</th>
                          <th className="px-3 py-2 text-left">Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedOrderItemRows.map((item) => (
                          <tr key={item.id} className="border-t border-acsm-line">
                            <td className="px-3 py-2">
                              <div className="font-semibold text-acsm-ink">{item.description}</div>
                              <div className="text-acsm-muted">{item.unit}</div>
                            </td>
                            <td className="px-3 py-2 text-right">
                              {formatQuantity(item.ordered)} {item.unit}
                            </td>
                            <td className="px-3 py-2 text-right">
                              {formatQuantity(item.received)} {item.unit}
                            </td>
                            <td className="px-3 py-2 text-right">
                              {formatQuantity(item.invoiced)} {item.unit}
                            </td>
                            <td className="px-3 py-2 text-right">
                              {formatQuantity(item.paid)} {item.unit}
                            </td>
                            <td className="px-3 py-2">
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="w-16 text-[11px] text-acsm-muted">Rec.</span>
                                  <div className="h-1.5 flex-1 rounded-full bg-slate-100">
                                    <div
                                      className="h-1.5 rounded-full bg-blue-500"
                                      style={{ width: `${item.receptionPercent}%` }}
                                    />
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="w-16 text-[11px] text-acsm-muted">Fact.</span>
                                  <div className="h-1.5 flex-1 rounded-full bg-slate-100">
                                    <div
                                      className="h-1.5 rounded-full bg-cyan-500"
                                      style={{ width: `${item.invoicePercent}%` }}
                                    />
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="w-16 text-[11px] text-acsm-muted">Pago</span>
                                  <div className="h-1.5 flex-1 rounded-full bg-slate-100">
                                    <div
                                      className="h-1.5 rounded-full bg-emerald-500"
                                      style={{ width: `${item.paymentPercent}%` }}
                                    />
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={[
                                  'inline-flex rounded-full border px-2 py-1 text-[11px] font-bold',
                                  statusPillClass(item.status),
                                ].join(' ')}
                              >
                                {statusLabel(item.status)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            <div className="overflow-x-auto rounded-md border border-acsm-line">
              <table className="min-w-[1080px] w-full text-sm">
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
                      <td className="px-4 py-3">
                        <div className="font-semibold text-acsm-ink">{invoice.invoice_number}</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {(invoice.documents ?? [])
                            .filter((document) => document.is_active)
                            .map((document) => (
                              <button
                                key={document.id}
                                type="button"
                                onClick={() => void downloadInvoiceDocument(document)}
                                className="inline-flex items-center gap-1 rounded-full border border-acsm-line bg-white px-2 py-1 text-[11px] font-bold uppercase text-blue-700 hover:bg-blue-50"
                              >
                                <Download className="h-3 w-3" aria-hidden="true" />
                                {document.document_type}
                              </button>
                            ))}
                        </div>
                        <div className="mt-1 text-[11px] text-acsm-muted">
                          Fiscal: {statusLabel(invoice.fiscal_status)}
                        </div>
                      </td>
                      <td className="px-4 py-3">{invoice.supplier?.name ?? invoice.supplier_id}</td>
                      <td className="px-4 py-3">{invoice.purchase_order?.po_number ?? invoice.purchase_order_id}</td>
                      <td className="px-4 py-3">{invoice.due_date}</td>
                      <td className="px-4 py-3">{formatMoney(invoice.total)}</td>
                      <td className="px-4 py-3">
                        <span
                          className={[
                            'inline-flex rounded-full border px-2 py-1 text-xs font-bold',
                            statusPillClass(invoice.status),
                          ].join(' ')}
                        >
                          {statusLabel(invoice.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {canUploadInvoices && (['pdf', 'xml'] as const).map((documentType) => {
                            const hasDocument = (invoice.documents ?? []).some(
                              (document) => document.is_active && document.document_type === documentType,
                            )
                            const uploadKey = `${invoice.id}:${documentType}`
                            const documentsLocked = ['scheduled', 'paid'].includes(invoice.status)
                            return (
                              <label
                                key={documentType}
                                title={`${hasDocument ? 'Reemplazar' : 'Adjuntar'} ${documentType.toUpperCase()}`}
                                className={[
                                  'inline-flex h-9 cursor-pointer items-center gap-1 rounded-md border px-2 text-xs font-bold uppercase',
                                  hasDocument
                                    ? 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
                                    : 'border-acsm-line bg-white text-acsm-muted hover:bg-acsm-paper',
                                  documentsLocked ? 'pointer-events-none cursor-not-allowed opacity-50' : '',
                                ].join(' ')}
                              >
                                <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                                {uploadingDocumentKey === uploadKey ? 'Subiendo' : documentType}
                                <input
                                  type="file"
                                  accept={
                                    documentType === 'pdf'
                                      ? 'application/pdf,.pdf'
                                      : 'application/xml,text/xml,.xml'
                                  }
                                  disabled={documentsLocked || Boolean(uploadingDocumentKey)}
                                  aria-label={`${hasDocument ? 'Reemplazar' : 'Adjuntar'} ${documentType.toUpperCase()} de ${invoice.invoice_number}`}
                                  onChange={(event) => {
                                    const selectedFile = event.target.files?.[0] ?? null
                                    event.target.value = ''
                                    void uploadInvoiceDocument(invoice, documentType, selectedFile)
                                  }}
                                  className="sr-only"
                                />
                              </label>
                            )
                          })}
                          {canValidateInvoices && <button
                            type="button"
                            onClick={() => void validateInvoice(invoice.id)}
                            disabled={
                              !(invoice.documents ?? []).some((document) => document.is_active) ||
                              ['approved_for_payment', 'scheduled', 'paid'].includes(invoice.status) ||
                              Boolean(uploadingDocumentKey)
                            }
                            className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                            Revisar
                          </button>}
                          {!canUploadInvoices && !canValidateInvoices && (
                            <span className="text-xs font-medium text-acsm-muted">Solo consulta</span>
                          )}
                        </div>
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
        </div>
      </section>

      <section id="payments-view-payments" className={canViewPayments && activeView === 'payments' ? 'scroll-mt-4 grid gap-5 lg:grid-cols-[420px_minmax(0,1fr)]' : 'hidden'}>
        <div className={canSchedulePayments ? 'rounded-md border border-acsm-line bg-white p-4 shadow-panel' : 'hidden'}>
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
              type="number"
              min="0.01"
              step="0.01"
              value={paymentAmount}
              onChange={(event) => setPaymentAmount(event.target.value)}
              placeholder="Monto a programar"
              className="h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
            />
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
              disabled={!invoiceToPay || Number(paymentAmount) <= 0}
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
                        {canMarkPaymentsPaid ? <button
                          type="button"
                          onClick={() => void markPaid(payment)}
                          disabled={payment.status !== 'scheduled'}
                          className="inline-flex h-9 items-center gap-2 rounded-md border border-acsm-line bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper disabled:opacity-60"
                        >
                          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                          Pagado
                        </button> : <span className="text-acsm-muted">-</span>}
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
