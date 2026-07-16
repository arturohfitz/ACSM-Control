import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Check,
  Plus,
  RefreshCw,
  Search,
  Warehouse,
} from 'lucide-react'

import FormDrawer from '../components/FormDrawer'
import { apiRequest } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'

type Client = {
  id: number
  name: string
}

type Project = {
  id: number
  client_id: number
  name: string
  location?: string | null
  status: string
}

type HouseModel = {
  id: number
  client_id: number
  name: string
  construction_m2: string | number
}

type ProjectHouseModel = {
  id: number
  project_id: number
  house_model_id: number
  quantity: string | number
}

type ProjectSummary = {
  project: Project
  assigned_models: ProjectHouseModel[]
}

type Supplier = {
  id: number
  name: string
  status: string
}

type MaterialModelCatalogItem = {
  id: number
  project_id: number
  project_name: string
  client_id: number
  client_name: string
  house_model_id: number
  house_model_name: string
  material_id?: number | null
  material_name: string
  source_code?: string | null
  family?: string | null
  unit: string
  quantity_per_house: string | number
  assigned_houses: string | number
  total_required: string | number
  unit_cost_reference?: string | number | null
  total_cost_reference?: string | number | null
  catalog_unit_price?: string | number | null
  supplier_name?: string | null
  validation_status: string
  is_linked: boolean
}

type MaterialForm = {
  name: string
  unit: string
  current_unit_price: string
  supplier_id: string
  quantity_per_house: string
  conversion_unit: string
  conversion_factor: string
  conversion_notes: string
  source_code: string
  family: string
  last_price_update: string
  notes: string
  is_active: boolean
}

const emptyMaterialForm: MaterialForm = {
  name: '',
  unit: '',
  current_unit_price: '',
  supplier_id: '',
  quantity_per_house: '',
  conversion_unit: '',
  conversion_factor: '',
  conversion_notes: '',
  source_code: '',
  family: '',
  last_price_update: '',
  notes: '',
  is_active: true,
}

function formatNumber(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === '') return '-'
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: digits }).format(Number(value))
}

function formatCurrency(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '-'
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 2,
  }).format(Number(value))
}

