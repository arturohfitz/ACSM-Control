import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileUp,
  PackageCheck,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  Truck,
  Warehouse,
} from 'lucide-react'

import { apiRequest } from '../lib/api'

type Project = {
  id: number
  name: string
}

type ProjectWarehouse = {
  id: number
  project_id: number
  name: string
  location?: string | null
}

type InventoryRow = {
  local_id: string
  source_code: string
  description: string
  unit: string
  expected_quantity: string
  unit_price: string
  line_total: string
  delivery_date: string
  received_quantity: string
  notes: string
}

type ExpectedMaterialItem = {
  id: number
  purchase_order_item_id?: number | null
  description: string
  unit: string
  expected_quantity: string
  received_quantity: string
  status: string
  notes?: string | null
}

type ParsedDocument = {
  metadata: {
    document_number?: string | null
    supplier_name?: string | null
    document_date?: string | null
    delivery_date?: string | null
    source_document_name?: string | null
    source_document_hash?: string | null
  }
  items: Array<Omit<InventoryRow, 'local_id'>>
}

type ExpectedMaterialList = {
  id: number
  warehouse_id?: number | null
  purchase_order_id?: number | null
  name: string
  document_number?: string | null
  supplier_name?: string | null
  source_document_name?: string | null
  source_document_hash?: string | null
  items: ExpectedMaterialItem[]
}

type PurchaseOrder = {
  id: number
  project_id: number
  warehouse_id?: number | null
  po_number: string
  status: string
  subtotal: string
  supplier?: { id: number; name: string } | null
  items: {
    id: number
    description: string
    unit: string
    quantity_ordered: string
    received_quantity: string
    status: string
  }[]
}

type PurchaseOrderReceiveRow = {
  expected_item_id: number
  description: string
  unit: string
  pending_quantity: number
  received_quantity: string
  condition_status: 'ok' | 'damaged' | 'incomplete' | 'extra' | 'other'
  notes: string
}

type InventoryStatusItem = {
  expected_item_id: number
  source_code?: string | null
  description: string
  unit: string
  expected_quantity: string
  received_quantity: string
  pending_quantity: string
  status: string
  notes?: string | null
}

type MaterialReception = {
  id: number
  received_at: string
  delivery_reference?: string | null
  received_by?: string | null
  items: { id: number; description: string; received_quantity: string; unit: string }[]
}

type WarehouseStock = {
  id: number
  warehouse_id: number
  description: string
  unit: string
  quantity_on_hand: string
}

type InventoryMode =
  | 'purchase_order'
  | 'external_document'
  | 'document_validation'
  | 'documents'
  | 'missing'
  | 'stock'

function newRow(overrides: Partial<InventoryRow> = {}): InventoryRow {
  return {
    local_id: crypto.randomUUID(),
    source_code: '',
    description: '',
    unit: '',
    expected_quantity: '',
    unit_price: '',
    line_total: '',
    delivery_date: '',
    received_quantity: '',
    notes: '',
    ...overrides,
  }
}

function formatQuantity(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '0'
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return String(value)
  return parsed.toLocaleString('es-MX', { maximumFractionDigits: 4 })
}

function numberOrNull(value: string) {
  return value.trim() === '' ? null : Number(value)
}

function textOrNull(value: string) {
  return value.trim() === '' ? null : value.trim()
}

function normalizeDocumentKey(value: string | null | undefined) {
  return value?.trim().replace(/\s+/g, ' ').toLowerCase() ?? ''
}

function documentLabel(list: ExpectedMaterialList) {
  return list.document_number || list.source_document_name || list.name
}

function isPdfFile(file: File) {
  return file.type === 'application/pdf' || /\.pdf$/i.test(file.name)
}

function isImageFile(file: File) {
  return file.type.startsWith('image/') || /\.(jpe?g|png|webp)$/i.test(file.name)
}

