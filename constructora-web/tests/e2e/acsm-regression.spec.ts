import { expect, type Page, test } from '@playwright/test'

const user = {
  id: 1,
  full_name: 'Administrador Maestro',
  email: 'admin@acsm-control.local',
  is_active: true,
  is_master_admin: true,
  permissions: [],
}

const limitedUser = {
  id: 2,
  full_name: 'Capturista Desarrolladoras',
  email: 'capturista@acsm-control.local',
  is_active: true,
  is_master_admin: false,
  permissions: ['clients:view'],
}

const projects = [{ id: 1, name: 'Privada Encinos' }]

const materials = [
  { id: 1, name: 'Cemento gris 50kg', unit: 'saco' },
  { id: 2, name: 'Varilla 3/8', unit: 'pieza' },
]

const suppliers = [
  { id: 1, name: 'Aceros del Bajio', payment_terms_days: 30, average_delivery_days: 5 },
  { id: 2, name: 'Agregados La Cantera', payment_terms_days: 30, average_delivery_days: 7 },
  { id: 3, name: 'Concretos Centro Norte', payment_terms_days: 15, average_delivery_days: 3 },
]

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const rfqs = [
  {
    id: 10,
    project_id: 1,
    rfq_number: 'SC-202606-0008',
    title: 'Cemento',
    status: 'sent',
    created_at: '2026-06-02T06:27:00-06:00',
    created_by: 1,
    creator: { id: 1, full_name: 'Arturo Fitz', email: 'arturoh.fitz@gmail.com' },
    required_by: '2026-06-10',
    response_deadline: '2026-06-06',
    items: [{ id: 100, description: 'Cemento gris 50kg', unit: 'saco', quantity: '100' }],
    supplier_links: suppliers.map((supplier) => ({
      supplier_id: supplier.id,
      status: 'sent',
      supplier,
    })),
  },
  {
    id: 11,
    project_id: 1,
    rfq_number: 'SC-202605-0006',
    title: 'Compra de varilla',
    status: 'approved',
    created_at: '2026-05-28T19:17:00-06:00',
    created_by: 1,
    creator: { id: 1, full_name: 'Administrador Maestro', email: 'admin@acsm-control.local' },
    required_by: '2026-06-05',
    response_deadline: '2026-06-01',
    items: [{ id: 101, description: 'Varilla 3/8', unit: 'pieza', quantity: '40' }],
    supplier_links: suppliers.map((supplier) => ({
      supplier_id: supplier.id,
      status: 'sent',
      supplier,
    })),
  },
]

type Supplier = (typeof suppliers)[number]
type Rfq = (typeof rfqs)[number]

type SupplierQuote = {
  id: number
  rfq_id: number
  supplier_id: number
  quote_number: string
  status: string
  subtotal: string
  delivery_days: number | null
  payment_terms_days: number
  supplier: Supplier
  items: Array<{
    id: number
    rfq_item_id: number
    description: string
    unit: string
    quantity: string
    unit_price: string
    line_total: string
    delivery_days: number | null
  }>
  created_at: string
  updated_at: string
}

type PurchaseOrder = {
  id: number
  supplier_quote_id: number
  project_id: number
  warehouse_id: number
  po_number: string
  status: string
  billing_mode: 'single' | 'partial'
  issued_at: string
  payment_terms_days: number
  subtotal: string
  supplier_id: number
  supplier: Supplier
  items: Array<{
    id: number
    description: string
    unit: string
    quantity_ordered: string
    unit_price: string
    line_total: string
    received_quantity: string
    status: string
  }>
}

type ExpectedList = {
  id: number
  warehouse_id: number
  purchase_order_id: number
  name: string
  document_number: string
  supplier_name: string
  source_document_name: string | null
  source_document_hash: string | null
  items: Array<{
    id: number
    purchase_order_item_id: number
    description: string
    unit: string
    expected_quantity: string
    received_quantity: string
    status: string
    notes: string | null
  }>
}

type Approval = {
  id: number
  rfq_id: number
  supplier_quote_id: number
  status: string
  request_notes: string | null
  decision_notes: string | null
  requested_at: string
  decided_at: string | null
  requester: typeof user
  decider: typeof user | null
  supplier_quote: SupplierQuote
  rfq: Rfq
}

type SupplierInvoice = {
  id: number
  supplier_id: number
  purchase_order_id: number
  invoice_number: string
  invoice_date: string
  due_date: string
  total: string
  currency: string
  fiscal_status: string
  fiscal_validation_message: string | null
  status: string
  document_name: string | null
  notes: string | null
  supplier: Supplier
  purchase_order: PurchaseOrder
  items: Array<{
    id: number
    purchase_order_item_id: number
    quantity: string
    unit_price: string
    line_total: string
  }>
  documents: Array<{
    id: number
    document_type: string
    original_file_name: string
    file_size: number
    validation_status: string
    is_active: boolean
  }>
}

type SupplierPayment = {
  id: number
  supplier_invoice_id: number
  amount: string
  scheduled_date: string | null
  paid_at: string | null
  status: string
  reference: string | null
}

function comparisonFromQuotes(quotes: SupplierQuote[]) {
  return quotes.map((quote) => ({
    supplier_quote_id: quote.id,
    supplier_name: quote.supplier.name,
    subtotal: quote.subtotal,
    delivery_days: quote.delivery_days,
    payment_terms_days: quote.payment_terms_days,
    status: quote.status,
    complete_items: quote.items.length,
    total_items: quote.items.length,
  }))
}

function makeQuote(rfq: Rfq, supplier: Supplier, quoteId: number, price = 20): SupplierQuote {
  const items = rfq.items.map((item, index) => {
    const unitPrice = price + index
    const lineTotal = unitPrice * Number(item.quantity)
    return {
      id: quoteId * 10 + index,
      rfq_item_id: item.id,
      description: item.description,
      unit: item.unit,
      quantity: item.quantity,
      unit_price: String(unitPrice),
      line_total: String(lineTotal),
      delivery_days: supplier.average_delivery_days ?? null,
    }
  })

  return {
    id: quoteId,
    rfq_id: rfq.id,
    supplier_id: supplier.id,
    quote_number: `COT-${quoteId}`,
    status: 'received',
    subtotal: String(items.reduce((sum, item) => sum + Number(item.line_total), 0)),
    delivery_days: supplier.average_delivery_days ?? null,
    payment_terms_days: supplier.payment_terms_days,
    supplier,
    items,
    created_at: '2026-06-03T10:00:00-06:00',
    updated_at: '2026-06-03T10:00:00-06:00',
  }
}

