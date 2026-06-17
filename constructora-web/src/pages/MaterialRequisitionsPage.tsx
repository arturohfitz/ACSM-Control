import { useEffect, useMemo, useState } from 'react'
import {
  Check,
  ClipboardList,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Send,
  Trash2,
  X,
} from 'lucide-react'

import { apiRequest } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'

type PageMode = 'field' | 'purchasing'

type Project = {
  id: number
  client_id: number
  name: string
  status?: string
}

type Supplier = {
  id: number
  name: string
  payment_terms_days?: number | null
  average_delivery_days?: number | null
}

type UserSummary = {
  id: number
  full_name: string
  email: string
}

type AvailableRequirement = {
  id: number
  house_model_id: number
  house_model_name: string
  material_id?: number | null
  source_code?: string | null
  description: string
  unit: string
  quantity_per_house: string
  assigned_houses: string
  total_required: string
  validation_status: string
  family?: string | null
}

type RequisitionItem = {
  id: number
  house_model_material_requirement_id?: number | null
  material_id?: number | null
  supplier_rfq_item_id?: number | null
  source_code?: string | null
  description: string
  unit: string
  requested_quantity: string
  approved_quantity?: string | null
  status: string
  notes?: string | null
}

type MaterialRequisition = {
  id: number
  client_id: number
  project_id: number
  house_model_id: number
  requested_by_user_id?: number | null
  reviewed_by_user_id?: number | null
  converted_rfq_id?: number | null
  requisition_number: string
  title: string
  status: string
  priority: string
  required_date?: string | null
  submitted_at?: string | null
  reviewed_at?: string | null
  notes?: string | null
  review_notes?: string | null
  requested_by?: UserSummary | null
  reviewed_by?: UserSummary | null
  items: RequisitionItem[]
  created_at: string
  updated_at: string
}

type DraftItem = {
  requirement: AvailableRequirement
  quantity: string
  notes: string
}

const statusLabels: Record<string, string> = {
  submitted: 'Pendiente',
  in_review: 'En revision',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  converted_to_rfq: 'Convertido a cotizacion',
  cancelled: 'Cancelado',
}

const purchasingActiveStatuses = new Set(['submitted', 'in_review', 'approved'])

const priorityLabels: Record<string, string> = {
  low: 'Baja',
  normal: 'Normal',
  high: 'Alta',
  urgent: 'Urgente',
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('es-MX', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))
}

function formatNumber(value?: string | number | null) {
  if (value === undefined || value === null || value === '') return '-'
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return String(value)
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 }).format(numberValue)
}

function statusClass(status: string) {
  if (status === 'approved' || status === 'converted_to_rfq') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  }
  if (status === 'rejected' || status === 'cancelled') {
    return 'border-rose-200 bg-rose-50 text-rose-700'
  }
  if (status === 'in_review') {
    return 'border-amber-200 bg-amber-50 text-amber-800'
  }
  return 'border-sky-200 bg-sky-50 text-sky-800'
}

