import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  ClipboardList,
  FileStack,
  HardHat,
  Package,
  RefreshCw,
  Send,
} from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { apiRequest } from '../lib/api'

type Project = {
  id: number
  client_id: number
  name: string
  location?: string | null
  status?: string
}

type HouseModel = {
  id: number
  name: string
}

type ProjectHouseModel = {
  id: number
  house_model_id: number
  quantity: string | number
}

type ProjectSummary = {
  project: Project
  assigned_models: ProjectHouseModel[]
}

type CatalogRow = {
  id: number
  is_linked: boolean
  validation_status: string
}

type RequisitionItem = {
  id: number
  description: string
  requested_quantity: string
  requested_unit?: string | null
  unit: string
}

type MaterialRequisition = {
  id: number
  project_id: number
  house_model_id: number
  requisition_number: string
  title: string
  status: string
  priority: string
  required_date?: string | null
  created_at: string
  items: RequisitionItem[]
}

type TrackingStep = {
  key: string
  label: string
  status: 'pending' | 'active' | 'complete' | 'blocked' | 'warning'
  detail?: string | null
}

type RequisitionTracking = {
  requisition: MaterialRequisition
  project_name?: string | null
  house_model_name?: string | null
  steps: TrackingStep[]
}

const statusLabels: Record<string, string> = {
  submitted: 'Enviado a Compras',
  in_review: 'En revision por Compras',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  converted_to_rfq: 'En cotizacion',
  ordered_to_suppliers: 'Pedido a proveedor',
  cancelled: 'Cancelado',
}

function formatDate(value?: string | null) {
  if (!value) return 'Sin fecha requerida'
  return new Intl.DateTimeFormat('es-MX', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))
}

function stepClasses(stepStatus: TrackingStep['status']) {
  if (stepStatus === 'complete') return 'border-emerald-300 bg-emerald-50 text-emerald-800'
  if (stepStatus === 'active') return 'border-sky-400 bg-sky-50 text-sky-900 shadow-sm'
  if (stepStatus === 'blocked' || stepStatus === 'warning') {
    return 'border-amber-300 bg-amber-50 text-amber-900'
  }
  return 'border-slate-200 bg-white text-slate-500'
}