async function mockApi(
  page: Page,
  currentUser = user,
  options: { withoutWarehouses?: boolean; withAssistedQuote?: boolean } = {},
) {
  let warehouses: Array<{
    id: number
    project_id: number
    name: string
    location: string | null
    notes?: string | null
  }> = options.withoutWarehouses
    ? []
    : [{ id: 1, project_id: 1, name: 'Bodega Privada Encinos', location: 'Obra' }]
  let rfqState = clone(rfqs)
  const quotesByRfq: Record<number, SupplierQuote[]> = {
    10: suppliers.map((supplier, index) => makeQuote(rfqs[0], supplier, 600 + index, 22 + index)),
    11: [],
  }
  const assistedUpload = {
    id: 501,
    rfq_id: 11,
    supplier_id: 1,
    quote_number: 'COT-ASISTIDA-001',
    original_file_name: 'COT-ASISTIDA-001.pdf',
    file_extension: '.pdf',
    file_size_bytes: 4096,
    status: 'review_required',
    uploaded_at: '2026-08-20T18:00:00-06:00',
    notes: null,
    supplier: suppliers[0],
  }
  let quoteUploads = options.withAssistedQuote ? [assistedUpload] : []
  let quoteDrafts = options.withAssistedQuote
    ? [
        {
          id: 500,
          rfq_id: 11,
          supplier_id: 1,
          upload_id: assistedUpload.id,
          supplier_quote_id: null,
          status: 'review_required',
          source_type: 'pdf_text',
          confidence: '0.96',
          quote_number: 'COT-ASISTIDA-001',
          valid_until: '2026-08-27',
          currency: 'MXN',
          delivery_days: 5,
          payment_terms_days: 30,
          subtotal: '800',
          discount: '0',
          shipping_cost: '0',
          tax_amount: '128',
          total: '928',
          notes: null,
          validation_errors: [],
          detected_supplier_name: 'Aceros del Bajio',
          detected_supplier_tax_id: null,
          detected_supplier_email: null,
          supplier_match_status: 'matched',
          supplier_match_confidence: '1',
          detected_rfq_number: 'SC-202605-0006',
          document_subtotal: '800',
          document_tax_amount: '128',
          document_total: '928',
          extraction_metadata: {},
          supplier: suppliers[0],
          upload: assistedUpload,
          items: [
            {
              id: 600,
              rfq_item_id: 101,
              description: 'Varilla 3/8',
              unit: 'pieza',
              quantity: '40',
              unit_price: '20',
              line_total: '800',
              delivery_days: 5,
              notes: null,
              confidence: '0.99',
              match_method: 'description',
            },
          ],
        },
      ]
    : []
  let approvals: Approval[] = []
  let purchaseOrders: PurchaseOrder[] = []
  let expectedLists: ExpectedList[] = []
  let supplierInvoices: SupplierInvoice[] = []
  let supplierPayments: SupplierPayment[] = []
  let receptions: Array<{
    id: number
    received_at: string
    delivery_reference: string | null
    received_by: string | null
    items: Array<{ id: number; description: string; received_quantity: string; unit: string }>
  }> = []
  let stockItems: Array<{
    id: number
    warehouse_id: number
    description: string
    unit: string
    quantity_on_hand: string
  }> = []
  let nextRfqId = 20
  let nextQuoteId = 700
  let nextInvoiceId = 9000
  let nextPaymentId = 9500

  const upsertRfq = (rfqId: number, patch: Partial<Rfq>) => {
    rfqState = rfqState.map((rfq) => (rfq.id === rfqId ? { ...rfq, ...patch } : rfq))
  }
  const invoiceStateForOrder = (order: PurchaseOrder) => {
    const pendingItems = order.items.filter(
      (item) => Number(item.received_quantity) < Number(item.quantity_ordered),
    ).length
    if (pendingItems > 0) {
      return {
        status: 'blocked',
        pendingItems,
        message: `Factura bloqueada: ${pendingItems} partida(s) pendiente(s) por recibir.`,
      }
    }
    return {
      status: 'approved_for_payment',
      pendingItems: 0,
      message: 'Factura validada y aprobada para pago.',
    }
  }
  const inventoryStatus = () =>
    expectedLists.flatMap((list) =>
      list.items.map((item) => {
        const expected = Number(item.expected_quantity)
        const received = Number(item.received_quantity)
        const pending = Math.max(expected - received, 0)
        return {
          expected_item_id: item.id,
          source_code: null,
          description: item.description,
          unit: item.unit,
          expected_quantity: item.expected_quantity,
          received_quantity: item.received_quantity,
          pending_quantity: String(pending),
          over_received_quantity: '0',
          status: pending === 0 ? 'complete' : received > 0 ? 'partial' : 'pending',
          notes: item.notes,
        }
      }),
    )

  const purchaseCases = () => {
    const stageLabels: Record<string, string> = {
      origin: 'Origen validado',
      providers: 'Proveedores convocados',
      documents: 'Respuesta de proveedores',
      capture: 'Cotizaciones capturadas',
      comparison: 'Comparativo listo',
      approval: 'Aprobacion gerencial',
      order: 'Orden de compra',
      receiving: 'Recepcion de material',
      payment: 'Facturacion y pago',
      closed: 'Proceso concluido',
    }
    const stageOrder = ['origin', 'providers', 'documents', 'capture', 'comparison', 'approval', 'order', 'receiving', 'payment']

    return rfqState.map((rfq) => {
      const quotes = quotesByRfq[rfq.id] ?? []
      const approval = approvals.find((entry) => entry.rfq_id === rfq.id)
      const approvedQuote = quotes.find((entry) => entry.status === 'approved')
      const order = approvedQuote
        ? purchaseOrders.find((entry) => entry.supplier_quote_id === approvedQuote.id)
        : undefined
      const requiredQuotes = 3
      const completeQuotes = quotes.filter((quote) => quote.items.length === rfq.items.length)
      let stage = 'documents'
      if (order?.status === 'closed') stage = 'closed'
      else if (order && ['received', 'factured'].includes(order.status)) stage = 'payment'
      else if (order && ['sent', 'partially_received'].includes(order.status)) stage = 'receiving'
      else if (['approved_for_order', 'purchase_order_ready'].includes(rfq.status) || order?.status === 'issued') stage = 'order'
      else if (approval?.status === 'requested') stage = 'approval'
      else if (completeQuotes.length >= requiredQuotes) stage = 'comparison'
      else if (quotes.length) stage = 'capture'

      const currentIndex = stage === 'closed' ? stageOrder.length : stageOrder.indexOf(stage)
      const nextActions: Record<string, [string, string]> = {
        documents: ['Revisar respuestas', `/purchasing/operations?rfq_id=${rfq.id}&focus=uploads`],
        capture: ['Capturar cotizaciones', `/purchasing/operations?rfq_id=${rfq.id}&focus=uploads`],
        comparison: ['Revisar comparativo', `/purchasing/operations?rfq_id=${rfq.id}&focus=comparison`],
        approval: ['Consultar aprobacion', '/purchasing/approvals'],
        order: ['Preparar orden de compra', `/purchasing/cases/${rfq.id}`],
        receiving: ['Consultar recepcion', '/inventory/material-receiving'],
        payment: ['Consultar facturas y pagos', '/supplier-payments'],
        closed: ['Consultar expediente', `/purchasing/cases/${rfq.id}`],
      }
      const [nextActionLabel, nextActionUrl] = nextActions[stage]

      return {
        id: rfq.id,
        rfq_id: rfq.id,
        rfq_number: rfq.rfq_number,
        title: rfq.title,
        status: rfq.status,
        project_id: rfq.project_id,
        project_name: projects.find((project) => project.id === rfq.project_id)?.name ?? 'Sin proyecto',
        requisition_id: null,
        requisition_number: null,
        owner_name: rfq.creator.full_name,
        required_by: rfq.required_by,
        response_deadline: rfq.response_deadline,
        supplier_count: rfq.supplier_links.length,
        item_count: rfq.items.length,
        upload_count: 0,
        quote_count: quotes.filter((quote) => quote.status !== 'discarded').length,
        complete_quote_count: completeQuotes.length,
        required_quote_count: requiredQuotes,
        approval_status: approval?.status ?? null,
        approved_supplier_name: approvedQuote?.supplier.name ?? null,
        approved_total: approvedQuote?.subtotal ?? null,
        purchase_order_id: order?.id ?? null,
        purchase_order_number: order?.po_number ?? null,
        purchase_order_status: order?.status ?? null,
        current_stage: stage,
        current_stage_label: stageLabels[stage],
        next_action_label: nextActionLabel,
        next_action_url: nextActionUrl,
        needs_attention: false,
        steps: stageOrder.map((key, index) => ({
          key,
          label: stageLabels[key],
          status: index < currentIndex ? 'complete' : index === currentIndex ? 'current' : 'pending',
          detail: '',
        })),
        created_at: rfq.created_at,
        updated_at: rfq.created_at,
      }
    })
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const pathname = url.pathname.replace('/api/v1', '')
    const path = `${pathname}${url.search}`
    const method = request.method()

    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })

    if (path === '/auth/login' && method === 'POST') {
      return json({ access_token: 'test-token', token_type: 'bearer' })
    }
    if (path === '/auth/me') return json(currentUser)
    if (pathname === '/executive-dashboard') {
      return json({
        generated_at: '2026-07-23T18:00:00Z',
        selected_project_id: null,
        totals: {
          project_count: 1,
          active_project_count: 1,
          attention_project_count: 0,
          houses_count: '10',
          budget_amount: '100000',
          committed_amount: '2200',
          received_amount: '0',
          invoiced_amount: '0',
          paid_amount: '0',
          available_amount: '97800',
          over_budget_amount: '0',
          purchase_orders_count: 1,
          invoices_count: 0,
          payments_count: 0,
        },
        flow: [],
        alerts: [],
        projects: [{
          project_id: 1,
          project_name: 'Privada Encinos',
          client_name: 'Inmobiliaria Encinos',
          houses_count: '10',
          models_count: 1,
          baseline_id: 1,
          baseline_revision: 1,
          budget_amount: '100000',
          committed_amount: '2200',
          received_amount: '0',
          invoiced_amount: '0',
          paid_amount: '0',
          available_amount: '97800',
          over_budget_amount: '0',
          committed_percent: '2.2',
          received_percent: '0',
          invoiced_percent: '0',
          paid_percent: '0',
          purchase_orders_count: 1,
          invoices_count: 0,
          payments_count: 0,
          integrity_issues: [],
          health: 'healthy',
          health_label: 'En control',
          next_action_label: 'Abrir proyecto',
          next_action_url: '/dashboard/projects/1',
        }],
        materials: [],
      })
    }
    if (path === '/projects') return json(projects)
    if (path === '/materials') return json(materials)
    if (path === '/purchasing/suppliers') return json(suppliers)
    if (pathname === '/material-requisitions' && method === 'GET') return json([])
    if (pathname === '/purchasing/purchase-cases' && method === 'GET') return json(purchaseCases())
    if (pathname === '/purchasing/supplier-rfqs' && method === 'GET') return json(rfqState)
    if (path.startsWith('/purchasing/supplier-rfq-exceptions')) return json([])
    if (pathname === '/purchasing/purchase-orders' && method === 'GET') return json(purchaseOrders)
    const billingModeMatch = pathname.match(
      /^\/purchasing\/purchase-orders\/(\d+)\/billing-mode$/,
    )
    if (billingModeMatch && method === 'PATCH') {
      const orderId = Number(billingModeMatch[1])
      const payload = await request.postDataJSON()
      purchaseOrders = purchaseOrders.map((order) =>
        order.id === orderId
          ? { ...order, billing_mode: payload.billing_mode as 'single' | 'partial' }
          : order,
      )
      const updatedOrder = purchaseOrders.find((order) => order.id === orderId)
      return updatedOrder
        ? json(updatedOrder)
        : json({ detail: 'Orden de compra no encontrada' }, 404)
    }
    if (pathname === '/purchasing/supplier-quote-approvals') return json(approvals)
    if (pathname === '/purchasing/supplier-invoices' && method === 'GET') return json(supplierInvoices)
    if (pathname === '/purchasing/supplier-payments' && method === 'GET') return json(supplierPayments)
    if (pathname === '/purchasing/project-financial-progress' && method === 'GET') {
      const selectedProjectId = url.searchParams.get('project_id')
      return json({
        projects: [
          {
            project_id: 1,
            project_name: 'Privada Encinos',
            client_name: 'Inmobiliaria Encinos',
            houses_count: '10',
            models_count: 1,
            baseline_id: null,
            baseline_revision: null,
            baseline_status: null,
            baseline_approved_at: null,
            budget_amount: '0',
            committed_amount: '2200',
            received_amount: '0',
            invoiced_amount: '0',
            paid_amount: '0',
            available_amount: '0',
            over_budget_amount: '2200',
            committed_percent: '0',
            received_percent: '0',
            invoiced_percent: '0',
            paid_percent: '0',
            purchase_orders_count: purchaseOrders.length,
            invoices_count: supplierInvoices.length,
            payments_count: supplierPayments.length,
            integrity_issues: [],
          },
        ],
        selected_project_id: selectedProjectId ? Number(selectedProjectId) : null,
        materials: [],
      })
    }
    if (pathname === '/inventory/projects/1/warehouses' && method === 'GET') return json(warehouses)
    if (pathname === '/inventory/projects/1/expected-materials') return json(expectedLists)
    if (pathname === '/inventory/projects/1/status') return json(inventoryStatus())
    if (pathname === '/inventory/projects/1/missing-materials') {
      return json(inventoryStatus().filter((item) => Number(item.pending_quantity) > 0))
    }
    if (pathname === '/inventory/projects/1/receptions' && method === 'GET') return json(receptions)
    if (pathname === '/inventory/warehouses/1/stock') return json(stockItems)

    if (pathname === '/inventory/warehouses' && method === 'POST') {
      const payload = await request.postDataJSON()
      const created = {
        id: warehouses.length ? Math.max(...warehouses.map((warehouse) => warehouse.id)) + 1 : 1,
        project_id: Number(payload.project_id),
        name: payload.name,
        location: payload.location,
        notes: payload.notes,
      }
      warehouses = [...warehouses, created]
      return json(created, 201)
    }

    if (pathname === '/purchasing/supplier-rfqs' && method === 'POST') {
      const payload = await request.postDataJSON()
      const created: Rfq = {
        id: nextRfqId++,
        project_id: Number(payload.project_id),
        rfq_number: 'SC-202606-0099',
        title: payload.title,
        status: 'sent',
        created_at: '2026-06-04T09:00:00-06:00',
        created_by: 1,
        creator: user,
        required_by: payload.required_by,
        response_deadline: payload.response_deadline,
        items: payload.items.map(
          (
            item: { description: string; unit: string; quantity: string | number },
            index: number,
          ) => ({
            id: 300 + index,
            description: item.description,
            unit: item.unit,
            quantity: String(item.quantity),
          }),
        ),
        supplier_links: payload.supplier_ids.map((supplierId: number) => ({
          supplier_id: supplierId,
          status: 'sent',
          supplier: suppliers.find((supplier) => supplier.id === supplierId),
        })),
      }
      rfqState = [created, ...rfqState]
      quotesByRfq[created.id] = []
      return json(created)
    }

    const rfqDetailMatch = pathname.match(/^\/purchasing\/supplier-rfqs\/(\d+)$/)
    if (rfqDetailMatch && method === 'GET') {
      const rfq = rfqState.find((entry) => entry.id === Number(rfqDetailMatch[1]))
      return rfq ? json(rfq) : json({ detail: 'RFQ no encontrada' }, 404)
    }

    const quoteUploadsMatch = pathname.match(
      /^\/purchasing\/supplier-rfqs\/(\d+)\/quote-uploads$/,
    )
    if (quoteUploadsMatch && method === 'GET') {
      const rfqId = Number(quoteUploadsMatch[1])
      return json(quoteUploads.filter((upload) => upload.rfq_id === rfqId))
    }

    const quoteDraftsMatch = pathname.match(
      /^\/purchasing\/supplier-rfqs\/(\d+)\/quote-drafts$/,
    )
    if (quoteDraftsMatch && method === 'GET') {
      const rfqId = Number(quoteDraftsMatch[1])
      return json(quoteDrafts.filter((draft) => draft.rfq_id === rfqId))
    }

    const manualCaptureMatch = pathname.match(
      /^\/purchasing\/supplier-quote-drafts\/(\d+)\/manual-capture$/,
    )
    if (manualCaptureMatch && method === 'POST') {
      const draftId = Number(manualCaptureMatch[1])
      const currentDraft = quoteDrafts.find((draft) => draft.id === draftId)
      if (!currentDraft) return json({ detail: 'Borrador no encontrado' }, 404)
      quoteDrafts = quoteDrafts.map((draft) =>
        draft.id === draftId ? { ...draft, status: 'manual_capture' } : draft,
      )
      quoteUploads = quoteUploads.map((upload) =>
        upload.id === currentDraft.upload_id
          ? { ...upload, status: 'manual_capture_required' }
          : upload,
      )
      return json(quoteDrafts.find((draft) => draft.id === draftId))
    }

    const reprocessUploadMatch = pathname.match(
      /^\/purchasing\/supplier-quote-uploads\/(\d+)\/reprocess$/,
    )
    if (reprocessUploadMatch && method === 'POST') {
      const uploadId = Number(reprocessUploadMatch[1])
      const currentDraft = quoteDrafts.find((draft) => draft.upload_id === uploadId)
      if (!currentDraft) return json({ detail: 'Borrador no encontrado' }, 404)
      quoteDrafts = quoteDrafts.map((draft) =>
        draft.id === currentDraft.id ? { ...draft, status: 'review_required' } : draft,
      )
      quoteUploads = quoteUploads.map((upload) =>
        upload.id === uploadId ? { ...upload, status: 'review_required' } : upload,
      )
      return json(quoteDrafts.find((draft) => draft.id === currentDraft.id))
    }

    const quotesMatch = pathname.match(/^\/purchasing\/supplier-rfqs\/(\d+)\/quotes$/)
    if (quotesMatch && method === 'GET') return json(quotesByRfq[Number(quotesMatch[1])] ?? [])
    if (quotesMatch && method === 'POST') {
      const rfqId = Number(quotesMatch[1])
      const rfq = rfqState.find((entry) => entry.id === rfqId)
      const payload = await request.postDataJSON()
      const supplier = suppliers.find((entry) => entry.id === Number(payload.supplier_id)) ?? suppliers[0]
      if (!rfq) return json({ detail: 'RFQ no encontrada' }, 404)
      const quoteItems = payload.items.map(
        (
          item: { rfq_item_id: number; unit_price: number; delivery_days: number | null },
          index: number,
        ) => {
          const rfqItem = rfq.items.find((entry) => entry.id === item.rfq_item_id) ?? rfq.items[index]
          const lineTotal = Number(item.unit_price) * Number(rfqItem.quantity)
          return {
            id: nextQuoteId * 10 + index,
            rfq_item_id: item.rfq_item_id,
            description: rfqItem.description,
            unit: rfqItem.unit,
            quantity: rfqItem.quantity,
            unit_price: String(item.unit_price),
            line_total: String(lineTotal),
            delivery_days: item.delivery_days,
          }
        },
      )
      const quote: SupplierQuote = {
        id: nextQuoteId++,
        rfq_id: rfq.id,
        supplier_id: supplier.id,
        quote_number: payload.quote_number,
        status: 'received',
        subtotal: String(quoteItems.reduce((sum, item) => sum + Number(item.line_total), 0)),
        delivery_days: payload.delivery_days,
        payment_terms_days: payload.payment_terms_days,
        supplier,
        items: quoteItems,
        created_at: '2026-06-03T10:00:00-06:00',
        updated_at: '2026-06-03T10:00:00-06:00',
      }
      quotesByRfq[rfq.id] = [
        quote,
        ...(quotesByRfq[rfq.id] ?? []).filter((entry) => entry.supplier_id !== supplier.id),
      ]
      return json(quote)
    }

    const quoteCorrectionMatch = pathname.match(
      /^\/purchasing\/supplier-quotes\/(\d+)\/request-correction$/,
    )
    if (quoteCorrectionMatch && method === 'POST') {
      const quoteId = Number(quoteCorrectionMatch[1])
      const quote = Object.values(quotesByRfq)
        .flat()
        .find((entry) => entry.id === quoteId)
      if (!quote) return json({ detail: 'Cotizacion no encontrada' }, 404)
      const payload = await request.postDataJSON()
      if (String(payload.reason ?? '').trim().length < 10) {
        return json({ detail: 'El motivo es obligatorio' }, 422)
      }
      quotesByRfq[quote.rfq_id] = (quotesByRfq[quote.rfq_id] ?? []).filter(
        (entry) => entry.id !== quoteId,
      )
      return json({
        message: 'Solicitud de nueva cotizacion enviada al proveedor.',
        supplier_email: 'compras@aceros-bajio.example.com',
        email_queued: true,
      })
    }

    const comparisonMatch = pathname.match(/^\/purchasing\/supplier-rfqs\/(\d+)\/comparison$/)
    if (comparisonMatch) {
      return json(comparisonFromQuotes(quotesByRfq[Number(comparisonMatch[1])] ?? []))
    }

    const approvalMatch = pathname.match(/^\/purchasing\/supplier-rfqs\/(\d+)\/request-approval$/)
    if (approvalMatch && method === 'POST') {
      const rfqId = Number(approvalMatch[1])
      const rfq = rfqState.find((entry) => entry.id === rfqId)
      const firstQuote = quotesByRfq[rfqId]?.[0]
      if (!rfq || !firstQuote) return json({ detail: 'Cotizacion no encontrada' }, 404)
      upsertRfq(rfqId, { status: 'approval_pending' })
      const approval: Approval = {
        id: 900,
        rfq_id: rfq.id,
        supplier_quote_id: firstQuote.id,
        status: 'requested',
        request_notes: null,
        decision_notes: null,
        requested_at: '2026-06-04T11:00:00-06:00',
        decided_at: null,
        requester: user,
        decider: null,
        supplier_quote: firstQuote,
        rfq: { ...rfq, status: 'approval_pending' },
      }
      approvals = [approval]
      return json(approval)
    }

    const approveMatch = pathname.match(/^\/purchasing\/supplier-quotes\/(\d+)\/approve$/)
    if (approveMatch && method === 'POST') {
      const quoteId = Number(approveMatch[1])
      const quote = Object.values(quotesByRfq)
        .flat()
        .find((entry) => entry.id === quoteId)
      if (!quote) return json({ detail: 'Cotizacion no encontrada' }, 404)
      Object.values(quotesByRfq).forEach((quotes) => {
        quotes.forEach((entry) => {
          if (entry.rfq_id === quote.rfq_id) entry.status = entry.id === quote.id ? 'approved' : 'discarded'
        })
      })
      const requestedApproval = approvals.find((entry) => entry.rfq_id === quote.rfq_id)
      if (!requestedApproval) return json({ detail: 'Aprobacion no encontrada' }, 404)
      upsertRfq(quote.rfq_id, { status: 'approved_for_order' })
      const approvedApproval: Approval = {
        ...requestedApproval,
        supplier_quote_id: quote.id,
        supplier_quote: quote,
        status: 'approved',
        decision_notes: null,
        decided_at: '2026-06-04T12:00:00-06:00',
        decider: user,
        rfq: { ...requestedApproval.rfq, status: 'approved_for_order' },
      }
      approvals = []
      return json(approvedApproval)
    }

    const createOrderMatch = pathname.match(/^\/purchasing\/supplier-rfqs\/(\d+)\/purchase-order$/)
    if (createOrderMatch && method === 'POST') {
      const rfqId = Number(createOrderMatch[1])
      const quote = (quotesByRfq[rfqId] ?? []).find((entry) => entry.status === 'approved')
      if (!quote) return json({ detail: 'Cotizacion aprobada no encontrada' }, 404)
      const order: PurchaseOrder = {
        id: 800,
        supplier_quote_id: quote.id,
        project_id: 1,
        warehouse_id: 1,
        po_number: 'OC-202606-0001',
        status: 'issued',
        billing_mode: 'single',
        issued_at: '2026-06-04T12:00:00-06:00',
        payment_terms_days: quote.payment_terms_days,
        subtotal: quote.subtotal,
        supplier_id: quote.supplier_id,
        supplier: quote.supplier,
        items: quote.items.map((item, index) => ({
          id: 900 + index,
          description: item.description,
          unit: item.unit,
          quantity_ordered: item.quantity,
          unit_price: item.unit_price,
          line_total: item.line_total,
          received_quantity: '0',
          status: 'pending',
        })),
      }
      purchaseOrders = [order]
      upsertRfq(rfqId, { status: 'purchase_order_ready' })
      return json(order, 201)
    }

    const sendOrderMatch = pathname.match(/^\/purchasing\/purchase-orders\/(\d+)\/send$/)
    if (sendOrderMatch && method === 'POST') {
      const orderId = Number(sendOrderMatch[1])
      purchaseOrders = purchaseOrders.map((order) =>
        order.id === orderId ? { ...order, status: 'sent' } : order,
      )
      const sentOrder = purchaseOrders.find((order) => order.id === orderId)
      if (!sentOrder) return json({ detail: 'Orden no encontrada' }, 404)
      const quote = Object.values(quotesByRfq).flat().find((entry) => entry.id === sentOrder.supplier_quote_id)
      if (quote) upsertRfq(quote.rfq_id, { status: 'awarded' })
      expectedLists = [
        {
          id: 810,
          warehouse_id: 1,
          purchase_order_id: sentOrder.id,
          name: `Lista esperada ${sentOrder.po_number}`,
          document_number: sentOrder.po_number,
          supplier_name: sentOrder.supplier.name,
          source_document_name: null,
          source_document_hash: null,
          items: sentOrder.items.map((item) => ({
            id: 1000 + item.id,
            purchase_order_item_id: item.id,
            description: item.description,
            unit: item.unit,
            expected_quantity: item.quantity_ordered,
            received_quantity: '0',
            status: 'pending',
            notes: null,
          })),
        },
      ]
      return json(sentOrder)
    }

    if (pathname === '/purchasing/supplier-invoice-documents/analyze' && method === 'POST') {
      const order = purchaseOrders.find((entry) => entry.id === 800)
      const item = order?.items[0]
      return json({
        document_type: 'pdf',
        extraction_method: 'native_text',
        validation_status: 'valid',
        validation_message: 'PDF interpretado',
        parsed_data: {
          folio: 'FAC-001',
          issue_datetime: '2026-06-05',
          currency: 'MXN',
          subtotal: '2200.00',
          transferred_taxes: '0.00',
          total: '2200.00',
          concepts: [],
        },
        items: item
          ? [
              {
                purchase_order_item_id: item.id,
                source_description: item.description,
                matched_description: item.description,
                source_unit: item.unit,
                source_quantity: '40',
                billable_quantity: '40',
                unit_price: '55',
                line_total: '2200',
                match_status: 'matched',
                confidence: '1',
              },
            ]
          : [],
        matched_items: item ? 1 : 0,
        source_items: item ? 1 : 0,
        warnings: [],
        requires_review: true,
      })
    }

    if (pathname === '/purchasing/supplier-invoices/register' && method === 'POST') {
      const multipartBody = request.postData() ?? ''
      const payloadMatch = multipartBody.match(/name="payload_json"\r\n\r\n([\s\S]*?)\r\n--/)
      if (!payloadMatch) return json({ detail: 'Datos de factura no encontrados' }, 422)
      const payload = JSON.parse(payloadMatch[1])
      const order = purchaseOrders.find((entry) => entry.id === Number(payload.purchase_order_id))
      if (!order) return json({ detail: 'Orden de compra no encontrada' }, 404)
      const invoice: SupplierInvoice = {
        id: nextInvoiceId++,
        supplier_id: order.supplier_id,
        purchase_order_id: order.id,
        invoice_number: payload.invoice_number,
        invoice_date: payload.invoice_date,
        due_date: '2026-07-05',
        total: String(payload.total),
        currency: 'MXN',
        fiscal_status: 'pending_manual',
        fiscal_validation_message: 'Factura capturada con PDF; requiere validacion fiscal manual.',
        status: 'fiscal_review',
        document_name: 'FAC-001.pdf',
        notes: null,
        supplier: order.supplier,
        purchase_order: order,
        items: [],
        documents: [
          {
            id: 9900,
            document_type: 'pdf',
            original_file_name: 'FAC-001.pdf',
            file_size: 51,
            validation_status: 'valid',
            is_active: true,
          },
        ],
      }
      supplierInvoices = [invoice, ...supplierInvoices]
      return json(invoice, 201)
    }

    const validateInvoiceMatch = pathname.match(/^\/purchasing\/supplier-invoices\/(\d+)\/validate$/)
    if (validateInvoiceMatch && method === 'POST') {
      const invoiceId = Number(validateInvoiceMatch[1])
      const invoice = supplierInvoices.find((entry) => entry.id === invoiceId)
      if (!invoice) return json({ detail: 'Factura no encontrada' }, 404)
      const order = purchaseOrders.find((entry) => entry.id === invoice.purchase_order_id)
      if (!order) return json({ detail: 'Orden de compra no encontrada' }, 404)
      const status = invoiceStateForOrder(order)
      supplierInvoices = supplierInvoices.map((entry) =>
        entry.id === invoiceId
          ? {
              ...entry,
              status: status.status,
              fiscal_status: 'manual_validated',
              notes: status.message,
              purchase_order: order,
            }
          : entry,
      )
      return json({
        invoice_id: invoiceId,
        status: status.status,
        pending_items: status.pendingItems,
        message: status.message,
      })
    }

    if (pathname === '/purchasing/supplier-payments' && method === 'POST') {
      const payload = await request.postDataJSON()
      const invoice = supplierInvoices.find((entry) => entry.id === Number(payload.supplier_invoice_id))
      if (!invoice) return json({ detail: 'Factura no encontrada' }, 404)
      if (!['approved_for_payment', 'scheduled'].includes(invoice.status)) {
        return json({ detail: 'La factura no esta aprobada para pago' }, 400)
      }
      const payment: SupplierPayment = {
        id: nextPaymentId++,
        supplier_invoice_id: invoice.id,
        amount: String(payload.amount),
        scheduled_date: payload.scheduled_date,
        paid_at: null,
        status: payload.status,
        reference: payload.reference,
      }
      supplierPayments = [payment, ...supplierPayments]
      supplierInvoices = supplierInvoices.map((entry) =>
        entry.id === invoice.id ? { ...entry, status: 'scheduled' } : entry,
      )
      return json(payment, 201)
    }

    const paymentMatch = pathname.match(/^\/purchasing\/supplier-payments\/(\d+)$/)
    if (paymentMatch && method === 'PATCH') {
      const paymentId = Number(paymentMatch[1])
      const payload = await request.postDataJSON()
      const payment = supplierPayments.find((entry) => entry.id === paymentId)
      if (!payment) return json({ detail: 'Pago no encontrado' }, 404)
      supplierPayments = supplierPayments.map((entry) =>
        entry.id === paymentId
          ? { ...entry, status: payload.status ?? entry.status, paid_at: payload.paid_at ?? entry.paid_at }
          : entry,
      )
      if (payload.status === 'paid') {
        supplierInvoices = supplierInvoices.map((entry) =>
          entry.id === payment.supplier_invoice_id ? { ...entry, status: 'paid' } : entry,
        )
      }
      return json(supplierPayments.find((entry) => entry.id === paymentId))
    }

    if (pathname === '/inventory/projects/1/receptions' && method === 'POST') {
      const payload = await request.postDataJSON()
      const expectedList = expectedLists.find((list) => list.id === Number(payload.expected_list_id))
      if (!expectedList) return json({ detail: 'Lista esperada no encontrada' }, 404)
      const receptionItems = payload.items.map(
        (itemPayload: { expected_item_id: number; received_quantity: number }, index: number) => {
          const expectedItem = expectedList.items.find((item) => item.id === itemPayload.expected_item_id)
          if (!expectedItem) return null
          const receivedQuantity = Number(itemPayload.received_quantity)
          expectedItem.received_quantity = String(Number(expectedItem.received_quantity) + receivedQuantity)
          expectedItem.status =
            Number(expectedItem.received_quantity) >= Number(expectedItem.expected_quantity)
              ? 'complete'
              : 'partial'
          purchaseOrders = purchaseOrders.map((order) => {
            if (order.id !== expectedList.purchase_order_id) return order
            const items = order.items.map((poItem) =>
              poItem.id === expectedItem.purchase_order_item_id
                ? {
                    ...poItem,
                    received_quantity: String(Number(poItem.received_quantity) + receivedQuantity),
                    status:
                      Number(poItem.received_quantity) + receivedQuantity >= Number(poItem.quantity_ordered)
                        ? 'received'
                        : 'partially_received',
                  }
                : poItem,
            )
            const isComplete = items.every(
              (poItem) => Number(poItem.received_quantity) >= Number(poItem.quantity_ordered),
            )
            const hasReceived = items.some((poItem) => Number(poItem.received_quantity) > 0)
            return {
              ...order,
              status: isComplete ? 'received' : hasReceived ? 'partially_received' : 'sent',
              items,
            }
          })
          const currentStock = stockItems.find(
            (stock) => stock.description === expectedItem.description && stock.unit === expectedItem.unit,
          )
          if (currentStock) {
            currentStock.quantity_on_hand = String(Number(currentStock.quantity_on_hand) + receivedQuantity)
          } else {
            stockItems = [
              ...stockItems,
              {
                id: 1200 + index,
                warehouse_id: Number(payload.warehouse_id),
                description: expectedItem.description,
                unit: expectedItem.unit,
                quantity_on_hand: String(receivedQuantity),
              },
            ]
          }
          return {
            id: 1100 + index,
            expected_item_id: expectedItem.id,
            description: expectedItem.description,
            received_quantity: String(receivedQuantity),
            accepted_quantity: String(receivedQuantity),
            rejected_quantity: '0',
            condition_status: 'ok',
            notes: null,
            unit: expectedItem.unit,
          }
        },
      ).filter(Boolean)
      const reception = {
        id: 100,
        project_id: 1,
        warehouse_id: Number(payload.warehouse_id),
        expected_list_id: expectedList.id,
        received_at: '2026-06-05',
        delivery_reference: payload.delivery_reference,
        delivered_by: payload.delivered_by,
        received_by: payload.received_by,
        notes: payload.notes,
        status: 'processed',
        items: receptionItems,
      }
      receptions = [reception, ...receptions]
      return json(reception, 201)
    }

    if (path.startsWith('/inventory/projects/')) return json([])

    return json([], 200)
  })
}