async function hashFile(file: File) {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

async function prepareImageForOcr(file: File) {
  const bitmap = await createImageBitmap(file)
  const longestSide = Math.max(bitmap.width, bitmap.height)
  const scale = longestSide < 2200 ? Math.min(2.4, 2200 / longestSide) : 1
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  const context = canvas.getContext('2d')
  if (!context) return file
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.filter = 'grayscale(1) contrast(1.35) brightness(1.08)'
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return new Promise<Blob>((resolve) => {
    canvas.toBlob((blob) => resolve(blob ?? file), 'image/png')
  })
}

async function extractTextFromImage(file: File, onProgress: (message: string) => void) {
  const { createWorker, OEM, PSM } = await import('tesseract.js')
  const image = await prepareImageForOcr(file)
  const worker = await createWorker(['spa', 'eng'], OEM.LSTM_ONLY, {
    logger: (message) => {
      if (message.status === 'recognizing text') {
        onProgress(`OCR de imagen: ${Math.round(message.progress * 100)}%`)
      }
    },
  })
  try {
    await worker.setParameters({
      preserve_interword_spaces: '1',
      tessedit_pageseg_mode: PSM.AUTO,
      user_defined_dpi: '220',
    })
    const {
      data: { text },
    } = await worker.recognize(image)
    const primaryText = text.trim()
    if (/\bP\s*33\s*[-–]?\s*\d{3,8}\b/i.test(primaryText)) {
      return primaryText
    }

    onProgress('OCR de imagen: buscando folio...')
    await worker.setParameters({
      preserve_interword_spaces: '1',
      tessedit_pageseg_mode: PSM.SPARSE_TEXT,
      user_defined_dpi: '220',
    })
    const {
      data: { text: sparseText },
    } = await worker.recognize(image)
    return `${primaryText}\n${sparseText}`.trim()
  } finally {
    await worker.terminate()
  }
}

function parsedRows(document: ParsedDocument): InventoryRow[] {
  return document.items.map((item) =>
    newRow({
      source_code: item.source_code ?? '',
      description: item.description ?? '',
      unit: item.unit ?? '',
      expected_quantity: String(item.expected_quantity ?? ''),
      unit_price: item.unit_price ? String(item.unit_price) : '',
      line_total: item.line_total ? String(item.line_total) : '',
      delivery_date: item.delivery_date ?? '',
      received_quantity: item.received_quantity ? String(item.received_quantity) : '',
      notes: item.notes ?? '',
    }),
  )
}

export default function InventoryPage({ mode = 'purchase_order' }: { mode?: InventoryMode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState('')
  const [warehouses, setWarehouses] = useState<ProjectWarehouse[]>([])
  const [warehouseId, setWarehouseId] = useState('')
  const [expectedLists, setExpectedLists] = useState<ExpectedMaterialList[]>([])
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([])
  const [selectedPurchaseOrderId, setSelectedPurchaseOrderId] = useState('')
  const [poReceiveRows, setPoReceiveRows] = useState<PurchaseOrderReceiveRow[]>([])
  const [poDeliveredBy, setPoDeliveredBy] = useState('')
  const [poReceivedBy, setPoReceivedBy] = useState('')
  const [poDeliveryReference, setPoDeliveryReference] = useState('')
  const [statusItems, setStatusItems] = useState<InventoryStatusItem[]>([])
  const [missingItems, setMissingItems] = useState<InventoryStatusItem[]>([])
  const [receptions, setReceptions] = useState<MaterialReception[]>([])
  const [stockItems, setStockItems] = useState<WarehouseStock[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [sourceText, setSourceText] = useState('')
  const [documentNumber, setDocumentNumber] = useState('')
  const [supplierName, setSupplierName] = useState('')
  const [documentDate, setDocumentDate] = useState('')
  const [deliveryDate, setDeliveryDate] = useState('')
  const [documentName, setDocumentName] = useState('')
  const [documentHash, setDocumentHash] = useState('')
  const [receivedBy, setReceivedBy] = useState('')
  const [rows, setRows] = useState<InventoryRow[]>([newRow()])

  const selectedProject = useMemo(
    () => projects.find((project) => String(project.id) === projectId),
    [projectId, projects],
  )

  const duplicateDocument = useMemo(() => {
    const currentHash = normalizeDocumentKey(documentHash)
    const currentNumber = normalizeDocumentKey(documentNumber)
    const currentName = normalizeDocumentKey(documentName || documentFile?.name)
    if (!currentHash && !currentNumber && !currentName) return null

    return (
      expectedLists.find((list) => {
        const listHash = normalizeDocumentKey(list.source_document_hash)
        const listNumber = normalizeDocumentKey(list.document_number)
        const listName = normalizeDocumentKey(list.source_document_name)
        return Boolean(
          (currentHash && listHash === currentHash) ||
            (currentNumber && listNumber === currentNumber) ||
            (currentName && listName === currentName),
        )
      }) ?? null
    )
  }, [documentFile, documentHash, documentName, documentNumber, expectedLists])

  const projectPurchaseOrders = useMemo(
    () =>
      purchaseOrders.filter((order) => String(order.project_id) === projectId),
    [projectId, purchaseOrders],
  )

  const receivablePurchaseOrders = useMemo(
    () =>
      projectPurchaseOrders.filter(
        (order) =>
          !['closed', 'cancelled'].includes(order.status) &&
          order.items.some(
            (item) => Number(item.received_quantity) < Number(item.quantity_ordered),
          ),
      ),
    [projectPurchaseOrders],
  )

  const selectedPurchaseOrder = useMemo(
    () =>
      projectPurchaseOrders.find((order) => String(order.id) === selectedPurchaseOrderId) ??
      null,
    [projectPurchaseOrders, selectedPurchaseOrderId],
  )

  const selectedPurchaseOrderList = useMemo(
    () =>
      expectedLists.find(
        (list) => String(list.purchase_order_id ?? '') === selectedPurchaseOrderId,
      ) ?? null,
    [expectedLists, selectedPurchaseOrderId],
  )

  const showPurchaseOrderReceiving = mode === 'purchase_order'
  const showExternalDocument = mode === 'external_document' || mode === 'document_validation'
  const showDocuments = mode === 'documents'
  const showMissing = mode === 'missing'
  const showStock = mode === 'stock'

  async function loadCatalogs() {
    setLoading(true)
    setError('')
    try {
      const projectData = await apiRequest<Project[]>('/projects')
      setProjects(projectData)
      if (!projectId && projectData[0]) setProjectId(String(projectData[0].id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar desarrollos')
    } finally {
      setLoading(false)
    }
  }

  async function loadProjectInventory(currentProjectId = projectId) {
    if (!currentProjectId) return
    setError('')
    try {
      const [warehouseData, expectedData, statusData, missingData, receptionData, orderData] =
        await Promise.all([
          apiRequest<ProjectWarehouse[]>(`/inventory/projects/${currentProjectId}/warehouses`),
          apiRequest<ExpectedMaterialList[]>(
            `/inventory/projects/${currentProjectId}/expected-materials`,
          ),
          apiRequest<InventoryStatusItem[]>(`/inventory/projects/${currentProjectId}/status`),
          apiRequest<InventoryStatusItem[]>(
            `/inventory/projects/${currentProjectId}/missing-materials`,
          ),
          apiRequest<MaterialReception[]>(`/inventory/projects/${currentProjectId}/receptions`),
          apiRequest<PurchaseOrder[]>('/purchasing/purchase-orders'),
        ])
      setWarehouses(warehouseData)
      setExpectedLists(expectedData)
      setStatusItems(statusData)
      setMissingItems(missingData)
      setReceptions(receptionData)
      setPurchaseOrders(orderData)
      setWarehouseId((current) => current || (warehouseData[0] ? String(warehouseData[0].id) : ''))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar inventario')
    }
  }

  async function loadWarehouseStock(currentWarehouseId = warehouseId) {
    if (!currentWarehouseId) {
      setStockItems([])
      return
    }
    try {
      const data = await apiRequest<WarehouseStock[]>(
        `/inventory/warehouses/${currentWarehouseId}/stock`,
      )
      setStockItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar existencias')
    }
  }

  useEffect(() => {
    void loadCatalogs()
  }, [])

  useEffect(() => {
    if (projectId) {
      setWarehouseId('')
      setSelectedPurchaseOrderId('')
      setPoReceiveRows([])
      void loadProjectInventory(projectId)
    }
  }, [projectId])

  useEffect(() => {
    if (warehouseId) {
      void loadWarehouseStock(warehouseId)
    } else {
      setStockItems([])
    }
  }, [warehouseId])

  function applyParsedDocument(document: ParsedDocument) {
    setDocumentNumber(document.metadata.document_number ?? documentNumber)
    setSupplierName(document.metadata.supplier_name ?? supplierName)
    setDocumentDate(document.metadata.document_date ?? documentDate)
    setDeliveryDate(document.metadata.delivery_date ?? deliveryDate)
    setDocumentName(document.metadata.source_document_name ?? documentName)
    setDocumentHash(document.metadata.source_document_hash ?? '')
    const nextRows = parsedRows(document)
    setRows(nextRows.length ? nextRows : [newRow()])
  }

  function selectPurchaseOrder(orderId: string) {
    setSelectedPurchaseOrderId(orderId)
    const order = projectPurchaseOrders.find((item) => String(item.id) === orderId)
    const expectedList =
      expectedLists.find((list) => String(list.purchase_order_id ?? '') === orderId) ?? null
    if (!order || !expectedList) {
      setPoReceiveRows([])
      return
    }
    if (expectedList.warehouse_id) {
      setWarehouseId(String(expectedList.warehouse_id))
    } else if (order.warehouse_id) {
      setWarehouseId(String(order.warehouse_id))
    }
    setPoDeliveryReference(order.po_number)
    setPoDeliveredBy(order.supplier?.name ?? '')
    setPoReceiveRows(
      expectedList.items
        .map((item) => {
          const pending = Math.max(
            Number(item.expected_quantity) - Number(item.received_quantity),
            0,
          )
          return {
            expected_item_id: item.id,
            description: item.description,
            unit: item.unit,
            pending_quantity: pending,
            received_quantity: pending > 0 ? String(pending) : '',
            condition_status: 'ok' as const,
            notes: '',
          }
        })
        .filter((item) => item.pending_quantity > 0),
    )
  }

  function updatePoReceiveRow(
    expectedItemId: number,
    patch: Partial<PurchaseOrderReceiveRow>,
  ) {
    setPoReceiveRows((current) =>
      current.map((row) =>
        row.expected_item_id === expectedItemId ? { ...row, ...patch } : row,
      ),
    )
  }

  async function savePurchaseOrderReception() {
    if (!projectId || !selectedPurchaseOrderList || !warehouseId) return
    const validRows = poReceiveRows.filter((row) => Number(row.received_quantity) > 0)
    if (!validRows.length) {
      setError('Captura al menos una cantidad recibida de la orden de compra')
      return
    }
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await apiRequest(`/inventory/projects/${projectId}/receptions`, {
        method: 'POST',
        body: JSON.stringify({
          warehouse_id: Number(warehouseId),
          expected_list_id: selectedPurchaseOrderList.id,
          delivery_reference: textOrNull(poDeliveryReference),
          delivered_by: textOrNull(poDeliveredBy),
          received_by: textOrNull(poReceivedBy || receivedBy),
          notes: `Recepcion contra orden de compra ${selectedPurchaseOrder?.po_number ?? ''}`.trim(),
          items: validRows.map((row) => ({
            expected_item_id: row.expected_item_id,
            received_quantity: Number(row.received_quantity),
            condition_status: row.condition_status,
            notes: textOrNull(row.notes),
          })),
        }),
      })
      setNotice(`Recepcion registrada contra ${selectedPurchaseOrder?.po_number ?? 'orden de compra'}`)
      setPoReceiveRows([])
      setSelectedPurchaseOrderId('')
      setPoDeliveredBy('')
      setPoReceivedBy('')
      setPoDeliveryReference('')
      await loadProjectInventory(projectId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible registrar la recepcion')
    } finally {
      setSaving(false)
    }
  }

  async function parsePdf() {
    if (!projectId || !documentFile) return
    setSaving(true)
    setError('')
    setNotice('')
    try {
      if (isImageFile(documentFile)) {
        setNotice('Leyendo imagen con OCR...')
        const [sourceTextFromImage, sourceDocumentHash] = await Promise.all([
          extractTextFromImage(documentFile, setNotice),
          hashFile(documentFile),
        ])
        if (!sourceTextFromImage) {
          throw new Error('No se detecto texto en la imagen. Toma la foto mas cerca y con mejor luz.')
        }
        const data = await apiRequest<ParsedDocument>(
          `/inventory/projects/${projectId}/quick-documents/parse-text`,
          {
            method: 'POST',
            body: JSON.stringify({
              source_text: sourceTextFromImage,
              source_document_name: documentFile.name,
            }),
          },
        )
        applyParsedDocument(data)
        setDocumentHash(sourceDocumentHash)
        setNotice(`Imagen interpretada con OCR: ${data.items.length} partidas`)
        return
      }

      if (!isPdfFile(documentFile)) {
        throw new Error('Selecciona un PDF o una imagen JPG, PNG o WEBP')
      }

      const formData = new FormData()
      formData.append('file', documentFile)
      const data = await apiRequest<ParsedDocument>(
        `/inventory/projects/${projectId}/quick-documents/parse-pdf`,
        { method: 'POST', body: formData },
      )
      applyParsedDocument(data)
      setNotice(`PDF interpretado: ${data.items.length} partidas`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible interpretar documento')
    } finally {
      setSaving(false)
    }
  }

  async function parseText() {
    if (!projectId || !sourceText.trim()) return
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const data = await apiRequest<ParsedDocument>(
        `/inventory/projects/${projectId}/quick-documents/parse-text`,
        {
          method: 'POST',
          body: JSON.stringify({
            source_text: sourceText,
            source_document_name: documentName || null,
          }),
        },
      )
      applyParsedDocument(data)
      setNotice(`Texto interpretado: ${data.items.length} partidas`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible interpretar texto')
    } finally {
      setSaving(false)
    }
  }

  function updateRow(index: number, field: keyof InventoryRow, value: string) {
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)),
    )
  }

  async function saveQuickDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!projectId) return
    if (duplicateDocument) {
      setError(`Este documento ya fue registrado: ${documentLabel(duplicateDocument)}`)
      setNotice('')
      return
    }
    const validRows = rows.filter(
      (row) => row.description.trim() && row.unit.trim() && Number(row.expected_quantity) > 0,
    )
    if (!validRows.length) {
      setError('Agrega al menos una partida valida')
      return
    }
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await apiRequest(`/inventory/projects/${projectId}/quick-documents`, {
        method: 'POST',
        body: JSON.stringify({
          warehouse_id: warehouseId ? Number(warehouseId) : null,
          name: documentNumber || documentName || `Material ${selectedProject?.name ?? ''}`.trim(),
          document_number: textOrNull(documentNumber),
          supplier_name: textOrNull(supplierName),
          document_date: textOrNull(documentDate),
          delivery_date: textOrNull(deliveryDate),
          source_document_name: textOrNull(documentName || documentFile?.name || ''),
          source_document_hash: textOrNull(documentHash),
          supply_source: 'developer',
          include_in_quote: false,
          auto_create_materials: true,
          update_project_prices: true,
          received_by: textOrNull(receivedBy),
          delivery_reference: textOrNull(documentNumber),
          items: validRows.map((row) => ({
            source_code: textOrNull(row.source_code),
            description: row.description.trim(),
            unit: row.unit.trim(),
            expected_quantity: Number(row.expected_quantity),
            unit_price: numberOrNull(row.unit_price),
            line_total: numberOrNull(row.line_total),
            delivery_date: textOrNull(row.delivery_date || deliveryDate),
            received_quantity: numberOrNull(row.received_quantity),
            notes: textOrNull(row.notes),
          })),
        }),
      })
      setNotice('Documento guardado')
      setRows([newRow()])
      setSourceText('')
      setDocumentFile(null)
      setDocumentNumber('')
      setSupplierName('')
      setDocumentDate('')
      setDeliveryDate('')
      setDocumentName('')
      setDocumentHash('')
      await loadProjectInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar documento')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="text-sm text-acsm-muted">Cargando...</div>

  return (
    <div className="min-w-0 space-y-5">
      <section className="overflow-hidden rounded-md border border-acsm-line bg-white p-3 shadow-panel">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] xl:items-end">
          <label className="min-w-0 text-sm">
            <span className="mb-1.5 block font-medium text-acsm-ink">Desarrollo</span>
            <select
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
            >
              <option value="">Seleccionar</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 text-sm">
            <span className="mb-1.5 block font-medium text-acsm-ink">Bodega</span>
            <select
              value={warehouseId}
              onChange={(event) => setWarehouseId(event.target.value)}
              className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
            >
              <option value="">Automatico</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => void loadProjectInventory()}
            className="inline-flex h-10 w-full shrink-0 items-center justify-center gap-2 rounded-md border border-acsm-line px-4 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper md:w-auto"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Actualizar
          </button>
        </div>
        {error ? (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mt-3 rounded-md border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm text-zinc-700">
            {notice}
          </div>
        ) : null}
      </section>

      {showPurchaseOrderReceiving ? (
      <section className="overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-green">
              <Truck className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <h2 className="text-base font-semibold">Recepcion contra orden de compra</h2>
              <p className="text-xs text-acsm-muted">
                El sistema ya conoce materiales, cantidades y proveedor; captura solo lo que llego.
              </p>
            </div>
          </div>
          <span className="rounded-full border border-acsm-line bg-acsm-paper px-3 py-1 text-xs font-semibold text-acsm-muted">
            {receivablePurchaseOrders.length} pendientes
          </span>
        </div>

        <div className="grid gap-4 p-4 xl:grid-cols-[420px_minmax(0,1fr)]">
          <div className="space-y-3">
            <label className="block text-sm font-semibold text-acsm-ink">
              Orden de compra
              <select
                value={selectedPurchaseOrderId}
                onChange={(event) => selectPurchaseOrder(event.target.value)}
                className="mt-1 h-10 w-full rounded-md border border-acsm-line px-3 text-sm"
              >
                <option value="">Seleccionar OC por recibir</option>
                {receivablePurchaseOrders.map((order) => {
                  const total = order.items.reduce(
                    (sum, item) => sum + Number(item.quantity_ordered),
                    0,
                  )
                  const received = order.items.reduce(
                    (sum, item) => sum + Number(item.received_quantity),
                    0,
                  )
                  return (
                    <option key={order.id} value={order.id}>
                      {order.po_number} · {order.supplier?.name ?? 'Proveedor'} ·{' '}
                      {formatQuantity(total - received)} pendiente
                    </option>
                  )
                })}
              </select>
            </label>

            {selectedPurchaseOrder ? (
              <div className="rounded-md border border-acsm-line bg-acsm-paper p-3">
                <div className="grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <div className="text-xs font-semibold uppercase text-acsm-muted">Proveedor</div>
                    <div className="font-semibold text-acsm-ink">
                      {selectedPurchaseOrder.supplier?.name ?? '-'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase text-acsm-muted">Estado OC</div>
                    <div className="font-semibold text-acsm-ink">{selectedPurchaseOrder.status}</div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase text-acsm-muted">Orden</div>
                    <div className="font-semibold text-acsm-ink">{selectedPurchaseOrder.po_number}</div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase text-acsm-muted">Lista inventario</div>
                    <div className="font-semibold text-acsm-ink">
                      {selectedPurchaseOrderList?.name ?? 'Sin lista esperada'}
                    </div>
                  </div>
                </div>
                {!selectedPurchaseOrderList ? (
                  <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                    Esta orden no tiene lista esperada ligada en inventario.
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              <input
                value={poDeliveryReference}
                onChange={(event) => setPoDeliveryReference(event.target.value)}
                placeholder="Referencia entrega"
                className="h-10 rounded-md border border-acsm-line px-3 text-sm"
              />
              <input
                value={poDeliveredBy}
                onChange={(event) => setPoDeliveredBy(event.target.value)}
                placeholder="Entrega"
                className="h-10 rounded-md border border-acsm-line px-3 text-sm"
              />
              <input
                value={poReceivedBy}
                onChange={(event) => setPoReceivedBy(event.target.value)}
                placeholder="Recibe"
                className="h-10 rounded-md border border-acsm-line px-3 text-sm sm:col-span-2"
              />
            </div>
          </div>

          <div className="min-w-0 overflow-hidden rounded-md border border-acsm-line">
            <div className="flex items-center justify-between border-b border-acsm-line bg-acsm-paper px-3 py-2">
              <div>
                <h3 className="text-sm font-semibold text-acsm-ink">Partidas pendientes de recibir</h3>
                <p className="text-xs text-acsm-muted">
                  Puedes modificar la cantidad recibida si la entrega fue parcial.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void savePurchaseOrderReception()}
                disabled={saving || !selectedPurchaseOrderList || !warehouseId || !poReceiveRows.length}
                className="inline-flex h-9 items-center gap-2 rounded-md bg-acsm-green px-3 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
              >
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                Registrar recepcion
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-sm">
                <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
                  <tr>
                    <th className="px-3 py-2">Material</th>
                    <th className="px-3 py-2">Pendiente</th>
                    <th className="px-3 py-2">Recibido ahora</th>
                    <th className="px-3 py-2">Condicion</th>
                    <th className="px-3 py-2">Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {poReceiveRows.map((row) => (
                    <tr key={row.expected_item_id} className="border-t border-acsm-line">
                      <td className="px-3 py-2 font-semibold text-acsm-ink">{row.description}</td>
                      <td className="px-3 py-2">
                        {formatQuantity(row.pending_quantity)} {row.unit}
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          min="0"
                          max={row.pending_quantity}
                          step="0.0001"
                          value={row.received_quantity}
                          onChange={(event) =>
                            updatePoReceiveRow(row.expected_item_id, {
                              received_quantity: event.target.value,
                            })
                          }
                          className="h-9 w-full rounded-md border border-acsm-line px-2"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <select
                          value={row.condition_status}
                          onChange={(event) =>
                            updatePoReceiveRow(row.expected_item_id, {
                              condition_status: event.target
                                .value as PurchaseOrderReceiveRow['condition_status'],
                            })
                          }
                          className="h-9 w-full rounded-md border border-acsm-line px-2"
                        >
                          <option value="ok">Correcto</option>
                          <option value="incomplete">Incompleto</option>
                          <option value="damaged">Dañado</option>
                          <option value="extra">Extra</option>
                          <option value="other">Otro</option>
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <input
                          value={row.notes}
                          onChange={(event) =>
                            updatePoReceiveRow(row.expected_item_id, { notes: event.target.value })
                          }
                          className="h-9 w-full rounded-md border border-acsm-line px-2"
                        />
                      </td>
                    </tr>
                  ))}
                  {!poReceiveRows.length ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-acsm-muted">
                        Selecciona una orden de compra pendiente.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
      ) : null}

      {showExternalDocument ? (
      <form
        onSubmit={saveQuickDocument}
        className="min-w-0 overflow-hidden rounded-md border border-acsm-line bg-white shadow-panel"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper text-acsm-green">
              <FileUp className="h-4 w-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h2 className="text-base font-semibold">
                {mode === 'document_validation'
                  ? 'Validar documento externo'
                  : 'Carga de material externo o sin OC'}
              </h2>
              <p className="text-xs text-acsm-muted">
                {mode === 'document_validation'
                  ? 'Interpreta, revisa y corrige partidas antes de guardar el documento en inventario.'
                  : 'Carga documentos que no nacieron desde Compras: desarrolladora, PDF, foto o Excel.'}
              </p>
            </div>
          </div>
          <span className="inline-flex h-8 items-center rounded-full border border-acsm-line bg-acsm-paper px-3 text-xs font-semibold text-acsm-muted">
            {rows.length} {rows.length === 1 ? 'partida' : 'partidas'}
          </span>
        </div>

        <div className="grid min-w-0 gap-3 border-b border-acsm-line bg-acsm-paper/40 p-3 xl:grid-cols-2">
          <div className="min-w-0 rounded-md border border-dashed border-acsm-line bg-white p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase text-acsm-muted">Archivo recibido</span>
              <span className="text-xs text-acsm-muted">Max. un archivo</span>
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <input
                id="inventory-pdf-file"
                type="file"
                accept="application/pdf,.pdf,image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                onChange={(event: ChangeEvent<HTMLInputElement>) => {
                  setDocumentFile(event.target.files?.[0] ?? null)
                  setDocumentHash('')
                  setError('')
                  setNotice('')
                }}
                className="hidden"
              />
              <label
                htmlFor="inventory-pdf-file"
                className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
              >
                <FileUp className="h-4 w-4" aria-hidden="true" />
                Seleccionar
              </label>
              <div className="min-w-0 flex-1 truncate rounded-md border border-acsm-line bg-acsm-paper px-3 py-2 text-sm text-acsm-muted sm:min-w-[180px]">
                {documentFile?.name ?? 'Sin PDF o imagen seleccionada'}
              </div>
              <button
                type="button"
                onClick={parsePdf}
                disabled={saving || !projectId || !documentFile}
                className="inline-flex h-9 w-auto shrink-0 items-center justify-center rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
              >
                {saving ? 'Analizando...' : 'Analizar'}
              </button>
            </div>
          </div>

          <div className="min-w-0 rounded-md border border-acsm-line bg-white p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase text-acsm-muted">Captura desde Excel</span>
              <span className="text-xs text-acsm-muted">Pegar tabla</span>
            </div>
            <div className="flex min-w-0 flex-wrap items-start gap-2 sm:flex-nowrap">
              <textarea
                value={sourceText}
                onChange={(event) => {
                  setSourceText(event.target.value)
                  setDocumentHash('')
                }}
                placeholder="Pegar renglones desde Excel"
                rows={2}
                className="min-h-9 min-w-0 flex-1 rounded-md border border-acsm-line px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={parseText}
                disabled={saving || !projectId || !sourceText.trim()}
                className="inline-flex h-9 w-full shrink-0 items-center justify-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold hover:bg-acsm-paper disabled:opacity-60 sm:w-auto"
              >
                <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
                Interpretar
              </button>
            </div>
          </div>
        </div>

        {duplicateDocument ? (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <div className="font-semibold">Documento ya registrado</div>
                <p className="mt-0.5">
                  Coincide con {documentLabel(duplicateDocument)}. No se puede guardar dos veces
                  dentro del mismo desarrollo.
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <div className="grid min-w-0 gap-3 border-b border-acsm-line p-3 md:grid-cols-3 xl:grid-cols-6">
          <input
            value={documentNumber}
            onChange={(event) => setDocumentNumber(event.target.value)}
            placeholder="OC / Documento"
            className="h-10 rounded-md border border-acsm-line px-3 text-sm"
          />
          <input
            value={supplierName}
            onChange={(event) => setSupplierName(event.target.value)}
            placeholder="Proveedor"
            className="h-10 rounded-md border border-acsm-line px-3 text-sm md:col-span-2"
          />
          <input
            value={documentDate}
            onChange={(event) => setDocumentDate(event.target.value)}
            type="date"
            className="h-10 rounded-md border border-acsm-line px-3 text-sm"
          />
          <input
            value={deliveryDate}
            onChange={(event) => setDeliveryDate(event.target.value)}
            type="date"
            className="h-10 rounded-md border border-acsm-line px-3 text-sm"
          />
          <input
            value={receivedBy}
            onChange={(event) => setReceivedBy(event.target.value)}
            placeholder="Recibe"
            className="h-10 rounded-md border border-acsm-line px-3 text-sm"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line px-3 py-2">
          <h3 className="text-sm font-semibold text-acsm-ink">Partidas del documento</h3>
          <button
            type="button"
            onClick={() => setRows((current) => [...current, newRow()])}
            className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border border-acsm-line px-3 text-sm font-semibold hover:bg-acsm-paper sm:w-auto"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Agregar renglon
          </button>
        </div>

        <div className="max-w-full overflow-x-auto">
          <table className="w-full min-w-[1488px] table-fixed text-sm">
            <colgroup>
              <col className="w-[120px]" />
              <col className="w-[330px]" />
              <col className="w-[85px]" />
              <col className="w-[135px]" />
              <col className="w-[125px]" />
              <col className="w-[135px]" />
              <col className="w-[145px]" />
              <col className="w-[135px]" />
              <col className="w-[230px]" />
              <col className="w-[48px]" />
            </colgroup>
            <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
              <tr>
                <th className="px-2 py-2">Codigo</th>
                <th className="px-2 py-2">Material</th>
                <th className="px-2 py-2">Unidad</th>
                <th className="px-2 py-2">Esperado</th>
                <th className="px-2 py-2">Precio</th>
                <th className="px-2 py-2">Importe</th>
                <th className="px-2 py-2">Entrega</th>
                <th className="px-2 py-2">Recibido</th>
                <th className="px-2 py-2">Notas</th>
                <th className="sticky right-0 z-10 border-l border-acsm-line bg-acsm-paper px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.local_id} className="border-b border-acsm-line last:border-0">
                  <td className="p-1"><input value={row.source_code} onChange={(event) => updateRow(index, 'source_code', event.target.value)} className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.description} onChange={(event) => updateRow(index, 'description', event.target.value)} title={row.description} className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.unit} onChange={(event) => updateRow(index, 'unit', event.target.value)} className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.expected_quantity} onChange={(event) => updateRow(index, 'expected_quantity', event.target.value)} type="number" min="0" step="0.0001" className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.unit_price} onChange={(event) => updateRow(index, 'unit_price', event.target.value)} type="number" min="0" step="0.0001" className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.line_total} onChange={(event) => updateRow(index, 'line_total', event.target.value)} type="number" min="0" step="0.01" className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.delivery_date} onChange={(event) => updateRow(index, 'delivery_date', event.target.value)} type="date" className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.received_quantity} onChange={(event) => updateRow(index, 'received_quantity', event.target.value)} type="number" min="0" step="0.0001" className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="p-1"><input value={row.notes} onChange={(event) => updateRow(index, 'notes', event.target.value)} title={row.notes} className="h-9 w-full min-w-0 rounded-md border border-acsm-line px-2" /></td>
                  <td className="sticky right-0 z-10 border-l border-acsm-line bg-white p-1">
                    <button
                      type="button"
                      onClick={() => setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}
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

        <div className="flex flex-col gap-3 border-t border-acsm-line bg-acsm-paper/40 p-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-acsm-muted">{rows.length} renglones en captura</div>
          <button
            type="submit"
            disabled={saving || !projectId || Boolean(duplicateDocument)}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-5 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-70 sm:w-auto"
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            Guardar documento
          </button>
        </div>
      </form>
      ) : null}
      {showStock ? (
      <section className="rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex h-14 items-center justify-between border-b border-acsm-line px-4">
          <div>
            <h2 className="text-base font-semibold">Existencias por bodega</h2>
            <p className="text-xs text-acsm-muted">Stock acumulado a partir de recepciones registradas.</p>
          </div>
          <Warehouse className="h-4 w-4 text-acsm-green" aria-hidden="true" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
              <tr>
                <th className="px-4 py-3">Material</th>
                <th className="px-4 py-3">Unidad</th>
                <th className="px-4 py-3">Existencia</th>
                <th className="px-4 py-3">Bodega</th>
              </tr>
            </thead>
            <tbody>
              {stockItems.map((item) => (
                <tr key={item.id} className="border-b border-acsm-line last:border-0">
                  <td className="px-4 py-3 font-semibold">{item.description}</td>
                  <td className="px-4 py-3">{item.unit}</td>
                  <td className="px-4 py-3">{formatQuantity(item.quantity_on_hand)}</td>
                  <td className="px-4 py-3">
                    {warehouses.find((warehouse) => warehouse.id === item.warehouse_id)?.name ?? item.warehouse_id}
                  </td>
                </tr>
              ))}
              {!stockItems.length ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-acsm-muted">
                    Sin existencias registradas en esta bodega.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      ) : null}

      {showDocuments || showMissing ? (
      <div className="grid gap-5 xl:grid-cols-2">
        {showDocuments ? (
        <section className="rounded-md border border-acsm-line bg-white shadow-panel">
          <div className="flex h-14 items-center justify-between border-b border-acsm-line px-4">
            <h2 className="text-base font-semibold">Documentos</h2>
            <Warehouse className="h-4 w-4 text-acsm-green" aria-hidden="true" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
                <tr>
                  <th className="px-4 py-3">Documento</th>
                  <th className="px-4 py-3">Proveedor</th>
                  <th className="px-4 py-3">Partidas</th>
                  <th className="px-4 py-3">Archivo</th>
                </tr>
              </thead>
              <tbody>
                {expectedLists.map((list) => (
                  <tr key={list.id} className="border-b border-acsm-line last:border-0">
                    <td className="px-4 py-3">{list.document_number || list.name}</td>
                    <td className="px-4 py-3">{list.supplier_name}</td>
                    <td className="px-4 py-3">{list.items.length}</td>
                    <td className="px-4 py-3">{list.source_document_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        ) : null}

        {showMissing ? (
        <section className="rounded-md border border-acsm-line bg-white shadow-panel">
          <div className="flex h-14 items-center justify-between border-b border-acsm-line px-4">
            <h2 className="text-base font-semibold">Faltantes</h2>
            <ClipboardCheck className="h-4 w-4 text-acsm-green" aria-hidden="true" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
                <tr>
                  <th className="px-4 py-3">Material</th>
                  <th className="px-4 py-3">Pendiente</th>
                  <th className="px-4 py-3">Notas</th>
                </tr>
              </thead>
              <tbody>
                {missingItems.map((item) => (
                  <tr key={item.expected_item_id} className="border-b border-acsm-line last:border-0">
                    <td className="px-4 py-3">{item.description}</td>
                    <td className="px-4 py-3">{formatQuantity(item.pending_quantity)} {item.unit}</td>
                    <td className="px-4 py-3">{item.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        ) : null}
      </div>
      ) : null}

      {showMissing ? (
      <section className="rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex h-14 items-center justify-between border-b border-acsm-line px-4">
          <h2 className="text-base font-semibold">Estatus de materiales</h2>
          <PackageCheck className="h-4 w-4 text-acsm-green" aria-hidden="true" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
              <tr>
                <th className="px-4 py-3">Codigo</th>
                <th className="px-4 py-3">Material</th>
                <th className="px-4 py-3">Esperado</th>
                <th className="px-4 py-3">Recibido</th>
                <th className="px-4 py-3">Pendiente</th>
                <th className="px-4 py-3">Estado</th>
              </tr>
            </thead>
            <tbody>
              {statusItems.map((item) => (
                <tr key={item.expected_item_id} className="border-b border-acsm-line last:border-0">
                  <td className="px-4 py-3">{item.source_code}</td>
                  <td className="px-4 py-3">{item.description}</td>
                  <td className="px-4 py-3">{formatQuantity(item.expected_quantity)} {item.unit}</td>
                  <td className="px-4 py-3">{formatQuantity(item.received_quantity)} {item.unit}</td>
                  <td className="px-4 py-3">{formatQuantity(item.pending_quantity)} {item.unit}</td>
                  <td className="px-4 py-3">{item.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      ) : null}

      {showDocuments ? (
      <section className="rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex h-14 items-center justify-between border-b border-acsm-line px-4">
          <h2 className="text-base font-semibold">Historial de recepciones</h2>
          <PackageCheck className="h-4 w-4 text-acsm-green" aria-hidden="true" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
              <tr>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">Referencia</th>
                <th className="px-4 py-3">Recibe</th>
                <th className="px-4 py-3">Partidas</th>
              </tr>
            </thead>
            <tbody>
              {receptions.map((reception) => (
                <tr key={reception.id} className="border-b border-acsm-line last:border-0">
                  <td className="px-4 py-3">{reception.received_at}</td>
                  <td className="px-4 py-3">{reception.delivery_reference}</td>
                  <td className="px-4 py-3">{reception.received_by}</td>
                  <td className="px-4 py-3">
                    {reception.items
                      .map((item) => `${item.description}: ${formatQuantity(item.received_quantity)} ${item.unit}`)
                      .join(', ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      ) : null}
    </div>
  )
}
