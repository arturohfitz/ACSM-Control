import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Check, Link2, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'

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
  description?: string | null
  location?: string | null
  status: string
  start_date?: string | null
  estimated_end_date?: string | null
}

type HouseModel = {
  id: number
  client_id: number
  name: string
  description?: string | null
  construction_m2: string | number
  levels?: number | null
  bedrooms?: number | null
  bathrooms?: string | number | null
}

type ProjectHouseModel = {
  id: number
  project_id: number
  house_model_id: number
  quantity: string | number
  estimated_cost_per_unit?: string | number | null
  estimated_price_per_unit?: string | number | null
  total_estimated_cost?: string | number | null
  total_estimated_price?: string | number | null
}

type ProjectSummary = {
  project: Project
  assigned_models: ProjectHouseModel[]
  quote_count: number
  approved_quote_id?: number | null
  total_estimated_cost: string | number
  total_estimated_price: string | number
}

type ProjectForm = {
  client_id: string
  name: string
  description: string
  location: string
  status: string
  start_date: string
  estimated_end_date: string
}

const emptyProjectForm: ProjectForm = {
  client_id: '',
  name: '',
  description: '',
  location: '',
  status: 'draft',
  start_date: '',
  estimated_end_date: '',
}

const statusOptions = [
  { label: 'Borrador', value: 'draft' },
  { label: 'Cotizado', value: 'quoted' },
  { label: 'Aprobado', value: 'approved' },
  { label: 'En obra', value: 'in_execution' },
  { label: 'Pausado', value: 'paused' },
  { label: 'Terminado', value: 'completed' },
  { label: 'Cancelado', value: 'cancelled' },
]

function statusLabel(status: string) {
  return statusOptions.find((option) => option.value === status)?.label ?? status
}

function formatNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '-'
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 }).format(Number(value))
}