async function authenticate(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('acsm_control_token', 'test-token')
  })
}

async function approveAndPrepareOrder(page: Page, sendToSupplier = false) {
  await page.getByRole('button', { name: 'Solicitar aprobacion' }).click()
  await expect(page.getByText('Solicitud de aprobacion enviada.')).toBeVisible()

  await page.getByRole('link', { name: /Aprobaciones/i }).click()
  await page.getByRole('button', { name: /Aprobar cotizacion seleccionada/i }).click()
  await expect(page.getByText('Cotizacion aprobada. Compras ya puede preparar la orden de compra.')).toBeVisible()

  await page.goto('/purchasing')
  await expect(page.getByRole('heading', { name: 'Bandeja de compras' })).toBeVisible()
  await page.getByRole('button', { name: 'Generar orden de compra' }).click()
  await expect(page.getByText('Orden OC-202606-0001 preparada. Revisa y confirma su envio al proveedor.')).toBeVisible()

  if (sendToSupplier) {
    await page.getByRole('button', { name: 'Enviar OC al proveedor' }).click()
    await expect(page.getByText('Orden OC-202606-0001 enviada. Inventario ya tiene el material esperado.')).toBeVisible()
  }
}

test('login muestra el dashboard con sesion activa', async ({ page }) => {
  await mockApi(page)
  await page.goto('/login')

  await page.getByLabel('Contrasena').fill('Admin12345!')
  await page.getByRole('button', { name: 'Entrar' }).click()

  await expect(
    page.getByRole('heading', { name: 'Control Ejecutivo', level: 1 }),
  ).toBeVisible()
  await expect(page.getByText('admin@acsm-control.local').first()).toBeVisible()
})

