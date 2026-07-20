import { expect, test } from '@playwright/test'

const user = {
  id: 1,
  full_name: 'Administrador Maestro',
  email: 'admin@acsm-control.local',
  is_active: true,
  is_master_admin: true,
  permissions: [],
}

const cases = [
  {
    id: 41,
    expected_list_id: 41,
    purchase_order_id: 91,
    purchase_order_number: 'OC-202607-0091',
    purchase_order_status: 'sent',
    project_id: 7,
    project_name: 'P-33-E-PLS-SMG-01',
    warehouse_id: 3,
    warehouse_name: 'Bodega San Miguel',
    supplier_id: 12,
    supplier_name: 'Materiales del Centro',
    issued_at: '2026-07-18',
    expected_delivery_date: '2026-07-22',
    stage: 'awaiting',
    item_count: 2,
    completed_item_count: 0,
    pending_item_count: 2,
    issue_item_count: 0,
    line_progress_percent: '0',
    next_action_label: 'Continuar recepcion',
    next_action_url: '/inventory/material-receiving?type=oc&project_id=7&purchase_order_id=91&warehouse_id=3',
    items: [
      { expected_item_id: 1, description: 'Cemento normal gris', unit: 'SACO', house_model_id: 2, house_model_name: 'San Miguel', expected_quantity: '100', accepted_quantity: '0', pending_quantity: '100', status: 'pending' },
      { expected_item_id: 2, description: 'Varilla corrugada 3/8', unit: 'PZA', house_model_id: 2, house_model_name: 'San Miguel', expected_quantity: '50', accepted_quantity: '0', pending_quantity: '50', status: 'pending' },
    ],
  },
  {
    id: 42,
    expected_list_id: 42,
    purchase_order_id: 92,
    purchase_order_number: 'OC-202607-0092',
    purchase_order_status: 'partially_received',
    project_id: 8,
    project_name: 'Torres Norte',
    warehouse_id: 4,
    warehouse_name: 'Almacen Norte',
    supplier_id: 13,
    supplier_name: 'Aceros del Bajio',
    issued_at: '2026-07-17',
    expected_delivery_date: '2026-07-20',
    stage: 'partial',
    item_count: 2,
    completed_item_count: 1,
    pending_item_count: 1,
    issue_item_count: 0,
    line_progress_percent: '75',
    next_action_label: 'Continuar recepcion',
    next_action_url: '/inventory/material-receiving?type=oc&project_id=8&purchase_order_id=92&warehouse_id=4',
    items: [
      { expected_item_id: 3, description: 'Mortero en saco', unit: 'TON', house_model_id: 4, house_model_name: 'Modelo Norte', expected_quantity: '10', accepted_quantity: '10', pending_quantity: '0', status: 'complete' },
      { expected_item_id: 4, description: 'Adhesivo gris', unit: 'SACO', house_model_id: 4, house_model_name: 'Modelo Norte', expected_quantity: '200', accepted_quantity: '100', pending_quantity: '100', status: 'partial' },
    ],
  },
]

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('acsm_control_token', 'test-token'))
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace('/api/v1', '')
    const body = path === '/auth/me' ? user : path === '/inventory/inbound-cases' ? cases : []
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
})

test('inventory center preserves context and stays usable on desktop and mobile', async ({ page }) => {
  await page.goto('/inventory')
  await expect(page.getByRole('heading', { name: 'Centro de Inventarios' })).toBeVisible()
  await expect(page.getByText('OC-202607-0091').first()).toBeVisible()
  await expect(page.getByText('Material esperado')).toBeVisible()
  await expect(page.getByText('100 SACO').first()).toBeVisible()
  await page.screenshot({ path: 'test-results/inventory-center-desktop.png', fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Centro de Inventarios' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  await page.screenshot({ path: 'test-results/inventory-center-mobile.png', fullPage: true })

  await page.getByRole('button', { name: /Continuar recepcion/ }).first().click()
  await expect(page).toHaveURL(/project_id=7.*purchase_order_id=91.*warehouse_id=3/)
})
