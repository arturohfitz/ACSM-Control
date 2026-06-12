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
  project_id: number
  warehouse_id: number
  po_number: string
  status: string
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
  status: string
  document_name: string | null
  notes: string | null
  supplier: Supplier
  purchase_order: PurchaseOrder
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

async function mockApi(page: Page, currentUser = user) {
  const warehouses = [{ id: 1, project_id: 1, name: 'Bodega Privada Encinos', location: 'Obra' }]
  let rfqState = clone(rfqs)
  const quotesByRfq: Record<number, SupplierQuote[]> = {
    10: suppliers.map((supplier, index) => makeQuote(rfqs[0], supplier, 600 + index, 22 + index)),
    11: [],
  }
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
    if (path === '/projects') return json(projects)
    if (path === '/materials') return json(materials)
    if (path === '/purchasing/suppliers') return json(suppliers)
    if (pathname === '/purchasing/supplier-rfqs' && method === 'GET') return json(rfqState)
    if (path.startsWith('/purchasing/supplier-rfq-exceptions')) return json([])
    if (pathname === '/purchasing/purchase-orders' && method === 'GET') return json(purchaseOrders)
    if (pathname === '/purchasing/supplier-quote-approvals') return json(approvals)
    if (pathname === '/purchasing/supplier-invoices' && method === 'GET') return json(supplierInvoices)
    if (pathname === '/purchasing/supplier-payments' && method === 'GET') return json(supplierPayments)
    if (pathname === '/inventory/projects/1/warehouses') return json(warehouses)
    if (pathname === '/inventory/projects/1/expected-materials') return json(expectedLists)
    if (pathname === '/inventory/projects/1/status') return json(inventoryStatus())
    if (pathname === '/inventory/projects/1/missing-materials') {
      return json(inventoryStatus().filter((item) => Number(item.pending_quantity) > 0))
    }
    if (pathname === '/inventory/projects/1/receptions' && method === 'GET') return json(receptions)
    if (pathname === '/inventory/warehouses/1/stock') return json(stockItems)

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
      upsertRfq(quote.rfq_id, { status: 'awarded' })
      const order: PurchaseOrder = {
        id: 800,
        project_id: 1,
        warehouse_id: 1,
        po_number: 'OC-202606-0001',
        status: 'issued',
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
      expectedLists = [
        {
          id: 810,
          warehouse_id: 1,
          purchase_order_id: order.id,
          name: `Lista esperada ${order.po_number}`,
          document_number: order.po_number,
          supplier_name: order.supplier.name,
          source_document_name: null,
          source_document_hash: null,
          items: order.items.map((item) => ({
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
      approvals = []
      return json({ purchase_order: order, expected_list: { id: 1 } })
    }

    const sendOrderMatch = pathname.match(/^\/purchasing\/purchase-orders\/(\d+)\/send$/)
    if (sendOrderMatch && method === 'POST') {
      const orderId = Number(sendOrderMatch[1])
      purchaseOrders = purchaseOrders.map((order) =>
        order.id === orderId ? { ...order, status: 'sent' } : order,
      )
      return json(purchaseOrders.find((order) => order.id === orderId))
    }

    if (pathname === '/purchasing/supplier-invoices' && method === 'POST') {
      const payload = await request.postDataJSON()
      const order = purchaseOrders.find((entry) => entry.id === Number(payload.purchase_order_id))
      if (!order) return json({ detail: 'Orden de compra no encontrada' }, 404)
      const status = invoiceStateForOrder(order)
      const invoice: SupplierInvoice = {
        id: nextInvoiceId++,
        supplier_id: order.supplier_id,
        purchase_order_id: order.id,
        invoice_number: payload.invoice_number,
        invoice_date: payload.invoice_date,
        due_date: '2026-07-05',
        total: String(payload.total),
        status: status.status,
        document_name: payload.document_name,
        notes: status.message,
        supplier: order.supplier,
        purchase_order: order,
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
          ? { ...entry, status: status.status, notes: status.message, purchase_order: order }
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
            description: expectedItem.description,
            received_quantity: String(receivedQuantity),
            unit: expectedItem.unit,
          }
        },
      ).filter(Boolean) as Array<{ id: number; description: string; received_quantity: string; unit: string }>
      const reception = {
        id: 100,
        received_at: '2026-06-05',
        delivery_reference: payload.delivery_reference,
        received_by: payload.received_by,
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

test('login muestra el dashboard con sesion activa', async ({ page }) => {
  await mockApi(page)
  await page.goto('/login')

  await page.getByLabel('Contrasena').fill('Admin12345!')
  await page.getByRole('button', { name: 'Entrar' }).click()

  await expect(page.getByRole('heading', { name: 'Inicio' })).toBeVisible()
  await expect(page.getByText('admin@acsm-control.local').first()).toBeVisible()
})

test('menu principal despliega y contrae submenus por modulo', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing')

  await expect(page.getByRole('link', { name: /Solicitudes/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Aprobaciones/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Ordenes de compra/i })).toBeVisible()

  await page.getByRole('link', { name: /^Inventario$/i }).click()
  await expect(page.getByRole('link', { name: /Recepcion por OC/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Recepcion sin OC/i })).toBeVisible()

  await page.getByRole('link', { name: /^Inicio$/i }).click()
  await expect(page.getByRole('link', { name: /Recepcion por OC/i })).toBeHidden()
})

test('menu oculta modulos sin permiso para usuarios operativos', async ({ page }) => {
  await mockApi(page, limitedUser)
  await authenticate(page)
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Inicio' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Desarrolladoras/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /^Compras$/i })).toHaveCount(0)
  await expect(page.getByRole('link', { name: /^Inventario$/i })).toHaveCount(0)
  await expect(page.getByRole('link', { name: /^Roles$/i })).toHaveCount(0)
})

test('compras separa detalle de solicitud y captura de cotizacion', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing')

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

test('compras crea solicitud de cotizacion con materiales y tres proveedores', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing')

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

test('compras envia comparativo a aprobacion y gerencia genera orden de compra', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing')

  await expect(page.getByText(/Solicitud activa: Cemento/)).toBeVisible()
  await expect(page.getByText('3 cotizaciones completas de 3 requeridas')).toBeVisible()

  await page.getByRole('button', { name: 'Solicitar aprobacion' }).click()
  await expect(page.getByText('Solicitud de aprobacion enviada.')).toBeVisible()

  await page.getByRole('link', { name: /Aprobaciones/i }).click()
  await expect(page.getByRole('heading', { name: 'Aprobaciones de cotizacion' })).toBeVisible()
  await expect(page.getByText('Cemento').first()).toBeVisible()
  await expect(page.getByRole('button', { name: /Aprobar cotizacion seleccionada y generar OC/i })).toBeVisible()

  await page.getByRole('button', { name: /Aprobar cotizacion seleccionada y generar OC/i }).click()
  await expect(page.getByText('Aprobacion registrada. Se genero la orden OC-202606-0001.')).toBeVisible()

  await page.getByRole('link', { name: /Ordenes de compra/i }).click()
  await expect(page.getByRole('heading', { name: 'Ordenes de compra', level: 2 })).toBeVisible()
  await expect(page.getByRole('button', { name: /OC-202606-0001\s+Ver documento/i })).toBeVisible()
  await expect(page.getByText('Aceros del Bajio')).toBeVisible()
})

test('inventario recibe parcialmente una orden de compra generada desde compras', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing')

  await page.getByRole('button', { name: 'Solicitar aprobacion' }).click()
  await expect(page.getByText('Solicitud de aprobacion enviada.')).toBeVisible()

  await page.getByRole('link', { name: /Aprobaciones/i }).click()
  await page.getByRole('button', { name: /Aprobar cotizacion seleccionada y generar OC/i }).click()
  await expect(page.getByText('Aprobacion registrada. Se genero la orden OC-202606-0001.')).toBeVisible()

  await page.goto('/inventory/purchase-order-receiving')
  await expect(page.getByRole('heading', { name: 'Recepcion contra orden de compra' })).toBeVisible()
  await expect(page.getByText('1 pendientes')).toBeVisible()

  await page.getByLabel('Orden de compra').selectOption('800')
  await expect(page.getByText('Lista esperada OC-202606-0001')).toBeVisible()

  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.locator('tr', { hasText: 'Cemento gris 50kg' }).locator('input[type="number"]').fill('40')
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()
  await expect(page.getByText('Recepcion registrada contra OC-202606-0001')).toBeVisible()

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

test('pagos bloquea factura con faltantes y permite pagar al completar recepcion', async ({ page }) => {
  await mockApi(page)
  await authenticate(page)
  await page.goto('/purchasing')

  await page.getByRole('button', { name: 'Solicitar aprobacion' }).click()
  await expect(page.getByText('Solicitud de aprobacion enviada.')).toBeVisible()

  await page.getByRole('link', { name: /Aprobaciones/i }).click()
  await page.getByRole('button', { name: /Aprobar cotizacion seleccionada y generar OC/i }).click()
  await expect(page.getByText('Aprobacion registrada. Se genero la orden OC-202606-0001.')).toBeVisible()

  await page.goto('/inventory/purchase-order-receiving')
  await page.getByLabel('Orden de compra').selectOption('800')
  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.locator('tr', { hasText: 'Cemento gris 50kg' }).locator('input[type="number"]').fill('40')
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()
  await expect(page.getByText('Recepcion registrada contra OC-202606-0001')).toBeVisible()

  await page.goto('/supplier-payments')
  const invoiceSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Facturas de proveedores' }),
  })
  await invoiceSection.locator('select').first().selectOption('800')
  await invoiceSection.getByPlaceholder('Folio factura').fill('FAC-001')
  await invoiceSection.locator('input[type="date"]').fill('2026-06-05')
  await invoiceSection.getByPlaceholder('Total factura').fill('2200')
  await invoiceSection.getByRole('button', { name: 'Guardar factura' }).click()

  await expect(page.getByText('Factura FAC-001 registrada como Bloqueada por faltantes.')).toBeVisible()
  await expect(invoiceSection.locator('tr', { hasText: 'FAC-001' }).getByText('Bloqueada por faltantes')).toBeVisible()

  await invoiceSection.locator('tr', { hasText: 'FAC-001' }).getByRole('button', { name: 'Validar' }).click()
  await expect(page.getByText('Factura bloqueada: 1 partida(s) pendiente(s) por recibir.')).toBeVisible()

  await page.goto('/inventory/purchase-order-receiving')
  await page.getByLabel('Orden de compra').selectOption('800')
  await page.getByPlaceholder('Recibe').fill('Encargado de bodega')
  await page.getByRole('button', { name: 'Registrar recepcion' }).click()
  await expect(page.getByText('Recepcion registrada contra OC-202606-0001')).toBeVisible()

  await page.goto('/supplier-payments')
  const refreshedInvoiceSection = page.locator('section', {
    has: page.getByRole('heading', { name: 'Facturas de proveedores' }),
  })
  await refreshedInvoiceSection.locator('tr', { hasText: 'FAC-001' }).getByRole('button', { name: 'Validar' }).click()
  await expect(page.getByText('Factura validada y aprobada para pago.')).toBeVisible()
  await expect(
    refreshedInvoiceSection.locator('tr', { hasText: 'FAC-001' }).getByText('Aprobada para pago'),
  ).toBeVisible()

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