test('el texto seleccionado mantiene contraste visible en todo el sistema', async ({ page }) => {
  await page.goto('/login')

  const selectionStyle = await page.getByText('ACSM Control').evaluate((element) => {
    const range = document.createRange()
    range.selectNodeContents(element)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)

    const style = window.getComputedStyle(element, '::selection')
    return {
      backgroundColor: style.backgroundColor,
      color: style.color,
      selectedText: selection?.toString(),
    }
  })

  expect(selectionStyle.selectedText).toBe('ACSM Control')
  expect(selectionStyle.backgroundColor).toBe('rgb(23, 105, 170)')
  expect(selectionStyle.color).toBe('rgb(255, 255, 255)')
})

test('control ejecutivo abre el detalle financiero del desarrollo', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/')

  await page.getByRole('button', { name: 'Privada Encinos' }).click()

  await expect(page).toHaveURL('/dashboard/projects/1')
  await expect(page.getByText('10 viviendas · 1 modelos · 1 órdenes')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Portafolio' })).toBeVisible()
})

test('menu principal despliega y contrae submenus por modulo', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing')

  await expect(page.getByRole('link', { name: /Bandeja de compras/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Captura y cotizaciones/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Aprobaciones/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Ordenes de compra/i })).toBeVisible()

  await page.getByRole('link', { name: /^Inventario$/i }).click()
  await expect(page.getByRole('link', { name: /Recepcion de materiales/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Control de avance/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Validar documentos/i })).toHaveCount(0)
  await expect(page.getByRole('link', { name: /Documentos material/i })).toHaveCount(0)

  await page.getByRole('link', { name: /^Control Ejecutivo$/i }).click()
  await expect(page.getByRole('link', { name: /Recepcion de materiales/i })).toBeHidden()
  await expect(page.getByRole('link', { name: /Control de avance/i })).toBeHidden()
})

