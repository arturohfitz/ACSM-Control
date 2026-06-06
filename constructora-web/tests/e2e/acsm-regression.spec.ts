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
  let rfqState = clone(rfqs)
  const quotesByRfq: Record<number, SupplierQuote[]> = {
    10: suppliers.map((supplier, index) => makeQuote(rfqs[0], supplier, 600 + index, 22 + index)),
    11: [],
  }
  let approvals: Approval[] = []
  let purchaseOrders: PurchaseOrder[] = []
  let nextRfqId = 20
  let nextQuoteId = 700

  const upsertRfq = (rfqId: number, patch: Partial<Rfq>) => {
    rfqState = rfqState.map((rfq) => (rfq.id === rfqId ? { ...rfq, ...patch } : rfq))
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
    if (path === '/projects') return json(projects)
    if (path === '/materials') return json(materials)
    if (path === '/purchasing/suppliers') return json(suppliers)
    if (pathname === '/purchasing/supplier-rfqs' && method === 'GET') return json(rfqState)
    if (path.startsWith('/purchasing/supplier-rfq-exceptions')) return json([])
    if (pathname === '/purchasing/purchase-orders' && method === 'GET') return json(purchaseOrders)
    if (pathname === '/purchasing/supplier-quote-approvals') return json(approvals)

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
  await expect(page.getByText('OC-202606-0001')).toBeVisible()
  await expect(page.getByText('Aceros del Bajio')).toBeVisible()
})
