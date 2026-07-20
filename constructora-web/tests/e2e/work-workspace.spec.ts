import { expect, type Page, test } from '@playwright/test'

const project = {
  id: 101,
  client_id: 21,
  name: 'P-33-E-PLS-SMG-01',
  location: 'Etapa norte',
  status: 'active',
}

const requisition = {
  id: 301,
  project_id: project.id,
  house_model_id: 201,
  requisition_number: 'RO-202607-0001',
  title: 'Cemento para cimentacion',
  status: 'in_review',
  priority: 'normal',
  required_date: '2026-07-30',
  created_at: '2026-07-20T09:00:00-06:00',
  items: [
    {
      id: 1,
      description: 'Cemento normal gris tipo I',
      requested_quantity: '120',
      requested_unit: 'SACO',
      unit: 'SACO',
    },
  ],
}

async function mockWorkApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const pathname = url.pathname.replace('/api/v1', '')
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

    if (pathname === '/auth/me') {
      return json({
        id: 1,
        full_name: 'Administrador Maestro',
        email: 'admin@acsm-control.local',
        is_active: true,
        is_master_admin: true,
        permissions: [],
      })
    }
    if (pathname === '/projects') return json([project])
    if (pathname === '/house-models') return json([{ id: 201, name: 'San Miguel' }])
    if (pathname === `/projects/${project.id}/summary`) {
      return json({
        project,
        assigned_models: [{ id: 401, house_model_id: 201, quantity: '12' }],
      })
    }
    if (pathname === '/materials/model-catalog') {
      return json(Array.from({ length: 103 }, (_, index) => ({
        id: index + 1,
        is_linked: index < 100,
        validation_status: index < 100 ? 'validated' : 'pending',
      })))
    }
    if (pathname === '/construction-concepts/model-catalog') {
      return json(Array.from({ length: 162 }, (_, index) => ({
        id: index + 1,
        is_linked: index < 160,
        validation_status: index < 160 ? 'validated' : 'pending',
      })))
    }
    if (pathname === '/material-requisitions' && request.method() === 'GET') return json([requisition])
    if (pathname === `/material-requisitions/${requisition.id}/tracking`) {
      return json({
        requisition,
        project_name: project.name,
        house_model_name: 'San Miguel',
        steps: [
          { key: 'created', label: 'Solicitud de Obra', status: 'complete', detail: 'Requerimiento enviado.' },
          { key: 'review', label: 'Revision de Compras', status: 'active', detail: 'Compras valida las partidas.' },
          { key: 'rfq', label: 'Cotizacion', status: 'pending', detail: 'Pendiente de proveedores.' },
          { key: 'approval', label: 'Aprobacion', status: 'pending' },
          { key: 'order', label: 'Orden de compra', status: 'pending' },
          { key: 'receipt', label: 'Recepcion', status: 'pending' },
        ],
      })
    }
    return json([])
  })
  await page.addInitScript(() => {
    window.localStorage.setItem('acsm_control_token', 'test-token')
  })
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
}

test('Centro de Obra conserva contexto y es legible en escritorio y movil', async ({ page }) => {
  await mockWorkApi(page)
  await page.goto('/work?project_id=101&house_model_id=201&requisition_id=301')

  await expect(page.getByRole('main').getByRole('heading', { name: 'Centro de Obra' })).toBeVisible()
  await expect(page.getByText('Cemento para cimentacion').first()).toBeVisible()
  await expect(page.getByText('Revision de Compras').first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await page.screenshot({ path: '/tmp/work-desktop.png', fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('main').getByRole('heading', { name: 'Centro de Obra' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
  await page.screenshot({ path: '/tmp/work-mobile.png', fullPage: true })
})