test('menu oculta modulos sin permiso para usuarios operativos', async ({ page }) => {
  await mockApi(page, limitedUser)
  await authenticate(page)
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Inmobiliarias', level: 1 })).toBeVisible()
  await expect(page.getByRole('link', { name: /^Inmobiliarias$/i }).first()).toBeVisible()
  await expect(page.getByRole('link', { name: /^Compras$/i })).toHaveCount(0)
  await expect(page.getByRole('link', { name: /^Inventario$/i })).toHaveCount(0)
  await expect(page.getByRole('link', { name: /^Roles$/i })).toHaveCount(0)
})

test('compras separa detalle de solicitud y captura de cotizacion', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')

  await expect(page.getByRole('heading', { name: 'Solicitudes de cotizacion' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Ver detalle/i }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: /Capturar cotizacion/i }).first()).toBeVisible()

  await page.getByRole('button', { name: /Ver detalle/i }).first().click()
  const detailDialog = page.getByRole('dialog')
  await expect(detailDialog.getByText('Detalle de solicitud')).toBeVisible()
  await expect(detailDialog.getByText('SC-202606-0008', { exact: true })).toBeVisible()
  await detailDialog.getByLabel('Cerrar').click()

  await page.getByRole('button', { name: /Capturar cotizacion/i }).first().click()
  await expect(page.getByText(/Solicitud activa: Compra de varilla/)).toBeVisible()

  await page.getByLabel('Proveedor cotizante').selectOption({ label: 'Aceros del Bajio' })
  await page.getByLabel('Folio de cotizacion').fill('COT-UI-001')
  await page.locator('tr', { hasText: 'Varilla 3/8' }).locator('input').first().fill('20')
  await page.getByRole('button', { name: 'Guardar cotizacion' }).click()

  await expect(page.getByText('Datos guardados para su comparativo.')).toBeVisible()
})