export default function MaterialsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [models, setModels] = useState<HouseModel[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [summary, setSummary] = useState<ProjectSummary | null>(null)
  const [items, setItems] = useState<MaterialModelCatalogItem[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [form, setForm] = useState<MaterialForm>(emptyMaterialForm)

  const clientById = useMemo(() => new Map(clients.map((client) => [client.id, client])), [clients])
  const modelById = useMemo(() => new Map(models.map((model) => [model.id, model])), [models])

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )
  const selectedClient = selectedProject ? clientById.get(selectedProject.client_id) ?? null : null
  const assignedModels = useMemo(
    () =>
      (summary?.assigned_models ?? [])
        .map((assignment) => ({
          assignment,
          model: modelById.get(assignment.house_model_id) ?? null,
        }))
        .filter((item) => item.model),
    [modelById, summary],
  )
  const selectedAssignment = useMemo(
    () =>
      (summary?.assigned_models ?? []).find(
        (assignment) => assignment.house_model_id === selectedModelId,
      ) ?? null,
    [selectedModelId, summary],
  )
  const selectedModel = selectedModelId ? modelById.get(selectedModelId) ?? null : null
  const linkedCount = useMemo(() => items.filter((item) => item.is_linked).length, [items])
  const activeSuppliers = useMemo(
    () =>
      suppliers
        .filter((supplier) => supplier.status === 'active')
        .sort((left, right) => left.name.localeCompare(right.name, 'es', { sensitivity: 'base' })),
    [suppliers],
  )
  const canCreateMaterial = Boolean(selectedProjectId && selectedModelId && activeSuppliers.length > 0)

  async function loadBaseData(nextProjectId = selectedProjectId) {
    setLoading(true)
    setError('')
    try {
      const [clientData, projectData, modelData, supplierData] = await Promise.all([
        apiRequest<Client[]>('/clients'),
        apiRequest<Project[]>('/projects'),
        apiRequest<HouseModel[]>('/house-models'),
        apiRequest<Supplier[]>('/purchasing/suppliers?limit=1000'),
      ])
      setClients(clientData)
      setProjects(projectData)
      setModels(modelData)
      setSuppliers(supplierData)
      setSelectedProjectId(nextProjectId ?? projectData[0]?.id ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar el catalogo')
    } finally {
      setLoading(false)
    }
  }

  async function loadSummary(projectId: number | null) {
    if (!projectId) {
      setSummary(null)
      setSelectedModelId(null)
      return
    }
    try {
      const data = await apiRequest<ProjectSummary>(`/projects/${projectId}/summary`)
      setSummary(data)
      setSelectedModelId((current) => {
        if (current && data.assigned_models.some((item) => item.house_model_id === current)) {
          return current
        }
        return data.assigned_models[0]?.house_model_id ?? null
      })
    } catch (err) {
      setSummary(null)
      setSelectedModelId(null)
      setError(err instanceof Error ? err.message : 'No fue posible cargar modelos del desarrollo')
    }
  }

  async function loadCatalog(projectId: number | null, modelId: number | null, search = query) {
    if (!projectId || !modelId) {
      setItems([])
      return
    }
    setCatalogLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({
        project_id: String(projectId),
        house_model_id: String(modelId),
        limit: '1000',
      })
      if (search.trim()) params.set('q', search.trim())
      setItems(await apiRequest<MaterialModelCatalogItem[]>(`/materials/model-catalog?${params}`))
    } catch (err) {
      setItems([])
      setError(err instanceof Error ? err.message : 'No fue posible cargar materiales del modelo')
    } finally {
      setCatalogLoading(false)
    }
  }

  useEffect(() => {
    void loadBaseData()
  }, [])

  useEffect(() => {
    void loadSummary(selectedProjectId)
  }, [selectedProjectId])

  useEffect(() => {
    void loadCatalog(selectedProjectId, selectedModelId)
  }, [selectedProjectId, selectedModelId])

  function startCreate() {
    if (!selectedProjectId || !selectedModelId) {
      showActionNotice('Selecciona un desarrollo y modelo antes de crear el material.', 'warning')
      return
    }
    if (activeSuppliers.length === 0) {
      showActionNotice('Registra primero un proveedor activo en Compras > Proveedores.', 'warning')
      return
    }
    setForm(emptyMaterialForm)
    setDrawerOpen(true)
  }

  function closeDrawer() {
    if (saving) return
    setDrawerOpen(false)
    setForm(emptyMaterialForm)
  }

  async function submitMaterial(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (!selectedProjectId || !selectedModelId) {
        throw new Error('Selecciona desarrollo y modelo de casa.')
      }
      if (!form.supplier_id) {
        throw new Error('Selecciona un proveedor registrado.')
      }
      if ((form.conversion_unit.trim() && !form.conversion_factor) || (!form.conversion_unit.trim() && form.conversion_factor)) {
        throw new Error('Captura unidad de compra y factor para registrar la equivalencia.')
      }
      const created = await apiRequest<MaterialModelCatalogItem>('/materials/model-catalog', {
        method: 'POST',
        body: JSON.stringify({
          project_id: selectedProjectId,
          house_model_id: selectedModelId,
          supplier_id: Number(form.supplier_id),
          name: form.name.trim(),
          unit: form.unit.trim(),
          current_unit_price: Number(form.current_unit_price || 0),
          quantity_per_house: Number(form.quantity_per_house || 0),
          source_code: form.source_code.trim() || null,
          family: form.family.trim() || null,
          last_price_update: form.last_price_update || null,
          notes: form.notes.trim() || null,
          is_active: form.is_active,
        }),
      })
      if (created.material_id && form.conversion_unit.trim() && form.conversion_factor) {
        await apiRequest(`/materials/${created.material_id}/unit-conversions`, {
          method: 'POST',
          body: JSON.stringify({
            from_unit: form.conversion_unit.trim(),
            to_unit: form.unit.trim(),
            factor_to_base: Number(form.conversion_factor),
            notes: form.conversion_notes.trim() || null,
            is_active: true,
          }),
        })
      }
      showActionNotice('Material ligado al modelo correctamente')
      closeDrawer()
      await loadCatalog(selectedProjectId, selectedModelId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar el material')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={startCreate}
          disabled={!canCreateMaterial}
          className="inline-flex h-11 items-center gap-2 rounded-xl bg-[linear-gradient(180deg,#1f7fc4_0%,#0f609c_100%)] px-4 text-sm font-bold text-white shadow-[0_12px_26px_rgba(10,96,160,0.28)] hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Nuevo material
        </button>
        <button
          type="button"
          onClick={() => {
            void loadBaseData(selectedProjectId)
            void loadCatalog(selectedProjectId, selectedModelId)
          }}
          className="inline-flex h-10 items-center gap-2 rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-sky-50"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Actualizar
        </button>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-[24px] border border-sky-200/80 bg-[linear-gradient(180deg,#f8fcff_0%,#dcecf7_100%)] shadow-panel">
          <div className="flex items-center gap-3 border-b border-sky-200/80 px-4 py-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-sky-200 bg-sky-50 text-sky-700">
              <Warehouse className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h2 className="text-base font-bold text-acsm-ink">Seleccionar desarrollo</h2>
              <p className="truncate text-sm text-acsm-muted">{projects.length} desarrollos</p>
            </div>
          </div>
          <div className="max-h-[68vh] space-y-3 overflow-y-auto p-3">
            {loading ? (
              <div className="rounded-2xl border border-sky-200 bg-white px-4 py-5 text-sm font-semibold text-acsm-muted">
                Cargando...
              </div>
            ) : null}
            {!loading && projects.length === 0 ? (
              <div className="rounded-2xl border border-sky-200 bg-white px-4 py-5 text-sm font-semibold text-acsm-muted">
                Sin desarrollos registrados.
              </div>
            ) : null}
            {projects.map((project) => {
              const active = project.id === selectedProjectId
              const client = clientById.get(project.client_id)
              return (
                <button
                  type="button"
                  key={project.id}
                  onClick={() => setSelectedProjectId(project.id)}
                  className={[
                    'w-full rounded-2xl border px-4 py-3 text-left transition',
                    active
                      ? 'border-sky-400 bg-white shadow-[inset_4px_0_0_#1283c7,0_14px_28px_rgba(8,80,130,0.12)]'
                      : 'border-sky-100 bg-white/72 hover:border-sky-300 hover:bg-white',
                  ].join(' ')}
                >
                  <span className="block truncate text-sm font-bold text-acsm-ink">
                    {project.name}
                  </span>
                  <span className="mt-1 block truncate text-xs font-semibold text-acsm-muted">
                    {client?.name ?? 'Sin inmobiliaria'}
                  </span>
                </button>
              )
            })}
          </div>
        </aside>

        <div className="space-y-4">
          <section className="overflow-hidden rounded-[24px] border border-sky-200/80 bg-[linear-gradient(180deg,#f8fcff_0%,#e3f0f8_100%)] shadow-panel">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-sky-200/80 px-4 py-4">
              <div className="min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-acsm-muted">
                  Catalogo por modelo
                </p>
                <h2 className="mt-1 text-xl font-bold text-acsm-ink">
                  {selectedProject?.name ?? 'Selecciona un desarrollo'}
                </h2>
                <p className="mt-1 text-sm text-acsm-muted">
                  {selectedClient?.name ?? 'Sin inmobiliaria seleccionada'}
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-2xl border border-sky-200 bg-white/72 px-3 py-2">
                  <div className="text-[11px] font-bold uppercase text-acsm-muted">Modelos</div>
                  <div className="text-lg font-bold text-acsm-ink">{assignedModels.length}</div>
                </div>
                <div className="rounded-2xl border border-sky-200 bg-white/72 px-3 py-2">
                  <div className="text-[11px] font-bold uppercase text-acsm-muted">Partidas</div>
                  <div className="text-lg font-bold text-acsm-ink">{items.length}</div>
                </div>
                <div className="rounded-2xl border border-sky-200 bg-white/72 px-3 py-2">
                  <div className="text-[11px] font-bold uppercase text-acsm-muted">Vinculadas</div>
                  <div className="text-lg font-bold text-acsm-ink">{linkedCount}</div>
                </div>
              </div>
            </div>

            <div className="grid gap-3 border-b border-sky-200/80 p-4 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div>
                <label className="mb-2 block text-sm font-bold text-acsm-ink" htmlFor="model-select">
                  Modelo de casa
                </label>
                <select
                  id="model-select"
                  value={selectedModelId ?? ''}
                  onChange={(event) => setSelectedModelId(Number(event.target.value) || null)}
                  className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold text-acsm-ink outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                  disabled={!selectedProject || assignedModels.length === 0}
                >
                  {assignedModels.length === 0 ? <option value="">Sin modelos asignados</option> : null}
                  {assignedModels.map(({ assignment, model }) => (
                    <option key={assignment.id} value={assignment.house_model_id}>
                      {model?.name} - {formatNumber(assignment.quantity, 0)} viviendas
                    </option>
                  ))}
                </select>
              </div>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  void loadCatalog(selectedProjectId, selectedModelId, query)
                }}
              >
                <label className="mb-2 block text-sm font-bold text-acsm-ink" htmlFor="material-search">
                  Buscar
                </label>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-acsm-muted" />
                  <input
                    id="material-search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    className="h-11 w-full rounded-xl border border-sky-200 bg-white pl-10 pr-3 text-sm font-semibold text-acsm-ink outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                    placeholder="Codigo, material o familia"
                  />
                </div>
              </form>
            </div>

            <div className="grid gap-3 border-b border-sky-200/80 p-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-sky-200 bg-white/72 px-4 py-3">
                <div className="text-[11px] font-bold uppercase text-acsm-muted">Modelo</div>
                <div className="mt-1 truncate text-sm font-bold text-acsm-ink">
                  {selectedModel?.name ?? '-'}
                </div>
              </div>
              <div className="rounded-2xl border border-sky-200 bg-white/72 px-4 py-3">
                <div className="text-[11px] font-bold uppercase text-acsm-muted">Viviendas</div>
                <div className="mt-1 text-sm font-bold text-acsm-ink">
                  {formatNumber(selectedAssignment?.quantity, 0)}
                </div>
              </div>
              <div className="rounded-2xl border border-sky-200 bg-white/72 px-4 py-3">
                <div className="text-[11px] font-bold uppercase text-acsm-muted">M2 modelo</div>
                <div className="mt-1 text-sm font-bold text-acsm-ink">
                  {formatNumber(selectedModel?.construction_m2, 2)}
                </div>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[1080px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-sky-200 bg-sky-100/70 text-left text-xs uppercase text-acsm-muted">
                    <th className="px-4 py-3">Codigo</th>
                    <th className="px-4 py-3">Material</th>
                    <th className="px-4 py-3">Familia</th>
                    <th className="px-4 py-3">Unidad</th>
                    <th className="px-4 py-3">Cant. vivienda</th>
                    <th className="px-4 py-3">Viviendas</th>
                    <th className="px-4 py-3">Total requerido</th>
                    <th className="px-4 py-3">Precio catalogo</th>
                    <th className="px-4 py-3">Proveedor</th>
                    <th className="px-4 py-3">Relacion</th>
                  </tr>
                </thead>
                <tbody>
                  {catalogLoading ? (
                    <tr>
                      <td className="px-4 py-10 text-center text-sm font-semibold text-acsm-muted" colSpan={10}>
                        Cargando materiales...
                      </td>
                    </tr>
                  ) : null}
                  {!catalogLoading && items.length === 0 ? (
                    <tr>
                      <td className="px-4 py-10 text-center text-sm font-semibold text-acsm-muted" colSpan={10}>
                        Sin materiales para el desarrollo y modelo seleccionados.
                      </td>
                    </tr>
                  ) : null}
                  {!catalogLoading
                    ? items.map((item) => (
                        <tr key={item.id} className="border-b border-sky-100 bg-white/70">
                          <td className="px-4 py-3 font-semibold text-acsm-muted">
                            {item.source_code ?? '-'}
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-bold text-acsm-ink">{item.material_name}</div>
                            <div className="text-xs text-acsm-muted">
                              {item.client_name} / {item.project_name} / {item.house_model_name}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-acsm-muted">{item.family ?? '-'}</td>
                          <td className="px-4 py-3 font-semibold text-acsm-ink">{item.unit}</td>
                          <td className="px-4 py-3 font-semibold text-acsm-ink">
                            {formatNumber(item.quantity_per_house, 4)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-acsm-ink">
                            {formatNumber(item.assigned_houses, 0)}
                          </td>
                          <td className="px-4 py-3 font-bold text-acsm-ink">
                            {formatNumber(item.total_required, 4)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-acsm-ink">
                            {formatCurrency(item.catalog_unit_price ?? item.unit_cost_reference)}
                          </td>
                          <td className="px-4 py-3 text-acsm-muted">{item.supplier_name ?? '-'}</td>
                          <td className="px-4 py-3">
                            <span
                              className={[
                                'inline-flex rounded-full border px-2.5 py-1 text-xs font-bold',
                                item.is_linked
                                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                  : 'border-amber-200 bg-amber-50 text-amber-800',
                              ].join(' ')}
                            >
                              {item.is_linked ? 'Vinculado' : 'Pendiente'}
                            </span>
                          </td>
                        </tr>
                      ))
                    : null}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>

      <FormDrawer
        open={drawerOpen}
        title="Nuevo material"
        description="Alta ligada al desarrollo, modelo y proveedor registrado."
        onClose={closeDrawer}
        footer={
          <button
            type="submit"
            form="material-form"
            disabled={saving}
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-[linear-gradient(180deg,#1f7fc4_0%,#0f609c_100%)] px-4 text-sm font-bold text-white shadow-[0_12px_24px_rgba(10,96,160,0.24)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Check className="h-4 w-4" aria-hidden="true" />
            {saving ? 'Guardando...' : 'Guardar material'}
          </button>
        }
      >
        <form id="material-form" onSubmit={submitMaterial} className="space-y-4">
          <div className="grid gap-3 rounded-2xl border border-sky-200 bg-sky-50/70 p-3 sm:grid-cols-2">
            <div>
              <div className="text-[11px] font-bold uppercase text-acsm-muted">Desarrollo</div>
              <div className="mt-1 truncate text-sm font-bold text-acsm-ink">
                {selectedProject?.name ?? '-'}
              </div>
              <div className="truncate text-xs font-semibold text-acsm-muted">
                {selectedClient?.name ?? 'Sin inmobiliaria'}
              </div>
            </div>
            <div>
              <div className="text-[11px] font-bold uppercase text-acsm-muted">Modelo</div>
              <div className="mt-1 truncate text-sm font-bold text-acsm-ink">
                {selectedModel?.name ?? '-'}
              </div>
              <div className="truncate text-xs font-semibold text-acsm-muted">
                {formatNumber(selectedAssignment?.quantity, 0)} viviendas
              </div>
            </div>
          </div>
          <label className="block">
            <span className="mb-2 block text-sm font-bold text-acsm-ink">Nombre</span>
            <input
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
              required
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-bold text-acsm-ink">Codigo</span>
              <input
                value={form.source_code}
                onChange={(event) =>
                  setForm((current) => ({ ...current, source_code: event.target.value }))
                }
                className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                placeholder="Opcional"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-bold text-acsm-ink">Familia</span>
              <input
                value={form.family}
                onChange={(event) =>
                  setForm((current) => ({ ...current, family: event.target.value }))
                }
                className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                placeholder="Opcional"
              />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-bold text-acsm-ink">Unidad</span>
              <input
                value={form.unit}
                onChange={(event) => setForm((current) => ({ ...current, unit: event.target.value }))}
                className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                required
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-bold text-acsm-ink">Cantidad por vivienda</span>
              <input
                type="number"
                step="0.0001"
                min="0.0001"
                value={form.quantity_per_house}
                onChange={(event) =>
                  setForm((current) => ({ ...current, quantity_per_house: event.target.value }))
                }
                className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                required
              />
            </label>
          </div>
          <div className="rounded-2xl border border-sky-200 bg-sky-50/60 p-3">
            <div className="mb-3">
              <div className="text-sm font-bold text-acsm-ink">Equivalencia de compra opcional</div>
              <p className="mt-1 text-xs font-semibold text-acsm-muted">
                Usala cuando el proveedor venda en otra unidad. Ejemplo: 1 BULTO equivale a 0.05 TON.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm font-bold text-acsm-ink">Unidad de compra</span>
                <input
                  value={form.conversion_unit}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, conversion_unit: event.target.value }))
                  }
                  className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold uppercase outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                  placeholder="BULTO, ROLLO, CAJA"
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-sm font-bold text-acsm-ink">
                  Factor a unidad base
                </span>
                <input
                  type="number"
                  step="0.00000001"
                  min="0.00000001"
                  value={form.conversion_factor}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, conversion_factor: event.target.value }))
                  }
                  className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                  placeholder="0.05"
                />
              </label>
            </div>
            <label className="mt-3 block">
              <span className="mb-2 block text-sm font-bold text-acsm-ink">Notas de equivalencia</span>
              <input
                value={form.conversion_notes}
                onChange={(event) =>
                  setForm((current) => ({ ...current, conversion_notes: event.target.value }))
                }
                className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                placeholder="Ej. bulto de 50 kg"
              />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-bold text-acsm-ink">Precio unitario</span>
              <input
                type="number"
                step="0.0001"
                value={form.current_unit_price}
                onChange={(event) =>
                  setForm((current) => ({ ...current, current_unit_price: event.target.value }))
                }
                className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
                required
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-bold text-acsm-ink">Fecha precio</span>
              <input
                type="date"
                value={form.last_price_update}
                onChange={(event) =>
                  setForm((current) => ({ ...current, last_price_update: event.target.value }))
                }
                className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
              />
            </label>
          </div>
          <label className="block">
            <span className="mb-2 block text-sm font-bold text-acsm-ink">Proveedor</span>
            <select
              value={form.supplier_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, supplier_id: event.target.value }))
              }
              className="h-11 w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
              required
            >
              <option value="">Seleccionar proveedor registrado</option>
              {activeSuppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-bold text-acsm-ink">Notas</span>
            <textarea
              value={form.notes}
              onChange={(event) =>
                setForm((current) => ({ ...current, notes: event.target.value }))
              }
              className="min-h-24 w-full rounded-xl border border-sky-200 bg-white px-3 py-3 text-sm font-semibold outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
              placeholder="Opcional"
            />
          </label>
          <label className="flex items-center gap-2 rounded-xl border border-sky-200 bg-white px-3 py-3 text-sm font-bold text-acsm-ink">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) =>
                setForm((current) => ({ ...current, is_active: event.target.checked }))
              }
              className="h-4 w-4 rounded border-sky-200 accent-sky-600"
            />
            Activo
          </label>
        </form>
      </FormDrawer>
    </div>
  )
}