function nullableText(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function nullableDate(value: string) {
  return value || null
}

function formFromProject(project: Project): ProjectForm {
  return {
    client_id: String(project.client_id),
    name: project.name,
    description: project.description ?? '',
    location: project.location ?? '',
    status: project.status,
    start_date: project.start_date ?? '',
    estimated_end_date: project.estimated_end_date ?? '',
  }
}

export default function ProjectsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [models, setModels] = useState<HouseModel[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [summary, setSummary] = useState<ProjectSummary | null>(null)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [form, setForm] = useState<ProjectForm>(emptyProjectForm)
  const [assignmentModelId, setAssignmentModelId] = useState('')
  const [assignmentQuantity, setAssignmentQuantity] = useState('1')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )
  const selectedClient = useMemo(
    () => clients.find((client) => client.id === selectedProject?.client_id) ?? null,
    [clients, selectedProject],
  )
  const modelById = useMemo(() => new Map(models.map((model) => [model.id, model])), [models])
  const availableModels = useMemo(() => {
    if (!selectedProject) return []
    const assigned = new Set((summary?.assigned_models ?? []).map((item) => item.house_model_id))
    return models
      .filter((model) => model.client_id === selectedProject.client_id && !assigned.has(model.id))
      .sort((left, right) => left.name.localeCompare(right.name, 'es', { sensitivity: 'base' }))
  }, [models, selectedProject, summary])
  const totalHouses = useMemo(
    () =>
      (summary?.assigned_models ?? []).reduce(
        (total, item) => total + Number(item.quantity || 0),
        0,
      ),
    [summary],
  )
  const totalM2 = useMemo(
    () =>
      (summary?.assigned_models ?? []).reduce((total, item) => {
        const model = modelById.get(item.house_model_id)
        return total + Number(item.quantity || 0) * Number(model?.construction_m2 || 0)
      }, 0),
    [modelById, summary],
  )

  async function loadData(nextProjectId = selectedProjectId) {
    setLoading(true)
    setError('')
    try {
      const [clientData, projectData, modelData] = await Promise.all([
        apiRequest<Client[]>('/clients'),
        apiRequest<Project[]>('/projects'),
        apiRequest<HouseModel[]>('/house-models'),
      ])
      setClients(clientData)
      setProjects(projectData)
      setModels(modelData)
      const nextId = nextProjectId ?? projectData[0]?.id ?? null
      setSelectedProjectId(nextId)
      if (!editingProject && projectData[0] && !form.client_id) {
        setForm((current) => ({ ...current, client_id: String(clientData[0]?.id ?? '') }))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar desarrollos')
    } finally {
      setLoading(false)
    }
  }

  async function loadSummary(projectId: number | null) {
    if (!projectId) {
      setSummary(null)
      return
    }
    try {
      setSummary(await apiRequest<ProjectSummary>(`/projects/${projectId}/summary`))
    } catch (err) {
      setSummary(null)
      setError(err instanceof Error ? err.message : 'No fue posible cargar modelos del desarrollo')
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  useEffect(() => {
    void loadSummary(selectedProjectId)
  }, [selectedProjectId])

  function startCreate() {
    setEditingProject(null)
    setForm({
      ...emptyProjectForm,
      client_id: clients[0] ? String(clients[0].id) : '',
    })
    setError('')
  }

  function startEdit(project: Project) {
    setEditingProject(project)
    setForm(formFromProject(project))
    setSelectedProjectId(project.id)
    setError('')
  }

  async function saveProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        client_id: Number(form.client_id),
        name: form.name.trim(),
        description: nullableText(form.description),
        location: nullableText(form.location),
        status: form.status,
        start_date: nullableDate(form.start_date),
        estimated_end_date: nullableDate(form.estimated_end_date),
      }
      let nextId = editingProject?.id ?? null
      if (editingProject) {
        await apiRequest(`/projects/${editingProject.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        })
        showActionNotice('Desarrollo actualizado')
      } else {
        const created = await apiRequest<Project>('/projects', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        nextId = created.id
        showActionNotice('Desarrollo creado')
      }
      setEditingProject(null)
      setForm({ ...emptyProjectForm, client_id: form.client_id })
      await loadData(nextId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar el desarrollo')
    } finally {
      setSaving(false)
    }
  }

  async function deleteProject(project: Project) {
    if (!window.confirm(`Eliminar el desarrollo ${project.name}?`)) return
    setError('')
    try {
      await apiRequest(`/projects/${project.id}`, { method: 'DELETE' })
      showActionNotice('Desarrollo eliminado')
      setEditingProject(null)
      await loadData(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible eliminar el desarrollo')
    }
  }

  async function assignModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedProject) return
    setSaving(true)
    setError('')
    try {
      await apiRequest(`/projects/${selectedProject.id}/house-models`, {
        method: 'POST',
        body: JSON.stringify({
          house_model_id: Number(assignmentModelId),
          quantity: Number(assignmentQuantity),
          estimated_cost_per_unit: null,
          estimated_price_per_unit: null,
        }),
      })
      setAssignmentModelId('')
      setAssignmentQuantity('1')
      showActionNotice('Modelo asignado al desarrollo')
      await loadSummary(selectedProject.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible asignar el modelo')
    } finally {
      setSaving(false)
    }
  }

  async function removeAssignment(assignment: ProjectHouseModel) {
    if (!selectedProject) return
    const model = modelById.get(assignment.house_model_id)
    if (!window.confirm(`Quitar ${model?.name ?? 'este modelo'} del desarrollo?`)) return
    setError('')
    try {
      await apiRequest(`/projects/${selectedProject.id}/house-models/${assignment.id}`, {
        method: 'DELETE',
      })
      showActionNotice('Modelo retirado del desarrollo')
      await loadSummary(selectedProject.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible quitar el modelo')
    }
  }

  return (
    <div className="grid gap-5 2xl:grid-cols-[380px_minmax(0,1fr)]">
      <section className="rounded-lg border border-acsm-line bg-white shadow-panel">
        <div className="flex items-center justify-between border-b border-acsm-line px-4 py-4">
          <div>
            <h2 className="text-base font-semibold text-acsm-ink">
              {editingProject ? 'Editar desarrollo' : 'Nuevo desarrollo'}
            </h2>
            <p className="text-sm text-acsm-muted">Contrato o etapa ligada a una inmobiliaria.</p>
          </div>
          {editingProject ? (
            <button
              type="button"
              onClick={startCreate}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line text-acsm-muted hover:bg-acsm-paper"
              title="Cancelar edicion"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : (
            <Plus className="h-5 w-5 text-acsm-blue" aria-hidden="true" />
          )}
        </div>

        <form onSubmit={saveProject} className="space-y-4 p-4">
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-acsm-ink">Inmobiliaria</span>
            <select
              value={form.client_id}
              onChange={(event) => setForm((current) => ({ ...current, client_id: event.target.value }))}
              required
              className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
            >
              <option value="">Seleccionar</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-acsm-ink">Nombre del desarrollo</span>
            <input
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              required
              className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-acsm-ink">Descripcion</span>
            <textarea
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
              rows={3}
              className="w-full rounded-md border border-acsm-line bg-white px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium text-acsm-ink">Ubicacion</span>
            <input
              value={form.location}
              onChange={(event) =>
                setForm((current) => ({ ...current, location: event.target.value }))
              }
              className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-1">
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-acsm-ink">Estado</span>
              <select
                value={form.status}
                onChange={(event) =>
                  setForm((current) => ({ ...current, status: event.target.value }))
                }
                className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium text-acsm-ink">Inicio</span>
              <input
                type="date"
                value={form.start_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, start_date: event.target.value }))
                }
                className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
              />
            </label>
            <label className="block text-sm sm:col-span-2 2xl:col-span-1">
              <span className="mb-1.5 block font-medium text-acsm-ink">Fin estimado</span>
              <input
                type="date"
                value={form.estimated_end_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, estimated_end_date: event.target.value }))
                }
                className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
              />
            </label>
          </div>

          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={saving}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
          >
            <Check className="h-4 w-4" aria-hidden="true" />
            {saving ? 'Guardando...' : editingProject ? 'Actualizar' : 'Crear'}
          </button>
        </form>
      </section>

      <div className="space-y-5">
        <section className="rounded-lg border border-acsm-line bg-white shadow-panel">
          <div className="flex h-14 items-center justify-between gap-3 border-b border-acsm-line px-4">
            <div>
              <h2 className="text-base font-semibold text-acsm-ink">Desarrollos</h2>
              <p className="text-xs text-acsm-muted">
                Selecciona un desarrollo para asignarle los modelos de casa que incluye.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void loadData(selectedProjectId)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line text-acsm-muted hover:bg-acsm-paper"
              title="Actualizar"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse text-sm">
              <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
                <tr>
                  <th className="border-b border-acsm-line px-4 py-3">ID</th>
                  <th className="border-b border-acsm-line px-4 py-3">Inmobiliaria</th>
                  <th className="border-b border-acsm-line px-4 py-3">Desarrollo</th>
                  <th className="border-b border-acsm-line px-4 py-3">Ubicacion</th>
                  <th className="border-b border-acsm-line px-4 py-3">Estado</th>
                  <th className="border-b border-acsm-line px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-acsm-muted">
                      Cargando...
                    </td>
                  </tr>
                ) : projects.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-acsm-muted">
                      Sin desarrollos registrados.
                    </td>
                  </tr>
                ) : (
                  projects.map((project) => {
                    const client = clients.find((item) => item.id === project.client_id)
                    const active = project.id === selectedProjectId
                    return (
                      <tr
                        key={project.id}
                        className={[
                          'cursor-pointer border-b border-acsm-line last:border-0 hover:bg-acsm-paper/70',
                          active ? 'bg-sky-50' : '',
                        ].join(' ')}
                        onClick={() => setSelectedProjectId(project.id)}
                      >
                        <td className="px-4 py-3 font-semibold text-acsm-muted">{project.id}</td>
                        <td className="px-4 py-3">{client?.name ?? '-'}</td>
                        <td className="px-4 py-3 font-semibold text-acsm-ink">{project.name}</td>
                        <td className="max-w-[260px] truncate px-4 py-3">
                          {project.location ?? '-'}
                        </td>
                        <td className="px-4 py-3">{statusLabel(project.status)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-2">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                startEdit(project)
                              }}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-acsm-line text-acsm-muted hover:bg-white"
                              title="Editar"
                            >
                              <Pencil className="h-4 w-4" aria-hidden="true" />
                            </button>
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                void deleteProject(project)
                              }}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-red-200 text-red-500 hover:bg-red-50"
                              title="Eliminar"
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-lg border border-acsm-line bg-white shadow-panel">
          <div className="border-b border-acsm-line px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-acsm-muted">
                  Desarrollo seleccionado
                </p>
                <h2 className="mt-1 text-lg font-bold text-acsm-ink">
                  {selectedProject?.name ?? 'Sin seleccion'}
                </h2>
                <p className="text-sm text-acsm-muted">
                  {selectedClient?.name ?? 'Selecciona un desarrollo para asignar modelos'}
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div className="rounded-md border border-acsm-line bg-acsm-paper px-3 py-2">
                  <span className="block text-[11px] font-bold uppercase text-acsm-muted">
                    Modelos
                  </span>
                  <span className="font-bold">{summary?.assigned_models.length ?? 0}</span>
                </div>
                <div className="rounded-md border border-acsm-line bg-acsm-paper px-3 py-2">
                  <span className="block text-[11px] font-bold uppercase text-acsm-muted">
                    Viviendas
                  </span>
                  <span className="font-bold">{formatNumber(totalHouses)}</span>
                </div>
                <div className="rounded-md border border-acsm-line bg-acsm-paper px-3 py-2">
                  <span className="block text-[11px] font-bold uppercase text-acsm-muted">
                    m2 total
                  </span>
                  <span className="font-bold">{formatNumber(totalM2)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="rounded-md border border-acsm-line">
              <div className="border-b border-acsm-line bg-acsm-paper px-4 py-3">
                <h3 className="font-semibold text-acsm-ink">Modelos asignados al desarrollo</h3>
                <p className="text-xs text-acsm-muted">
                  Estos modelos habilitan convenios, compras, inventario y tabuladores.
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-sm">
                  <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
                    <tr>
                      <th className="border-b border-acsm-line px-4 py-3">Modelo</th>
                      <th className="border-b border-acsm-line px-4 py-3">Viviendas</th>
                      <th className="border-b border-acsm-line px-4 py-3">m2 por vivienda</th>
                      <th className="border-b border-acsm-line px-4 py-3">m2 total</th>
                      <th className="border-b border-acsm-line px-4 py-3 text-right">Accion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(summary?.assigned_models ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-10 text-center text-acsm-muted">
                          Este desarrollo aun no tiene modelos asignados.
                        </td>
                      </tr>
                    ) : (
                      summary?.assigned_models.map((assignment) => {
                        const model = modelById.get(assignment.house_model_id)
                        const quantity = Number(assignment.quantity || 0)
                        const m2 = Number(model?.construction_m2 || 0)
                        return (
                          <tr key={assignment.id} className="border-b border-acsm-line last:border-0">
                            <td className="px-4 py-3">
                              <div className="font-semibold text-acsm-ink">
                                {model?.name ?? `Modelo #${assignment.house_model_id}`}
                              </div>
                              <div className="text-xs text-acsm-muted">
                                {model?.description ?? 'Sin descripcion capturada'}
                              </div>
                            </td>
                            <td className="px-4 py-3 font-semibold">{formatNumber(quantity)}</td>
                            <td className="px-4 py-3">{formatNumber(m2)}</td>
                            <td className="px-4 py-3 font-semibold">{formatNumber(quantity * m2)}</td>
                            <td className="px-4 py-3">
                              <div className="flex justify-end">
                                <button
                                  type="button"
                                  onClick={() => void removeAssignment(assignment)}
                                  className="inline-flex h-8 items-center justify-center rounded-md border border-red-200 px-3 text-xs font-bold text-red-600 hover:bg-red-50"
                                >
                                  Quitar
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <form onSubmit={assignModel} className="rounded-md border border-acsm-line bg-acsm-paper p-4">
              <div className="mb-4 flex items-start gap-2">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line bg-white text-acsm-blue">
                  <Link2 className="h-4 w-4" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-semibold text-acsm-ink">Asignar modelo existente</h3>
                  <p className="text-xs text-acsm-muted">
                    Usa los modelos creados en el menu Modelos.
                  </p>
                </div>
              </div>
              <label className="block text-sm">
                <span className="mb-1.5 block font-medium text-acsm-ink">Modelo de casa</span>
                <select
                  value={assignmentModelId}
                  onChange={(event) => setAssignmentModelId(event.target.value)}
                  required
                  disabled={!selectedProject}
                  className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
                >
                  <option value="">Seleccionar modelo</option>
                  {availableModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name} - {formatNumber(model.construction_m2)} m2
                    </option>
                  ))}
                </select>
              </label>
              <label className="mt-3 block text-sm">
                <span className="mb-1.5 block font-medium text-acsm-ink">Cantidad de viviendas</span>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={assignmentQuantity}
                  onChange={(event) => setAssignmentQuantity(event.target.value)}
                  required
                  disabled={!selectedProject}
                  className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
                />
              </label>
              {!selectedProject ? (
                <div className="mt-3 rounded-md border border-acsm-line bg-white px-3 py-2 text-xs text-acsm-muted">
                  Selecciona un desarrollo para asignar modelos.
                </div>
              ) : availableModels.length === 0 ? (
                <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  No hay modelos disponibles para esta inmobiliaria o ya estan asignados.
                </div>
              ) : null}
              <button
                type="submit"
                disabled={!selectedProject || !assignmentModelId || saving}
                className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
              >
                <Check className="h-4 w-4" aria-hidden="true" />
                Asignar modelo
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  )
}