test('compras cancela una cotizacion y solicita reemplazo con motivo obligatorio', async ({
  page,
}) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations?rfq_id=10&focus=comparison')

  await page.getByRole('button', { name: 'Solicitar nueva' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Cancelar y solicitar nueva cotizacion' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Enviar solicitud al proveedor' })).toBeDisabled()

  await dialog
    .getByLabel('Motivo y correcciones solicitadas *')
    .fill('Corregir cantidades, vigencia y reenviar el documento firmado.')
  await dialog.getByRole('button', { name: 'Enviar solicitud al proveedor' }).click()

  await expect(dialog).toHaveCount(0)
  await expect(
    page.getByText(
      'Cotizacion de Aceros del Bajio cancelada. La solicitud de reemplazo se envio a compras@aceros-bajio.example.com.',
    ),
  ).toBeVisible()
  await expect(page.getByText('2 cotizaciones completas de 3 requeridas')).toBeVisible()
})

test('captura asistida abre desde la alerta y permite continuar manualmente', async ({
  page,
}) => {
  await mockApi(page, user, { withAssistedQuote: true })
  await authenticate(page)
  await page.goto(
    '/purchasing/operations?rfq_id=11&focus=quote-review&draft_id=500&notification_id=900',
  )

  const assistedSection = page
    .getByRole('heading', { name: 'Cotizaciones por revisar' })
    .locator('xpath=ancestor::section[1]')
  await expect(assistedSection).toBeVisible()
  await expect(assistedSection.locator('input[value="COT-ASISTIDA-001"]')).toBeVisible()
  await expect
    .poll(async () =>
      assistedSection.evaluate((element) => {
        const bounds = element.getBoundingClientRect()
        return bounds.top >= 0 && bounds.top < window.innerHeight
      }),
    )
    .toBe(true)

  await assistedSection.getByRole('button', { name: 'Ocultar asistencia' }).click()
  await expect(
    assistedSection.getByText('La asistencia esta oculta. Los documentos pendientes se conservan sin cambios.'),
  ).toBeVisible()

  await page.goto('/purchasing/operations?rfq_id=11')
  await expect(
    assistedSection.getByText('La asistencia esta oculta. Los documentos pendientes se conservan sin cambios.'),
  ).toBeVisible()
  await assistedSection.getByRole('button', { name: 'Revisar cotizaciones' }).click()
  await expect(assistedSection.locator('input[value="COT-ASISTIDA-001"]')).toBeVisible()

  await assistedSection.getByRole('button', { name: 'Usar captura manual' }).click()
  await expect(
    page.getByText(
      'Captura asistida cancelada. El documento se conserva y los datos recuperados quedaron en la captura manual.',
    ),
  ).toBeVisible()
  await expect(page.getByLabel('Proveedor cotizante')).toHaveValue('1')
  await expect(page.getByLabel('Folio de cotizacion')).toHaveValue('COT-ASISTIDA-001')
  await expect(page.locator('tr', { hasText: 'Varilla 3/8' }).locator('input').first()).toHaveValue(
    '20',
  )
  await expect(page.getByRole('button', { name: 'Reactivar asistencia' })).toBeVisible()
  await expect(assistedSection).toHaveCount(0)
})

