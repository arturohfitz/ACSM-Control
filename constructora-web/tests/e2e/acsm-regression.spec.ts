import { expect, type Page, test } from '@playwright/test'

const user = {
  id: 1,
  full_name: 'Administrador Maestro',
  email: 'admin@acsm-control.local',
  is_active: true,
  is_master_admin: true,
  permissions: [],
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

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = `${url.pathname.replace('/api/v1', '')}${url.search}`
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
    if (path === '/auth/me') return json(user)
    if (path === '/projects') return json(projects)
    if (path === '/materials') return json(materials)
    if (path === '/purchasing/suppliers') return json(suppliers)
    if (path === '/purchasing/supplier-rfqs') return json(rfqs)
    if (path.startsWith('/purchasing/supplier-rfq-exceptions')) return json([])
    if (path.startsWith('/purchasing/purchase-orders')) return json([])
    if (path === '/purchasing/supplier-rfqs/10/quotes') return json([])
    if (path === '/purchasing/supplier-rfqs/10/comparison') return json([])
    if (path === '/purchasing/supplier-rfqs/11/quotes' && method === 'GET') return json([])
    if (path === '/purchasing/supplier-rfqs/11/comparison') return json([])
    if (path === '/purchasing/supplier-rfqs/11/quotes' && method === 'POST') {
      return json({
        id: 500,
        company_id: 1,
        rfq_id: 11,
        supplier_id: 1,
        quote_number: 'COT-UI-001',
        status: 'received',
        subtotal: '800.00',
        delivery_days: 5,
        payment_terms_days: 30,
        supplier: suppliers[0],
        items: [],
        created_at: '2026-06-03T10:00:00-06:00',
        updated_at: '2026-06-03T10:00:00-06:00',
      })
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