export default function MaterialRequisitionsPage({ mode }: { mode: PageMode }) {
  const isPurchasing = mode === 'purchasing'
  const [projects, setProjects] = useState<Project[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [projectId, setProjectId] = useState('')
  const [houseModelId, setHouseModelId] = useState('')
  const [materialSearch, setMaterialSearch] = useState('')
  const [availableMaterials, setAvailableMaterials] = useState<AvailableRequirement[]>([])
  const [draftItems, setDraftItems] = useState<DraftItem[]>([])
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState('normal')
  const [requiredDate, setRequiredDate] = useState('')
  const [notes, setNotes] = useState('')
  const [requisitions, setRequisitions] = useState<MaterialRequisition[]>([])
  const [selectedRequisitionId, setSelectedRequisitionId] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState(isPurchasing ? 'active' : '')
  const [requisitionSearch, setRequisitionSearch] = useState('')
  const [reviewNotes, setReviewNotes] = useState('')
  const [selectedSupplierIds, setSelectedSupplierIds] = useState<number[]>([])
  const [rfqDeadline, setRfqDeadline] = useState('')
  const [loading, setLoading] = useState(false)

  const selectedProject = useMemo(
    () => projects.find((project) => String(project.id) === projectId) ?? null,
    [projectId, projects],
  )

  const modelOptions = useMemo(() => {
    const byId = new Map<number, string>()
    for (const item of availableMaterials) {
      byId.set(item.house_model_id, item.house_model_name)
    }
    return [...byId.entries()].map(([id, name]) => ({ id, name }))
  }, [availableMaterials])

  const selectedRequisition = useMemo(
    () => requisitions.find((item) => item.id === selectedRequisitionId) ?? requisitions[0] ?? null,
    [requisitions, selectedRequisitionId],
  )

  const filteredAvailableMaterials = useMemo(() => {
    const normalized = materialSearch.trim().toLowerCase()
    return availableMaterials
      .filter((item) => !houseModelId || item.house_model_id === Number(houseModelId))
      .filter((item) => {
        if (!normalized) return true
        return [item.description, item.source_code ?? '', item.family ?? '', item.unit]
          .join(' ')
          .toLowerCase()
          .includes(normalized)
      })
      .slice(0, 80)
  }, [availableMaterials, houseModelId, materialSearch])

  async function loadBaseData() {
    setLoading(true)
    try {
      const [projectRows, supplierRows] = await Promise.all([
        apiRequest<Project[]>('/projects'),
        isPurchasing
          ? apiRequest<Supplier[]>('/purchasing/suppliers')
          : Promise.resolve([] as Supplier[]),
      ])
      setProjects(projectRows)
      setSuppliers(supplierRows)
      if (!projectId && projectRows[0]) {
        setProjectId(String(projectRows[0].id))
      }
    } catch (error) {
      showActionNotice(error instanceof Error ? error.message : 'No fue posible cargar datos base', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function loadRequisitions() {
    const params = new URLSearchParams()
    params.set('limit', '150')
    if (statusFilter && statusFilter !== 'active') params.set('status_filter', statusFilter)
    if (projectId && !isPurchasing) params.set('project_id', projectId)
    if (requisitionSearch.trim()) params.set('q', requisitionSearch.trim())
    try {
      const apiRows = await apiRequest<MaterialRequisition[]>(`/material-requisitions?${params}`)
      const rows =
        isPurchasing && statusFilter === 'active'
          ? apiRows.filter((item) => purchasingActiveStatuses.has(item.status))
          : apiRows
      setRequisitions(rows)
      if (rows.length > 0 && !rows.some((item) => item.id === selectedRequisitionId)) {
        setSelectedRequisitionId(rows[0].id)
      }
      if (rows.length === 0) {
        setSelectedRequisitionId(null)
      }
    } catch (error) {
      showActionNotice(error instanceof Error ? error.message : 'No fue posible cargar requerimientos', 'error')
    }
  }

  async function loadAvailableMaterials(nextProjectId = projectId) {
    if (!nextProjectId) {
      setAvailableMaterials([])
      return
    }
    const params = new URLSearchParams({ project_id: nextProjectId, limit: '500' })
    try {
      const rows = await apiRequest<AvailableRequirement[]>(
        `/material-requisitions/available-materials?${params}`,
      )
      setAvailableMaterials(rows)
      const firstModel = rows[0]?.house_model_id
      setHouseModelId(firstModel ? String(firstModel) : '')
    } catch (error) {
      setAvailableMaterials([])
      showActionNotice(error instanceof Error ? error.message : 'No fue posible leer la explosion del modelo', 'error')
    }
  }

  useEffect(() => {
    loadBaseData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  useEffect(() => {
    if (!projectId) return
    loadAvailableMaterials(projectId)
    if (!isPurchasing) {
      loadRequisitions()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  useEffect(() => {
    loadRequisitions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  function addDraftItem(requirement: AvailableRequirement) {
    if (draftItems.some((item) => item.requirement.id === requirement.id)) {
      showActionNotice('Ese material ya esta en el requerimiento.', 'warning')
      return
    }
    setDraftItems((items) => [
      ...items,
      {
        requirement,
        quantity: formatNumber(requirement.total_required).replace(/,/g, ''),
        notes: '',
      },
    ])
  }

  function updateDraftItem(requirementId: number, field: 'quantity' | 'notes', value: string) {
    setDraftItems((items) =>
      items.map((item) =>
        item.requirement.id === requirementId ? { ...item, [field]: value } : item,
      ),
    )
  }

  async function createRequisition() {
    if (!projectId || !houseModelId || !title.trim() || draftItems.length === 0) {
      showActionNotice('Selecciona desarrollo, modelo, nombre y al menos un material.', 'warning')
      return
    }
    try {
      const created = await apiRequest<MaterialRequisition>('/material-requisitions', {
        method: 'POST',
        body: JSON.stringify({
          project_id: Number(projectId),
          house_model_id: Number(houseModelId),
          title: title.trim(),
          priority,
          required_date: requiredDate || null,
          notes: notes || null,
          items: draftItems.map((item) => ({
            house_model_material_requirement_id: item.requirement.id,
            requested_quantity: item.quantity,
            notes: item.notes || null,
          })),
        }),
      })
      setDraftItems([])
      setTitle('')
      setNotes('')
      setRequiredDate('')
      showActionNotice(`Requerimiento ${created.requisition_number} enviado a Compras.`)
      await loadRequisitions()
    } catch (error) {
      showActionNotice(error instanceof Error ? error.message : 'No fue posible crear el requerimiento', 'error')
    }
  }

  async function reviewRequisition(decision: 'approved' | 'rejected') {
    if (!selectedRequisition) return
    try {
      const updated = await apiRequest<MaterialRequisition>(
        `/material-requisitions/${selectedRequisition.id}/review`,
        {
          method: 'POST',
          body: JSON.stringify({
            decision,
            review_notes: reviewNotes || null,
          }),
        },
      )
      setSelectedRequisitionId(updated.id)
      setReviewNotes('')
      showActionNotice(
        decision === 'approved'
          ? 'Requerimiento aprobado. Ya puedes enviarlo a cotizacion.'
          : 'Requerimiento rechazado y notificado a obra.',
        decision === 'approved' ? 'success' : 'warning',
      )
      await loadRequisitions()
    } catch (error) {
      showActionNotice(error instanceof Error ? error.message : 'No fue posible revisar el requerimiento', 'error')
    }
  }

  function toggleSupplier(supplierId: number) {
    setSelectedSupplierIds((current) =>
      current.includes(supplierId)
        ? current.filter((id) => id !== supplierId)
        : [...current, supplierId],
    )
  }

  async function convertToRFQ() {
    if (!selectedRequisition) return
    if (selectedSupplierIds.length < 3) {
      showActionNotice('Selecciona al menos 3 proveedores para continuar con Compras.', 'warning')
      return
    }
    try {
      const result = await apiRequest<{ rfq: { rfq_number: string } }>(
        `/material-requisitions/${selectedRequisition.id}/convert-to-rfq`,
        {
          method: 'POST',
          body: JSON.stringify({
            supplier_ids: selectedSupplierIds,
            title: selectedRequisition.title,
            required_by: selectedRequisition.required_date,
            response_deadline: rfqDeadline || null,
            notes: `Solicitud generada desde ${selectedRequisition.requisition_number}`,
          }),
        },
      )
      setSelectedSupplierIds([])
      setRfqDeadline('')
      showActionNotice(`Se genero ${result.rfq.rfq_number} y se envio a proveedores.`)
      await loadRequisitions()
    } catch (error) {
      showActionNotice(error instanceof Error ? error.message : 'No fue posible convertir a cotizacion', 'error')
    }
  }

  const pageTitle = isPurchasing ? 'Requerimientos de obra para Compras' : 'Requerimiento de material de obra'
  const pageSubtitle = isPurchasing
    ? 'Revisa solicitudes de obra y conviertelas en solicitudes de cotizacion a proveedores.'
    : 'Solicita materiales desde la explosion aprobada del modelo asignado al desarrollo.'

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-sky-300 bg-[linear-gradient(180deg,#f8fcff_0%,#e9f5ff_100%)] shadow-[0_24px_70px_rgba(5,28,44,0.26)]">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-sky-300 bg-[linear-gradient(180deg,#f8fcff_0%,#dff0fb_100%)] p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-sky-300 bg-sky-50 text-sky-700">
              <ClipboardList className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-acsm-muted">
                Operacion de obra
              </div>
              <h2 className="text-xl font-bold text-acsm-ink">{pageTitle}</h2>
              <p className="text-sm text-acsm-muted">{pageSubtitle}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              loadBaseData()
              loadRequisitions()
              if (projectId) loadAvailableMaterials()
            }}
            className="inline-flex h-11 items-center gap-2 rounded-xl border border-sky-300 bg-white px-4 text-sm font-bold text-acsm-ink transition hover:bg-sky-50"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Actualizar
          </button>
        </div>

        {!isPurchasing ? (
          <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-1.5 text-sm font-bold text-acsm-ink">
                  Desarrollo
                  <select
                    value={projectId}
                    onChange={(event) => setProjectId(event.target.value)}
                    className="h-11 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm"
                  >
                    <option value="">Seleccionar desarrollo</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1.5 text-sm font-bold text-acsm-ink">
                  Modelo del desarrollo
                  <select
                    value={houseModelId}
                    onChange={(event) => setHouseModelId(event.target.value)}
                    className="h-11 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm"
                  >
                    <option value="">Seleccionar modelo</option>
                    {modelOptions.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_160px_180px]">
                <label className="space-y-1.5 text-sm font-bold text-acsm-ink">
                  Nombre del requerimiento
                  <input
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Ej. Acero para colado semana 28"
                    className="h-11 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm"
                  />
                </label>
                <label className="space-y-1.5 text-sm font-bold text-acsm-ink">
                  Prioridad
                  <select
                    value={priority}
                    onChange={(event) => setPriority(event.target.value)}
                    className="h-11 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm"
                  >
                    <option value="low">Baja</option>
                    <option value="normal">Normal</option>
                    <option value="high">Alta</option>
                    <option value="urgent">Urgente</option>
                  </select>
                </label>
                <label className="space-y-1.5 text-sm font-bold text-acsm-ink">
                  Fecha requerida
                  <input
                    type="date"
                    value={requiredDate}
                    onChange={(event) => setRequiredDate(event.target.value)}
                    className="h-11 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm"
                  />
                </label>
              </div>
              <label className="space-y-1.5 text-sm font-bold text-acsm-ink">
                Notas para Compras
                <textarea
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Ubicacion en obra, frente, etapa o aclaraciones para compras."
                  className="min-h-20 w-full rounded-xl border border-sky-300 bg-white px-3 py-2 text-sm"
                />
              </label>
              <div className="rounded-2xl border border-sky-300 bg-white/75">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sky-300 bg-sky-50 px-4 py-3">
                  <div>
                    <h3 className="font-bold text-acsm-ink">Materiales disponibles</h3>
                    <p className="text-xs text-acsm-muted">
                      Solo se muestran partidas de explosion del modelo asignado al desarrollo.
                    </p>
                  </div>
                  <div className="relative w-full sm:w-80">
                    <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-acsm-muted" />
                    <input
                      value={materialSearch}
                      onChange={(event) => setMaterialSearch(event.target.value)}
                      placeholder="Buscar material, clave o familia"
                      className="h-10 w-full rounded-xl border border-sky-300 bg-white pl-9 pr-3 text-sm"
                    />
                  </div>
                </div>
                <div className="max-h-[430px] overflow-y-auto">
                  {filteredAvailableMaterials.map((item) => (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => addDraftItem(item)}
                      className="grid w-full gap-3 border-b border-sky-100 px-4 py-3 text-left transition hover:bg-sky-50 md:grid-cols-[minmax(0,1fr)_110px_130px_88px]"
                    >
                      <span className="min-w-0">
                        <span className="block text-sm font-bold text-acsm-ink">{item.description}</span>
                        <span className="block text-xs text-acsm-muted">
                          {item.source_code || 'Sin clave'} · {item.house_model_name}
                        </span>
                      </span>
                      <span className="text-sm font-semibold text-acsm-ink">{item.unit}</span>
                      <span className="text-sm text-acsm-muted">
                        Total sugerido: <b>{formatNumber(item.total_required)}</b>
                      </span>
                      <span className="inline-flex items-center justify-center rounded-xl border border-sky-300 bg-white px-3 py-2 text-sm font-bold text-sky-700">
                        <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
                        Agregar
                      </span>
                    </button>
                  ))}
                  {filteredAvailableMaterials.length === 0 ? (
                    <div className="px-4 py-10 text-center text-sm text-acsm-muted">
                      {selectedProject
                        ? 'No hay materiales de explosion para este desarrollo/modelo.'
                        : 'Selecciona un desarrollo para ver materiales.'}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-sky-300 bg-white/80">
              <div className="border-b border-sky-300 bg-sky-50 px-4 py-3">
                <h3 className="font-bold text-acsm-ink">Requerimiento en captura</h3>
                <p className="text-xs text-acsm-muted">{draftItems.length} partidas seleccionadas</p>
              </div>
              <div className="max-h-[520px] space-y-3 overflow-y-auto p-4">
                {draftItems.map((item) => (
                  <div key={item.requirement.id} className="rounded-2xl border border-sky-200 bg-white p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-bold text-acsm-ink">{item.requirement.description}</div>
                        <div className="text-xs text-acsm-muted">
                          {item.requirement.source_code || 'Sin clave'} · {item.requirement.unit}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setDraftItems((items) =>
                            items.filter((draft) => draft.requirement.id !== item.requirement.id),
                          )
                        }
                        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-600"
                        aria-label="Quitar partida"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <label className="space-y-1 text-xs font-bold uppercase tracking-wide text-acsm-muted">
                        Cantidad
                        <input
                          type="number"
                          min="0"
                          step="0.0001"
                          value={item.quantity}
                          onChange={(event) =>
                            updateDraftItem(item.requirement.id, 'quantity', event.target.value)
                          }
                          className="h-10 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm text-acsm-ink"
                        />
                      </label>
                      <label className="space-y-1 text-xs font-bold uppercase tracking-wide text-acsm-muted">
                        Nota
                        <input
                          value={item.notes}
                          onChange={(event) =>
                            updateDraftItem(item.requirement.id, 'notes', event.target.value)
                          }
                          placeholder="Opcional"
                          className="h-10 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm text-acsm-ink"
                        />
                      </label>
                    </div>
                  </div>
                ))}
                {draftItems.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-sky-300 bg-sky-50 px-4 py-10 text-center text-sm text-acsm-muted">
                    Agrega materiales desde la lista de la izquierda.
                  </div>
                ) : null}
              </div>
              <div className="border-t border-sky-300 p-4">
                <button
                  type="button"
                  onClick={createRequisition}
                  disabled={loading || draftItems.length === 0}
                  className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-[linear-gradient(180deg,#0d8bd3,#07578d)] px-4 text-sm font-bold text-white shadow-[0_14px_28px_rgba(0,91,160,0.26)] disabled:cursor-not-allowed disabled:opacity-55"
                >
                  <Send className="h-4 w-4" aria-hidden="true" />
                  Enviar requerimiento a Compras
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {isPurchasing ? (
          <div className="grid min-h-[720px] lg:grid-cols-[390px_minmax(0,1fr)]">
            <aside className="border-r border-sky-300 bg-sky-50/75">
              <div className="space-y-3 border-b border-sky-300 p-4">
                <div>
                  <h3 className="font-bold text-acsm-ink">Requerimientos</h3>
                  <p className="text-xs text-acsm-muted">Selecciona uno para revisar o convertir.</p>
                </div>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-acsm-muted" />
                  <input
                    value={requisitionSearch}
                    onChange={(event) => setRequisitionSearch(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') loadRequisitions()
                    }}
                    placeholder="Buscar folio, titulo o notas"
                    className="h-10 w-full rounded-xl border border-sky-300 bg-white pl-9 pr-3 text-sm"
                  />
                </div>
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  className="h-10 w-full rounded-xl border border-sky-300 bg-white px-3 text-sm"
	                >
	                  <option value="active">Por atender</option>
	                  <option value="">Todos</option>
	                  <option value="submitted">Pendientes de revisar</option>
	                  <option value="approved">Listos para cotizar</option>
	                  <option value="converted_to_rfq">Convertidos a cotizacion</option>
	                  <option value="rejected">Rechazados</option>
	                </select>
                <button
                  type="button"
                  onClick={loadRequisitions}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-sky-300 bg-white text-sm font-bold text-acsm-ink"
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Filtrar
                </button>
              </div>
              <div className="max-h-[610px] overflow-y-auto">
                {requisitions.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    onClick={() => setSelectedRequisitionId(item.id)}
                    className={[
                      'w-full border-b border-sky-200 px-4 py-4 text-left transition',
                      selectedRequisition?.id === item.id
                        ? 'bg-white shadow-[inset_4px_0_0_#0284c7]'
                        : 'hover:bg-white/70',
                    ].join(' ')}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-bold text-acsm-ink">{item.title}</div>
                        <div className="text-xs font-bold text-sky-700">{item.requisition_number}</div>
                      </div>
                      <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${statusClass(item.status)}`}>
                        {statusLabels[item.status] ?? item.status}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-acsm-muted">
                      {formatDate(item.created_at)} · {item.items.length} partidas
                    </div>
                  </button>
                ))}
                {requisitions.length === 0 ? (
                  <div className="px-4 py-12 text-center text-sm text-acsm-muted">
                    No hay requerimientos con los filtros actuales.
                  </div>
                ) : null}
              </div>
            </aside>

            <main className="min-w-0 p-5">
              {selectedRequisition ? (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-sky-300 bg-white/80 p-4">
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-acsm-muted">
                        Requerimiento seleccionado
                      </div>
                      <h3 className="text-xl font-bold text-acsm-ink">{selectedRequisition.title}</h3>
                      <p className="text-sm text-acsm-muted">
                        {selectedRequisition.requisition_number} · solicitado por{' '}
                        {selectedRequisition.requested_by?.full_name ?? 'Usuario'} ·{' '}
                        {priorityLabels[selectedRequisition.priority] ?? selectedRequisition.priority}
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                      <div className="rounded-xl border border-sky-300 bg-sky-50 px-3 py-2">
                        <div className="text-[10px] font-bold uppercase text-acsm-muted">Estado</div>
                        <div className="font-bold text-acsm-ink">
                          {statusLabels[selectedRequisition.status] ?? selectedRequisition.status}
                        </div>
                      </div>
                      <div className="rounded-xl border border-sky-300 bg-sky-50 px-3 py-2">
                        <div className="text-[10px] font-bold uppercase text-acsm-muted">Requerida</div>
                        <div className="font-bold text-acsm-ink">{formatDate(selectedRequisition.required_date)}</div>
                      </div>
                      <div className="rounded-xl border border-sky-300 bg-sky-50 px-3 py-2">
                        <div className="text-[10px] font-bold uppercase text-acsm-muted">Partidas</div>
                        <div className="font-bold text-acsm-ink">{selectedRequisition.items.length}</div>
                      </div>
                    </div>
                  </div>

                  <div className="overflow-hidden rounded-2xl border border-sky-300 bg-white/80">
                    <div className="border-b border-sky-300 bg-sky-50 px-4 py-3">
                      <h3 className="font-bold text-acsm-ink">Material solicitado por obra</h3>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[760px] text-sm">
                        <thead className="bg-sky-100 text-xs uppercase text-acsm-muted">
                          <tr>
                            <th className="px-4 py-3 text-left">Material</th>
                            <th className="px-4 py-3 text-left">Unidad</th>
                            <th className="px-4 py-3 text-left">Solicitado</th>
                            <th className="px-4 py-3 text-left">Aprobado</th>
                            <th className="px-4 py-3 text-left">Notas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedRequisition.items.map((item) => (
                            <tr key={item.id} className="border-t border-sky-100">
                              <td className="px-4 py-3">
                                <div className="font-bold text-acsm-ink">{item.description}</div>
                                <div className="text-xs text-acsm-muted">{item.source_code || 'Sin clave'}</div>
                              </td>
                              <td className="px-4 py-3 text-acsm-muted">{item.unit}</td>
                              <td className="px-4 py-3 font-semibold text-acsm-ink">
                                {formatNumber(item.requested_quantity)}
                              </td>
                              <td className="px-4 py-3 font-semibold text-acsm-ink">
                                {formatNumber(item.approved_quantity)}
                              </td>
                              <td className="px-4 py-3 text-acsm-muted">{item.notes || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {selectedRequisition.status === 'submitted' || selectedRequisition.status === 'in_review' ? (
                    <div className="rounded-2xl border border-sky-300 bg-white/80 p-4">
                      <h3 className="font-bold text-acsm-ink">Revision de Compras</h3>
                      <p className="text-sm text-acsm-muted">
                        Aprueba para convertir a cotizacion o rechaza con notas para obra.
                      </p>
                      <textarea
                        value={reviewNotes}
                        onChange={(event) => setReviewNotes(event.target.value)}
                        placeholder="Notas de revision"
                        className="mt-3 min-h-24 w-full rounded-xl border border-sky-300 bg-white px-3 py-2 text-sm"
                      />
                      <div className="mt-3 flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => reviewRequisition('approved')}
                          className="inline-flex h-11 items-center gap-2 rounded-xl bg-[linear-gradient(180deg,#0d8bd3,#07578d)] px-4 text-sm font-bold text-white"
                        >
                          <Check className="h-4 w-4" aria-hidden="true" />
                          Aprobar requerimiento
                        </button>
                        <button
                          type="button"
                          onClick={() => reviewRequisition('rejected')}
                          className="inline-flex h-11 items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 text-sm font-bold text-rose-700"
                        >
                          <X className="h-4 w-4" aria-hidden="true" />
                          Rechazar
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {selectedRequisition.status === 'approved' ? (
                    <div className="rounded-2xl border border-sky-300 bg-white/80 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <h3 className="font-bold text-acsm-ink">Enviar a cotizacion</h3>
                          <p className="text-sm text-acsm-muted">
                            Selecciona proveedores. El requerimiento se convertira en Solicitud de cotizacion.
                          </p>
                        </div>
                        <label className="space-y-1 text-sm font-bold text-acsm-ink">
                          Limite de respuesta
                          <input
                            type="date"
                            value={rfqDeadline}
                            onChange={(event) => setRfqDeadline(event.target.value)}
                            className="h-10 rounded-xl border border-sky-300 bg-white px-3 text-sm"
                          />
                        </label>
                      </div>
                      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        {suppliers.map((supplier) => (
                          <label
                            key={supplier.id}
                            className={[
                              'flex cursor-pointer items-center justify-between gap-3 rounded-2xl border p-3 transition',
                              selectedSupplierIds.includes(supplier.id)
                                ? 'border-sky-500 bg-sky-50'
                                : 'border-sky-200 bg-white hover:border-sky-300',
                            ].join(' ')}
                          >
                            <span className="min-w-0">
                              <span className="block truncate text-sm font-bold text-acsm-ink">
                                {supplier.name}
                              </span>
                              <span className="text-xs text-acsm-muted">
                                {supplier.payment_terms_days ?? 0} dias credito
                              </span>
                            </span>
                            <input
                              type="checkbox"
                              checked={selectedSupplierIds.includes(supplier.id)}
                              onChange={() => toggleSupplier(supplier.id)}
                              className="h-4 w-4"
                            />
                          </label>
                        ))}
                      </div>
                      <button
                        type="button"
                        onClick={convertToRFQ}
                        className="mt-4 inline-flex h-11 items-center gap-2 rounded-xl bg-[linear-gradient(180deg,#0d8bd3,#07578d)] px-4 text-sm font-bold text-white"
                      >
                        <FileText className="h-4 w-4" aria-hidden="true" />
                        Crear solicitud de cotizacion
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-sky-300 bg-white/70 px-4 py-16 text-center text-sm text-acsm-muted">
                  Selecciona un requerimiento para revisar su detalle.
                </div>
              )}
            </main>
          </div>
        ) : null}
      </section>

      {!isPurchasing ? (
        <section className="overflow-hidden rounded-3xl border border-sky-300 bg-[linear-gradient(180deg,#f8fcff_0%,#e9f5ff_100%)] shadow-[0_24px_70px_rgba(5,28,44,0.22)]">
          <div className="border-b border-sky-300 bg-sky-50 px-5 py-4">
            <h2 className="text-lg font-bold text-acsm-ink">Mis requerimientos enviados</h2>
            <p className="text-sm text-acsm-muted">Seguimiento de solicitudes enviadas a Compras.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="bg-sky-100 text-xs uppercase text-acsm-muted">
                <tr>
                  <th className="px-5 py-3 text-left">Folio</th>
                  <th className="px-5 py-3 text-left">Requerimiento</th>
                  <th className="px-5 py-3 text-left">Estado</th>
                  <th className="px-5 py-3 text-left">Partidas</th>
                  <th className="px-5 py-3 text-left">Fecha requerida</th>
                  <th className="px-5 py-3 text-left">Revision</th>
                </tr>
              </thead>
              <tbody>
                {requisitions.map((item) => (
                  <tr key={item.id} className="border-t border-sky-100">
                    <td className="px-5 py-4 font-bold text-sky-700">{item.requisition_number}</td>
                    <td className="px-5 py-4 font-bold text-acsm-ink">{item.title}</td>
                    <td className="px-5 py-4">
                      <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${statusClass(item.status)}`}>
                        {statusLabels[item.status] ?? item.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-acsm-muted">{item.items.length}</td>
                    <td className="px-5 py-4 text-acsm-muted">{formatDate(item.required_date)}</td>
                    <td className="px-5 py-4 text-acsm-muted">{item.review_notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {requisitions.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-acsm-muted">
                Aun no hay requerimientos capturados para este desarrollo.
              </div>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  )
}