test('compras crea solicitud de cotizacion con materiales y tres proveedores', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')

  await page.getByLabel('Nombre de solicitud').fill('Cemento para prototipo')
  await page.getByLabel('Fecha requerida').fill('2026-06-20')
  await page.getByLabel('Limite de respuesta').fill('2026-06-12')
  await page.getByPlaceholder('Buscar material...').fill('Cemento gris 50kg')

  for (const supplier of suppliers) {
    await page.locator('label', { hasText: supplier.name }).locator('input[type="checkbox"]').check()
  }

  await page.getByRole('button', { name: 'Crear solicitud' }).click()

  await expect(page.getByText('Solicitud SC-202606-0099 creada.')).toBeVisible()
  await expect(page.getByText('Cemento para prototipo').first()).toBeVisible()
  await expect(page.getByText('3 proveedores · 1 partidas').first()).toBeVisible()
})

test('compras aprueba cotizacion y prepara la orden como pasos separados', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')

  await expect(page.getByText(/Solicitud activa: Cemento/)).toBeVisible()
  await expect(page.getByText('3 cotizaciones completas de 3 requeridas')).toBeVisible()

  await approveAndPrepareOrder(page)

  await page.getByRole('link', { name: /Ordenes de compra/i }).click()
  await expect(page.getByRole('heading', { name: 'Ordenes de compra', level: 2 })).toBeVisible()
  await expect(page.getByRole('button', { name: /OC-202606-0001\s+Ver documento/i })).toBeVisible()
  await expect(page.getByText('Aceros del Bajio')).toBeVisible()
})

test('inventario recibe parcialmente una orden de compra generada desde compras', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')
  await approveAndPrepareOrder(page, true)

  await page.goto('/inventory/purchase-order-receiving')
  await expect(page.getByRole('heading', { name: 'Recepcion contra orden de compra' })).toBeVisible()
  await expect(page.getByText('1 pendientes')).toBeVisible()

  await page.getByLabel('Orden de compra').selectOption('800')
  await expect(page.getByText('Lista esperada OC-202606-0001')).toBeVisible()

  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.getByLabel('Entregado Cemento gris 50kg').fill('40')
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()
  await expect(page.getByText('Recepcion registrada contra OC-202606-0001')).toBeVisible()

  await page.goto('/inventory/reception-history')
  await expect(page.getByRole('heading', { name: 'Historial de recepciones' })).toBeVisible()
  await expect(page.getByRole('table').first().getByText('OC-202606-0001')).toBeVisible()

  await page.goto('/inventory/missing')
  await expect(page.getByRole('heading', { name: 'Faltantes' })).toBeVisible()
  const missingSection = page.locator('section', { has: page.getByRole('heading', { name: 'Faltantes' }) })
  const statusSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Estatus de materiales' }),
  })
  await expect(missingSection.locator('tr', { hasText: 'Cemento gris 50kg' }).getByText('60 saco')).toBeVisible()
  await expect(statusSection.locator('tr', { hasText: 'Cemento gris 50kg' }).getByText('40 saco')).toBeVisible()
  await expect(statusSection.locator('tr', { hasText: 'Cemento gris 50kg' }).getByText('partial')).toBeVisible()
})

test('inventario registra una partida que no llego sin alterar cantidades', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')
  await approveAndPrepareOrder(page, true)
  await page.goto('/inventory/material-receiving')

  await page.getByLabel('Orden de compra').selectOption('800')
  const materialRow = page.locator('tr', { hasText: 'Cemento gris 50kg' })
  await materialRow.locator('select').selectOption('not_delivered')

  await expect(page.getByLabel('Entregado Cemento gris 50kg')).toHaveValue('0')
  await expect(page.getByLabel('Entregado Cemento gris 50kg')).toBeDisabled()
  await expect(page.getByLabel('Aceptado Cemento gris 50kg')).toHaveValue('0')
  await expect(page.getByLabel('Aceptado Cemento gris 50kg')).toBeDisabled()
  await expect(page.getByLabel('Rechazado Cemento gris 50kg')).toHaveValue('0')
  await expect(page.getByLabel('Rechazado Cemento gris 50kg')).toBeDisabled()
  await expect(materialRow.locator('input').last()).toHaveValue(
    'Material no entregado por el proveedor',
  )
  await expect(page.getByRole('button', { name: 'Registrar recepcion' })).toBeEnabled()

  const requestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'POST' &&
      new URL(request.url()).pathname.endsWith('/inventory/projects/1/receptions'),
  )
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()
  const request = await requestPromise
  const payload = request.postDataJSON()
  expect(payload.items).toEqual([
    expect.objectContaining({
      received_quantity: 0,
      accepted_quantity: 0,
      rejected_quantity: 0,
      condition_status: 'not_delivered',
      notes: 'Material no entregado por el proveedor',
    }),
  ])
  await expect(page.getByText('Recepcion registrada contra OC-202606-0001')).toBeVisible()
})