export default function WorkWorkspacePage() {
  const { hasPermission } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [projects, setProjects] = useState<Project[]>([])
  const [models, setModels] = useState<HouseModel[]>([])
  const [summary, setSummary] = useState<ProjectSummary | null>(null)
  const [materials, setMaterials] = useState<CatalogRow[]>([])
  const [concepts, setConcepts] = useState<CatalogRow[]>([])
  const [requisitions, setRequisitions] = useState<MaterialRequisition[]>([])
  const [tracking, setTracking] = useState<RequisitionTracking | null>(null)
  const [loading, setLoading] = useState(true)
  const [contextLoading, setContextLoading] = useState(false)
  const [error, setError] = useState('')

  const selectedProjectId = Number(searchParams.get('project_id')) || 0
  const selectedModelId = Number(searchParams.get('house_model_id')) || 0
  const selectedRequisitionId = Number(searchParams.get('requisition_id')) || 0

  const modelById = useMemo(() => new Map(models.map((model) => [model.id, model])), [models])
  const assignedModels = useMemo(
    () =>
      (summary?.assigned_models ?? [])
        .map((assignment) => ({ assignment, model: modelById.get(assignment.house_model_id) }))
        .filter((entry): entry is { assignment: ProjectHouseModel; model: HouseModel } => Boolean(entry.model)),
    [modelById, summary],
  )
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null
  const selectedModel = modelById.get(selectedModelId) ?? null
  const selectedAssignment = summary?.assigned_models.find(
    (assignment) => assignment.house_model_id === selectedModelId,
  )
  const modelRequisitions = useMemo(
    () => requisitions.filter((item) => !selectedModelId || item.house_model_id === selectedModelId),
    [requisitions, selectedModelId],
  )

  const linkedMaterials = materials.filter((item) => item.is_linked).length
  const linkedConcepts = concepts.filter((item) => item.is_linked).length
  const pendingMaterials = materials.length - linkedMaterials
  const pendingConcepts = concepts.length - linkedConcepts
  const activeRequisitions = modelRequisitions.filter(
    (item) => !['rejected', 'cancelled', 'ordered_to_suppliers'].includes(item.status),
  ).length
  const preparationReady = materials.length > 0 && pendingMaterials === 0 && concepts.length > 0 && pendingConcepts === 0

  const contextQuery = new URLSearchParams()
  if (selectedProjectId) contextQuery.set('project_id', String(selectedProjectId))
  if (selectedModelId) contextQuery.set('house_model_id', String(selectedModelId))
  const contextSuffix = contextQuery.toString() ? `?${contextQuery.toString()}` : ''

  async function loadBaseData() {
    setLoading(true)
    setError('')
    try {
      const [projectData, modelData] = await Promise.all([
        apiRequest<Project[]>('/projects'),
        apiRequest<HouseModel[]>('/house-models'),
      ])
      setProjects(projectData)
      setModels(modelData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar el Centro de Obra')
    } finally {
      setLoading(false)
    }
  }

  async function loadProjectContext(projectId: number) {
    if (!projectId) {
      setSummary(null)
      setMaterials([])
      setConcepts([])
      setRequisitions([])
      return
    }
    setContextLoading(true)
    setError('')
    try {
      const [projectSummary, requisitionData] = await Promise.all([
        apiRequest<ProjectSummary>(`/projects/${projectId}/summary`),
        hasPermission('material_requisitions:view')
          ? apiRequest<MaterialRequisition[]>(`/material-requisitions?project_id=${projectId}&limit=250`)
          : Promise.resolve([]),
      ])
      setSummary(projectSummary)
      setRequisitions(requisitionData)

      const currentModelIsValid = projectSummary.assigned_models.some(
        (assignment) => assignment.house_model_id === selectedModelId,
      )
      if (!currentModelIsValid) {
        const next = new URLSearchParams(searchParams)
        next.delete('house_model_id')
        next.delete('requisition_id')
        if (projectSummary.assigned_models.length === 1) {
          next.set('house_model_id', String(projectSummary.assigned_models[0].house_model_id))
        }
        setSearchParams(next, { replace: true })
      }
    } catch (err) {
      setSummary(null)
      setRequisitions([])
      setError(err instanceof Error ? err.message : 'No fue posible cargar el desarrollo')
    } finally {
      setContextLoading(false)
    }
  }

  async function loadModelContext(projectId: number, modelId: number) {
    if (!projectId || !modelId) {
      setMaterials([])
      setConcepts([])
      return
    }
    setContextLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({
        project_id: String(projectId),
        house_model_id: String(modelId),
        limit: '1000',
      })
      const [materialData, conceptData] = await Promise.all([
        hasPermission('materials:view')
          ? apiRequest<CatalogRow[]>(`/materials/model-catalog?${params}`)
          : Promise.resolve([]),
        hasPermission('construction_concepts:view')
          ? apiRequest<CatalogRow[]>(`/construction-concepts/model-catalog?${params}`)
          : Promise.resolve([]),
      ])
      setMaterials(materialData)
      setConcepts(conceptData)
    } catch (err) {
      setMaterials([])
      setConcepts([])
      setError(err instanceof Error ? err.message : 'No fue posible validar la preparacion del modelo')
    } finally {
      setContextLoading(false)
    }
  }

  async function loadTracking(requisitionId: number) {
    if (!requisitionId || !hasPermission('material_requisitions:view')) {
      setTracking(null)
      return
    }
    try {
      setTracking(
        await apiRequest<RequisitionTracking>(`/material-requisitions/${requisitionId}/tracking`),
      )
    } catch (err) {
      setTracking(null)
      setError(err instanceof Error ? err.message : 'No fue posible cargar el seguimiento')
    }
  }

  useEffect(() => {
    void loadBaseData()
  }, [])

  useEffect(() => {
    void loadProjectContext(selectedProjectId)
  }, [selectedProjectId])

  useEffect(() => {
    void loadModelContext(selectedProjectId, selectedModelId)
  }, [selectedProjectId, selectedModelId])

  useEffect(() => {
    void loadTracking(selectedRequisitionId)
  }, [selectedRequisitionId])

  function selectProject(value: string) {
    const next = new URLSearchParams()
    if (value) next.set('project_id', value)
    setSearchParams(next)
  }

  function selectModel(value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set('house_model_id', value)
    else next.delete('house_model_id')
    next.delete('requisition_id')
    setSearchParams(next)
  }

  function selectRequisition(id: number) {
    const next = new URLSearchParams(searchParams)
    next.set('requisition_id', String(id))
    setSearchParams(next)
  }

  if (loading) {
    return <div className="py-20 text-center text-sm text-slate-500">Preparando Centro de Obra...</div>
  }

  return (
    <div className="space-y-5 pb-10">
      <section className="overflow-hidden rounded-lg border border-sky-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-sky-200 bg-sky-50 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-sky-200 bg-white text-sky-700">
              <HardHat className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-sky-700">Control operativo</p>
              <h1 className="mt-1 text-xl font-bold text-slate-950">Centro de Obra</h1>
              <p className="mt-1 text-sm text-slate-600">Prepara el modelo, solicita material y sigue cada requerimiento sin perder el contexto.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadProjectContext(selectedProjectId)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-sky-200 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-sky-50"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Actualizar
          </button>
        </div>

        <div className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
          <label className="block text-sm font-semibold text-slate-800">
            Desarrollo
            <select
              value={selectedProjectId || ''}
              onChange={(event) => selectProject(event.target.value)}
              className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              <option value="">Seleccionar desarrollo</option>
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </label>
          <label className="block text-sm font-semibold text-slate-800">
            Modelo del desarrollo
            <select
              value={selectedModelId || ''}
              onChange={(event) => selectModel(event.target.value)}
              disabled={!selectedProjectId || assignedModels.length === 0}
              className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm shadow-sm outline-none disabled:bg-slate-100 focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              <option value="">Seleccionar modelo</option>
              {assignedModels.map(({ assignment, model }) => (
                <option key={assignment.id} value={model.id}>{model.name} · {Number(assignment.quantity)} viviendas</option>
              ))}
            </select>
          </label>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-600 lg:min-w-48">
            <p className="text-xs font-bold uppercase text-slate-500">Contexto activo</p>
            <p className="mt-1 font-semibold text-slate-900">{selectedModel?.name ?? 'Sin seleccionar'}</p>
            <p>{selectedAssignment ? `${Number(selectedAssignment.quantity)} viviendas` : selectedProject?.location || 'Selecciona un modelo'}</p>
          </div>
        </div>
      </section>

      {error ? (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
          {error}
        </div>
      ) : null}

      {!selectedProjectId ? (
        <section className="rounded-lg border border-dashed border-sky-300 bg-sky-50 px-6 py-12 text-center">
          <Boxes className="mx-auto h-8 w-8 text-sky-600" aria-hidden="true" />
          <h2 className="mt-3 text-lg font-bold text-slate-950">Selecciona el desarrollo donde vas a trabajar</h2>
          <p className="mt-1 text-sm text-slate-600">El sistema conservara ese contexto al abrir catalogos o preparar un requerimiento.</p>
        </section>
      ) : !selectedModelId ? (
        <section className="rounded-lg border border-dashed border-amber-300 bg-amber-50 px-6 py-10 text-center">
          <FileStack className="mx-auto h-8 w-8 text-amber-700" aria-hidden="true" />
          <h2 className="mt-3 text-lg font-bold text-slate-950">Selecciona un modelo asignado</h2>
          <p className="mt-1 text-sm text-slate-600">Cada catalogo y requerimiento debe quedar ligado a un modelo y a su numero de viviendas.</p>
        </section>
      ) : (
        <>
          <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Paso 1 · Preparacion</p>
                <h2 className="mt-1 text-lg font-bold text-slate-950">Validar informacion base del modelo</h2>
              </div>
              <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-bold ${preparationReady ? 'border-emerald-300 bg-emerald-50 text-emerald-800' : 'border-amber-300 bg-amber-50 text-amber-800'}`}>
                {preparationReady ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                {preparationReady ? 'Modelo listo para operar' : 'Requiere revision'}
              </span>
            </div>
            <div className="grid divide-y divide-slate-200 md:grid-cols-3 md:divide-x md:divide-y-0">
              <Link to={`/materials${contextSuffix}`} className="group flex min-h-32 items-center gap-4 p-5 hover:bg-sky-50">
                <Package className="h-7 w-7 shrink-0 text-sky-700" />
                <div className="min-w-0 flex-1">
                  <p className="font-bold text-slate-950">Catalogo de materiales</p>
                  <p className="mt-1 text-sm text-slate-600">{materials.length} partidas · {pendingMaterials} pendientes de vincular</p>
                </div>
                <ChevronRight className="h-5 w-5 text-slate-400 group-hover:text-sky-700" />
              </Link>
              <Link to={`/construction-concepts${contextSuffix}`} className="group flex min-h-32 items-center gap-4 p-5 hover:bg-sky-50">
                <ClipboardCheck className="h-7 w-7 shrink-0 text-sky-700" />
                <div className="min-w-0 flex-1">
                  <p className="font-bold text-slate-950">Conceptos y presupuesto</p>
                  <p className="mt-1 text-sm text-slate-600">{concepts.length} actividades · {pendingConcepts} pendientes de vincular</p>
                </div>
                <ChevronRight className="h-5 w-5 text-slate-400 group-hover:text-sky-700" />
              </Link>
              <div className="flex min-h-32 items-center gap-4 p-5">
                <FileStack className="h-7 w-7 shrink-0 text-sky-700" />
                <div>
                  <p className="font-bold text-slate-950">Alcance del proyecto</p>
                  <p className="mt-1 text-sm text-slate-600">{Number(selectedAssignment?.quantity ?? 0)} viviendas asignadas a {selectedModel?.name}</p>
                </div>
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Paso 2 · Solicitud</p>
                <h2 className="mt-1 text-lg font-bold text-slate-950">Requerir material a Compras</h2>
                <p className="mt-1 text-sm text-slate-600">El saldo disponible ya descuenta lo solicitado anteriormente para este modelo.</p>
              </div>
              {hasPermission('material_requisitions:create') ? (
                <Link to={`/field-requisitions${contextSuffix}`} className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-sky-700 px-5 text-sm font-bold text-white shadow-sm hover:bg-sky-800">
                  <Send className="h-4 w-4" aria-hidden="true" />
                  Preparar requerimiento
                </Link>
              ) : null}
            </div>
            <div className="grid gap-0 md:grid-cols-3">
              <div className="border-b border-slate-200 p-5 md:border-b-0 md:border-r">
                <p className="text-xs font-bold uppercase text-slate-500">Requerimientos activos</p>
                <p className="mt-2 text-3xl font-bold text-slate-950">{activeRequisitions}</p>
              </div>
              <div className="border-b border-slate-200 p-5 md:border-b-0 md:border-r">
                <p className="text-xs font-bold uppercase text-slate-500">Partidas del modelo</p>
                <p className="mt-2 text-3xl font-bold text-slate-950">{materials.length}</p>
              </div>
              <div className="p-5">
                <p className="text-xs font-bold uppercase text-slate-500">Regla activa</p>
                <p className="mt-2 font-bold text-slate-950">No exceder explosion disponible</p>
                <p className="mt-1 text-sm text-slate-600">La API valida cantidad y conversion de unidad.</p>
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 py-4">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Paso 3 · Seguimiento</p>
              <h2 className="mt-1 text-lg font-bold text-slate-950">Que esta pasando con cada requerimiento</h2>
              <p className="mt-1 text-sm text-slate-600">Selecciona un folio para ver su etapa actual y el siguiente responsable.</p>
            </div>
            <div className="grid min-h-72 lg:grid-cols-[minmax(280px,0.38fr)_minmax(0,1fr)]">
              <div className="border-b border-slate-200 lg:border-b-0 lg:border-r">
                {modelRequisitions.map((requisition) => (
                  <button
                    key={requisition.id}
                    type="button"
                    onClick={() => selectRequisition(requisition.id)}
                    className={`flex w-full items-center gap-3 border-b border-slate-100 px-5 py-4 text-left hover:bg-sky-50 ${selectedRequisitionId === requisition.id ? 'bg-sky-50 ring-1 ring-inset ring-sky-300' : ''}`}
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-sky-700">
                      <ClipboardList className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-bold text-slate-950">{requisition.title}</span>
                      <span className="mt-1 block text-xs text-slate-500">{requisition.requisition_number} · {requisition.items.length} partidas</span>
                      <span className="mt-1 block text-xs font-semibold text-sky-700">{statusLabels[requisition.status] ?? requisition.status}</span>
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
                  </button>
                ))}
                {!modelRequisitions.length ? (
                  <div className="px-5 py-10 text-center text-sm text-slate-500">Aun no hay requerimientos para este modelo.</div>
                ) : null}
              </div>

              <div className="p-5">
                {tracking ? (
                  <>
                    <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-xs font-bold uppercase text-sky-700">{tracking.requisition.requisition_number}</p>
                        <h3 className="mt-1 text-lg font-bold text-slate-950">{tracking.requisition.title}</h3>
                        <p className="mt-1 text-sm text-slate-600">{formatDate(tracking.requisition.required_date)} · {tracking.requisition.items.length} partidas</p>
                      </div>
                      <Link to={`/field-requisitions${contextSuffix}&requisition_id=${tracking.requisition.id}`} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-sky-300 px-4 text-sm font-bold text-sky-800 hover:bg-sky-50">
                        Ver detalle <ArrowRight className="h-4 w-4" />
                      </Link>
                    </div>
                    <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                      {tracking.steps.map((step, index) => (
                        <div key={step.key} className={`rounded-lg border px-3 py-3 ${stepClasses(step.status)}`}>
                          <p className="text-xs font-bold uppercase">{String(index + 1).padStart(2, '0')} · {step.label}</p>
                          <p className="mt-1 text-xs leading-5">{step.detail || (step.status === 'pending' ? 'Pendiente' : 'Completado')}</p>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="flex min-h-56 flex-col items-center justify-center text-center">
                    <ClipboardList className="h-8 w-8 text-slate-300" />
                    <p className="mt-3 font-bold text-slate-700">Selecciona un requerimiento</p>
                    <p className="mt-1 max-w-sm text-sm text-slate-500">Aqui veras su recorrido desde Obra hasta la recepcion del material.</p>
                  </div>
                )}
              </div>
            </div>
          </section>
        </>
      )}

      {contextLoading ? <p className="text-center text-xs font-semibold text-slate-500">Actualizando contexto operativo...</p> : null}
    </div>
  )
}