test('inventario exige crear y seleccionar una bodega antes de recibir material', async ({ page }) => {
  await mockApi(page, user, { withoutWarehouses: true })
  await authenticate(page)
  await page.goto('/inventory/material-receiving')

  await expect(page.getByText('Falta crear una bodega para este desarrollo')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Registrar recepcion' })).toBeDisabled()

  await page.getByRole('button', { name: 'Crear bodega' }).click()
  await expect(page.getByRole('heading', { name: 'Nueva bodega' })).toBeVisible()
  await page.getByLabel('Nombre de la bodega').fill('Bodega de acceso norte')
  await page.getByLabel('Ubicacion').fill('Acceso norte')
  await page.getByRole('button', { name: 'Crear y seleccionar' }).click()

  await expect(
    page.getByText('Bodega Bodega de acceso norte creada y seleccionada para esta recepcion'),
  ).toBeVisible()
  await expect(page.getByLabel('Bodega')).toHaveValue('1')
  await expect(page.getByText('Falta crear una bodega para este desarrollo')).toHaveCount(0)
})

test('pagos bloquea factura con faltantes y permite pagar al completar recepcion', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')
  await approveAndPrepareOrder(page, true)

  await page.goto('/inventory/purchase-order-receiving')
  await page.getByLabel('Orden de compra').selectOption('800')
  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.getByLabel('Entregado Cemento gris 50kg').fill('40')
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()
  await expect(page.getByText('Recepcion registrada contra OC-202606-0001')).toBeVisible()

  await page.goto('/supplier-payments')
  await page.getByRole('tab', { name: /Facturas/ }).click()
  const invoiceSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Facturas de proveedores' }),
  })
  await invoiceSection.locator('select').first().selectOption('800')
  await invoiceSection.getByPlaceholder('Folio factura').fill('FAC-001')
  await invoiceSection.locator('input[type="date"]').fill('2026-06-05')
  await invoiceSection.locator('input[type="file"]').first().setInputFiles({
    name: 'FAC-001.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n%%EOF'),
  })
  await invoiceSection.getByPlaceholder('Importe antes de impuestos').fill('2200')
  await invoiceSection.getByPlaceholder('Total con impuestos').fill('2200')
  await invoiceSection.getByRole('button', { name: 'Guardar factura' }).click()

  await expect(page.getByText('Factura FAC-001 registrada como Revision fiscal.')).toBeVisible()
  await expect(invoiceSection.locator('tr', { hasText: 'FAC-001' }).getByText('Revision fiscal')).toBeVisible()

  await invoiceSection.locator('tr', { hasText: 'FAC-001' }).getByRole('button', { name: 'Revisar' }).click()
  await expect(page.getByText('Factura bloqueada: 1 partida(s) pendiente(s) por recibir.')).toBeVisible()
  await expect(invoiceSection.locator('tr', { hasText: 'FAC-001' }).getByText('Bloqueada por faltantes')).toBeVisible()

  await page.goto('/inventory/purchase-order-receiving')
  await page.getByLabel('Orden de compra').selectOption('800')
  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.getByRole('button', { name: 'Recibir todo' }).click()
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()
  await expect(page.getByText('Recepcion registrada contra OC-202606-0001')).toBeVisible()

  await page.goto('/supplier-payments')
  await page.getByRole('tab', { name: /Facturas/ }).click()
  const refreshedInvoiceSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Facturas de proveedores' }),
  })
  await refreshedInvoiceSection.locator('tr', { hasText: 'FAC-001' }).getByRole('button', { name: 'Revisar' }).click()
  await expect(page.getByText('Factura validada y aprobada para pago.')).toBeVisible()
  await expect(
    refreshedInvoiceSection.locator('tr', { hasText: 'FAC-001' }).getByText('Aprobada para pago'),
  ).toBeVisible()

  await page.getByRole('tab', { name: /Pagos/ }).click()
  const paymentSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Programar pago' }),
  })
  await paymentSection.locator('select').first().selectOption('9000')
  await paymentSection.locator('input[type="date"]').fill('2026-07-04')
  await paymentSection.getByPlaceholder('Referencia interna').fill('PAGO-FAC-001')
  await paymentSection.getByRole('button', { name: 'Programar pago' }).click()
  await expect(page.getByText('Pago programado para factura FAC-001.')).toBeVisible()
  await expect(paymentSection.locator('tr', { hasText: 'FAC-001' }).getByText('Pago programado')).toBeVisible()

  await paymentSection.locator('tr', { hasText: 'FAC-001' }).getByRole('button', { name: 'Pagado' }).click()
  await expect(page.getByText('Pago marcado como realizado.')).toBeVisible()
  await expect(paymentSection.locator('tr', { hasText: 'FAC-001' }).getByText('Pagada')).toBeVisible()
})

test('pagos captura precios e importes con formato mexicano sin alterar la cantidad', async ({
  page,
}) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')
  await approveAndPrepareOrder(page, true)

  await page.goto('/inventory/material-receiving')
  await page.getByLabel('Orden de compra').selectOption('800')
  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.getByLabel('Entregado Cemento gris 50kg').fill('40')
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()

  await page.goto('/supplier-payments')
  await page.getByRole('tab', { name: /Facturas/ }).click()
  const invoiceSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Facturas de proveedores' }),
  })
  await invoiceSection.locator('select').first().selectOption('800')
  await invoiceSection.getByRole('button', { name: 'Parcial por entregas' }).click()
  await expect(
    page.getByText('Orden OC-202606-0001 configurada para facturacion parcial.'),
  ).toBeVisible()

  const quantityInput = invoiceSection.getByLabel(
    'Cantidad a facturar de Cemento gris 50kg',
  )
  const unitPriceInput = invoiceSection.getByLabel(
    'Precio unitario de Cemento gris 50kg',
  )

  await quantityInput.fill('1')
  await quantityInput.blur()
  await unitPriceInput.fill('21,064.50')
  await unitPriceInput.blur()

  await expect(quantityInput).toHaveValue('1')
  await expect(unitPriceInput).toHaveValue('21,064.50')
  await expect(
    invoiceSection.getByText('$21,064.50', { exact: true }).first(),
  ).toBeVisible()
})

test('pagos interpreta la factura y autocompleta encabezado y partidas recibidas', async ({
  page,
}) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing/operations')
  await approveAndPrepareOrder(page, true)

  await page.goto('/inventory/material-receiving')
  await page.getByLabel('Orden de compra').selectOption('800')
  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.getByLabel('Entregado Cemento gris 50kg').fill('40')
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()

  await page.goto('/supplier-payments')
  await page.getByRole('tab', { name: /Facturas/ }).click()
  const invoiceSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Facturas de proveedores' }),
  })
  await invoiceSection.locator('select').first().selectOption('800')
  await invoiceSection.getByRole('button', { name: 'Parcial por entregas' }).click()
  await invoiceSection.locator('input[type="file"]').first().setInputFiles({
    name: 'FAC-001.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n%%EOF'),
  })

  await expect(invoiceSection.getByText('PDF interpretado')).toBeVisible()
  await expect(invoiceSection.getByText('1 de 1 partidas identificadas')).toBeVisible()
  await expect(invoiceSection.getByPlaceholder('Folio factura')).toHaveValue('FAC-001')
  await expect(invoiceSection.locator('input[type="date"]').first()).toHaveValue('2026-06-05')
  await expect(
    invoiceSection.getByLabel('Cantidad a facturar de Cemento gris 50kg'),
  ).toHaveValue('40')
  await expect(
    invoiceSection.getByLabel('Precio unitario de Cemento gris 50kg'),
  ).toHaveValue('55.00')
})
