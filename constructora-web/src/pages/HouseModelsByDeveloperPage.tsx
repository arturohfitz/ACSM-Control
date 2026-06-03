import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Check,
  FileSpreadsheet,
  FileText,
  Home,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { apiRequest } from '../lib/api'

type Client = {
  id: number
  name: string
  contact_name?: string | null
  contact_email?: string | null
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
  base_notes?: string | null
}

type ModelMaterialRequirement = {
  id: number
  material_id?: number | null
  source_code?: string | null
  description: string
  unit: string
  quantity_per_house: string | number
  unit_cost_reference?: string | number | null
  total_cost_reference?: string | number | null
  family?: string | null
  validation_status: ReviewStatus
}

type ModelBudgetActivity = {
  id: number
  construction_concept_id?: number | null
  chapter_code?: string | null
  chapter_name?: string | null
  source_code?: string | null
  description: string
  unit: string
  quantity_per_house: string | number
  unit_price_reference?: string | number | null
  total_price_reference?: string | number | null
  validation_status: ReviewStatus
}

type ReviewStatus = 'pending' | 'validated' | 'ignored'

type Material = {
  id: number
  name: string
  unit: string
}

type ConstructionConcept = {
  id: number
  code: string
  name: string
  unit: string
}

type HouseModelDocument = {
  id: number
  document_type: 'explosion' | 'budget'
  version?: string | null
  source_code?: string | null
  source_date?: string | null
  file_name: string
  status: string
  total_items: number
  total_amount?: string | number | null
  created_at: string
  material_requirements?: ModelMaterialRequirement[]
  budget_activities?: ModelBudgetActivity[]
}

type ModelForm = {
  name: string
  description: string
  construction_m2: string
  levels: string
  bedrooms: string
  bathrooms: string
  base_notes: string
}

const emptyForm: ModelForm = {
  name: '',
  description: '',
  construction_m2: '',
  levels: '',
  bedrooms: '',
  bathrooms: '',
  base_notes: '',
}

function formatNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '-'
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 }).format(Number(value))
}

function nullableNumber(value: string) {
  return value === '' ? null : Number(value)
}

function nullableText(value: string) {
  return value.trim() === '' ? null : value
}

function formFromModel(model: HouseModel): ModelForm {
  return {
    name: model.name,
    description: model.description ?? '',
    construction_m2: String(model.construction_m2 ?? ''),
    levels: model.levels === null || model.levels === undefined ? '' : String(model.levels),
    bedrooms: model.bedrooms === null || model.bedrooms === undefined ? '' : String(model.bedrooms),
    bathrooms:
      model.bathrooms === null || model.bathrooms === undefined ? '' : String(model.bathrooms),
    base_notes: model.base_notes ?? '',
  }
}

type SummaryRow = {
  id: number
  order: number
  code: string
  name: string
  group: string
  unit: string
  quantity: string
  quantityValue: number
  amount: string
  amountValue: number
  status: ReviewStatus
  linkedId?: number | null
}

type IntegrationFilter = 'all' | 'integrated' | 'pending' | 'ignored'
type RowSort = 'document' | 'code_asc' | 'code_desc' | 'name_asc' | 'amount_desc' | 'amount_asc' | 'quantity_desc' | 'quantity_asc'
type GroupSort = 'amount_desc' | 'amount_asc' | 'name_asc' | 'count_desc'

type GroupSummaryRow = {
  label: string
  count: number
  amount: number
}

function numberValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return 0
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function normalizeSearch(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

function classifyGroup(label: string) {
  const value = normalizeSearch(label)
  if (value.includes('segundo') || value.includes('planta alta') || value.includes('escalera')) {
    return 'Planta alta'
  }
  if (
    value.includes('primer nivel') ||
    value.includes('planta baja') ||
    value.includes('cimentacion') ||
    value.includes('firme') ||
    value.includes('preliminar')
  ) {
    return 'Planta baja'
  }
  if (value.includes('azotea') || value.includes('tinaco')) return 'Azotea'
  if (value.includes('fachada') || value.includes('banqueta') || value.includes('barda') || value.includes('exterior')) {
    return 'Exterior'
  }
  if (value.includes('instalac') || value.includes('gas') || value.includes('sanitaria') || value.includes('electrica')) {
    return 'Instalaciones'
  }
  if (
    value.includes('acabado') ||
    value.includes('mueble') ||
    value.includes('azulejo') ||
    value.includes('puerta') ||
    value.includes('chapa') ||
    value.includes('ventana') ||
    value.includes('herrer')
  ) {
    return 'Acabados'
  }
  return 'General'
}

function formatCurrency(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '-'
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 2,
  }).format(Number(value))
}

function integrationLabel(row: Pick<SummaryRow, 'status' | 'linkedId'>) {
  if (row.status === 'ignored') return 'Ignorada'
  if (row.linkedId) return 'Integrada'
  return 'Pendiente de integrar'
}

function integrationPillClass(row: Pick<SummaryRow, 'status' | 'linkedId'>) {
  if (row.status === 'ignored') return 'border-slate-300 bg-slate-100 text-slate-600'
  if (row.linkedId) return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  return 'border-amber-200 bg-amber-50 text-amber-800'
}

function integrationStatus(row: Pick<SummaryRow, 'status' | 'linkedId'>): Exclude<IntegrationFilter, 'all'> {
  if (row.status === 'ignored') return 'ignored'
  if (row.linkedId) return 'integrated'
  return 'pending'
}

function buildExplosionGroups(document: HouseModelDocument | null): GroupSummaryRow[] {
  const groups = new Map<string, GroupSummaryRow>()
  for (const item of document?.material_requirements ?? []) {
    const key = item.family || 'Sin familia'
    const current = groups.get(key) ?? { label: key, count: 0, amount: 0 }
    current.count += 1
    current.amount += numberValue(item.total_cost_reference)
    groups.set(key, current)
  }
  return [...groups.values()].sort((left, right) => right.amount - left.amount)
}

function buildBudgetGroups(document: HouseModelDocument | null): GroupSummaryRow[] {
  const groups = new Map<string, GroupSummaryRow>()
  for (const item of document?.budget_activities ?? []) {
    const key = item.chapter_name || item.chapter_code || 'Sin capitulo'
    const current = groups.get(key) ?? { label: key, count: 0, amount: 0 }
    current.count += 1
    current.amount += numberValue(item.total_price_reference)
    groups.set(key, current)
  }
  return [...groups.values()].sort((left, right) => right.amount - left.amount)
}

function DocumentSummary({
  title,
  subtitle,
  catalogLabel,
  document,
  emptyText,
  rows,
  groups,
  expanded,
  onToggleExpanded,
  catalogOptions,
  onLink,
  onCreateCatalogItem,
  onIgnore,
  onRestore,
  onIntegrateAll,
  actionBusyKey,
}: {
  title: string
  subtitle: string
  catalogLabel: string
  document: HouseModelDocument | null
  emptyText: string
  rows: SummaryRow[]
  groups: GroupSummaryRow[]
  expanded: boolean
  onToggleExpanded: () => void
  catalogOptions: { id: number; label: string }[]
  onLink: (rowId: number, linkedId: number | null) => void
  onCreateCatalogItem: (rowId: number) => void
  onIgnore: (rowId: number) => void
  onRestore: (rowId: number) => void
  onIntegrateAll: (pendingCount: number) => void
  actionBusyKey: string
}) {
  const [statusFilter, setStatusFilter] = useState<IntegrationFilter>('all')
  const [groupSearch, setGroupSearch] = useState('')
  const [groupSort, setGroupSort] = useState<GroupSort>('amount_desc')
  const [selectedGroup, setSelectedGroup] = useState('')
  const [rowSearch, setRowSearch] = useState('')
  const [rowSort, setRowSort] = useState<RowSort>('document')
  const integrationCounts = useMemo(() => {
    return rows.reduce(
      (counts, row) => {
        const status = integrationStatus(row)
        counts[status] += 1
        return counts
      },
      { integrated: 0, pending: 0, ignored: 0 },
    )
  }, [rows])
  const filteredGroups = useMemo(() => {
    const search = normalizeSearch(groupSearch.trim())
    const nextGroups = groups.filter((group) =>
      search ? normalizeSearch(`${group.label} ${classifyGroup(group.label)}`).includes(search) : true,
    )
    return [...nextGroups].sort((left, right) => {
      if (groupSort === 'name_asc') return left.label.localeCompare(right.label, 'es')
      if (groupSort === 'count_desc') return right.count - left.count
      if (groupSort === 'amount_asc') return left.amount - right.amount
      return right.amount - left.amount
    })
  }, [groups, groupSearch, groupSort])
  const filteredRows = useMemo(() => {
    const search = normalizeSearch(rowSearch.trim())
    const nextRows = rows.filter((row) => {
      if (statusFilter !== 'all' && integrationStatus(row) !== statusFilter) return false
      if (selectedGroup && row.group !== selectedGroup) return false
      if (!search) return true
      return normalizeSearch(`${row.order} ${row.code} ${row.name} ${row.unit} ${row.group}`).includes(search)
    })
    return [...nextRows].sort((left, right) => {
      if (rowSort === 'code_asc') return left.code.localeCompare(right.code, 'es')
      if (rowSort === 'code_desc') return right.code.localeCompare(left.code, 'es')
      if (rowSort === 'name_asc') return left.name.localeCompare(right.name, 'es')
      if (rowSort === 'amount_desc') return right.amountValue - left.amountValue
      if (rowSort === 'amount_asc') return left.amountValue - right.amountValue
      if (rowSort === 'quantity_desc') return right.quantityValue - left.quantityValue
      if (rowSort === 'quantity_asc') return left.quantityValue - right.quantityValue
      return left.order - right.order
    })
  }, [rows, statusFilter, selectedGroup, rowSearch, rowSort])
  const categoryDetailMode = Boolean(selectedGroup)
  const visibleRows = categoryDetailMode || expanded ? filteredRows : filteredRows.slice(0, 8)
  const bulkBusy = document ? actionBusyKey === `${document.document_type}:bulk` : false

  return (
    <div className="overflow-hidden rounded-md border-2 border-[#8fb4d4] bg-white shadow-[0_10px_24px_rgba(31,66,110,0.12)]">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#8fb4d4] bg-[linear-gradient(180deg,#f8fbff_0%,#dfeaf5_100%)] px-4 py-3">
        <div>
          <h4 className="text-sm font-semibold text-acsm-ink">{title}</h4>
          <p className="mt-0.5 text-xs text-acsm-muted">{subtitle}</p>
          <p className="mt-0.5 text-xs text-acsm-muted">
            {document
              ? `${document.file_name} · ${document.source_date ?? 'sin fecha'}`
              : emptyText}
          </p>
        </div>
        {document ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <div className="rounded-md border border-[#aac5dc] bg-white px-3 py-2 shadow-sm">
              <div className="text-[10px] font-semibold uppercase text-acsm-muted">Partidas</div>
              <div className="text-sm font-semibold text-acsm-ink">{document.total_items}</div>
            </div>
            <div className="rounded-md border border-[#aac5dc] bg-white px-3 py-2 shadow-sm">
              <div className="text-[10px] font-semibold uppercase text-acsm-muted">Total</div>
              <div className="text-sm font-semibold text-acsm-ink">{formatCurrency(document.total_amount)}</div>
            </div>
            <button
              type="button"
              onClick={onToggleExpanded}
              className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-800 hover:bg-blue-100"
            >
              {expanded ? 'Contraer' : 'Ver detalle'}
            </button>
          </div>
        ) : null}
      </div>

      {document ? (
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#aac5dc] bg-[#f7fbff] px-3 py-3">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
                {integrationCounts.integrated} integradas
              </span>
              <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
                {integrationCounts.pending} pendientes
              </span>
              <span className="rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {integrationCounts.ignored} ignoradas
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs font-semibold uppercase text-acsm-muted">
                Estado
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as IntegrationFilter)}
                  className="ml-2 h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold normal-case text-acsm-ink"
                >
                  <option value="all">Todas</option>
                  <option value="pending">Pendientes</option>
                  <option value="integrated">Integradas</option>
                  <option value="ignored">Ignoradas</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => onIntegrateAll(integrationCounts.pending)}
                disabled={bulkBusy || integrationCounts.pending === 0}
                className="inline-flex h-9 items-center justify-center rounded-md border border-blue-200 bg-blue-50 px-3 text-xs font-semibold text-blue-800 hover:bg-blue-100 disabled:opacity-50"
              >
                {bulkBusy ? 'Vinculando' : 'Vincular todo'}
              </button>
            </div>
          </div>
          <div className="border-b border-[#aac5dc] bg-[#eef6fc] p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-xs font-semibold text-acsm-ink">Resumen por categoria</div>
                <div className="text-[11px] text-acsm-muted">
                  Selecciona una categoria para revisar sus partidas abajo.
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  value={groupSearch}
                  onChange={(event) => setGroupSearch(event.target.value)}
                  placeholder="Buscar categoria"
                  className="h-9 w-48 rounded-md border border-slate-300 bg-white px-3 text-xs text-acsm-ink"
                />
                <select
                  value={groupSort}
                  onChange={(event) => setGroupSort(event.target.value as GroupSort)}
                  className="h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-acsm-ink"
                >
                  <option value="amount_desc">Mayor monto</option>
                  <option value="amount_asc">Menor monto</option>
                  <option value="count_desc">Mas partidas</option>
                  <option value="name_asc">A-Z</option>
                </select>
              </div>
            </div>
            <div className="overflow-hidden rounded-md border border-[#8fb4d4] bg-white shadow-sm">
              <div className="grid grid-cols-[minmax(0,1fr)_120px_90px_120px_110px] gap-2 border-b border-[#aac5dc] bg-[#d8e8f4] px-3 py-2 text-[10px] font-semibold uppercase text-acsm-muted">
                <div>Categoria</div>
                <div>Area sugerida</div>
                <div>Partidas</div>
                <div>Monto</div>
                <div>Detalle</div>
              </div>
              <div className="max-h-[320px] divide-y divide-slate-100 overflow-auto">
                {(expanded ? filteredGroups : filteredGroups.slice(0, 6)).map((group) => (
                  <button
                    key={group.label}
                    type="button"
                    onClick={() => setSelectedGroup((current) => (current === group.label ? '' : group.label))}
                    className={[
                      'grid w-full grid-cols-[minmax(0,1fr)_120px_90px_120px_110px] gap-2 px-3 py-2 text-left text-xs transition',
                      selectedGroup === group.label
                        ? 'bg-blue-50 shadow-[inset_4px_0_0_#0b7fbd]'
                        : 'bg-white hover:bg-slate-50',
                    ].join(' ')}
                  >
                    <div className="min-w-0 truncate font-semibold text-acsm-ink">{group.label}</div>
                    <div className="text-acsm-muted">{classifyGroup(group.label)}</div>
                    <div className="text-acsm-ink">{group.count}</div>
                    <div className="font-semibold text-acsm-ink">{formatCurrency(group.amount)}</div>
                    <div className="font-semibold text-blue-700">
                      {selectedGroup === group.label ? 'Mostrando' : 'Ver partidas'}
                    </div>
                  </button>
                ))}
                {filteredGroups.length === 0 ? (
                  <div className="px-3 py-6 text-center text-xs text-acsm-muted">
                    No hay categorias con ese filtro.
                  </div>
                ) : null}
              </div>
            </div>
            {selectedGroup ? (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-acsm-muted">
                <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 font-semibold text-blue-800">
                  Filtro activo: {selectedGroup}
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedGroup('')}
                  className="rounded-full border border-slate-300 bg-white px-3 py-1 font-semibold text-acsm-ink hover:bg-slate-50"
                >
                  Ver todas
                </button>
              </div>
            ) : null}
          </div>

          <div className="divide-y divide-slate-100">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#aac5dc] bg-[#f8fbff] px-3 py-3">
              <div>
                <div className="text-xs font-semibold text-acsm-ink">Partidas interpretadas</div>
                <div className="text-[11px] text-acsm-muted">
                  El orden inicial respeta como llego el documento.
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  value={rowSearch}
                  onChange={(event) => setRowSearch(event.target.value)}
                  placeholder="Buscar clave, descripcion o unidad"
                  className="h-9 w-64 max-w-full rounded-md border border-slate-300 bg-white px-3 text-xs text-acsm-ink"
                />
                <select
                  value={rowSort}
                  onChange={(event) => setRowSort(event.target.value as RowSort)}
                  className="h-9 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-acsm-ink"
                >
                  <option value="document">Orden del documento</option>
                  <option value="code_asc">Clave A-Z</option>
                  <option value="code_desc">Clave Z-A</option>
                  <option value="name_asc">Descripcion A-Z</option>
                  <option value="amount_desc">Mayor importe</option>
                  <option value="amount_asc">Menor importe</option>
                  <option value="quantity_desc">Mayor cantidad</option>
                  <option value="quantity_asc">Menor cantidad</option>
                </select>
              </div>
            </div>
            <div
              className={[
                'hidden gap-2 border-b border-[#aac5dc] bg-[#d8e8f4] px-3 py-2 text-[10px] font-semibold uppercase text-acsm-muted xl:grid',
                categoryDetailMode
                  ? 'grid-cols-[54px_72px_minmax(360px,1.5fr)_52px_78px_92px_112px_minmax(130px,180px)_128px]'
                  : 'grid-cols-[54px_72px_minmax(0,1fr)_52px_78px_92px_120px_minmax(160px,220px)_140px]',
              ].join(' ')}
            >
              <div>No.</div>
              <div>Clave</div>
              <div>Descripcion</div>
              <div>Unidad</div>
              <div>Cantidad</div>
              <div>Importe</div>
              <div>Estado</div>
              <div>{catalogLabel}</div>
              <div>Accion</div>
            </div>
            {visibleRows.map((row, index) => (
              <div
                key={`${row.code}-${index}`}
                className={[
                  'grid gap-2 px-3 py-3 text-xs xl:items-start',
                  categoryDetailMode
                    ? 'xl:grid-cols-[54px_72px_minmax(360px,1.5fr)_52px_78px_92px_112px_minmax(130px,180px)_128px]'
                    : 'xl:grid-cols-[54px_72px_minmax(0,1fr)_52px_78px_92px_120px_minmax(160px,220px)_140px]',
                  row.status === 'ignored' ? 'bg-slate-50/80 opacity-75' : '',
                ].join(' ')}
              >
                <div className="flex items-start justify-between gap-3 xl:block">
                  <span className="text-[10px] font-semibold uppercase text-acsm-muted xl:hidden">No.</span>
                  <span className="font-semibold text-acsm-muted">{row.order}</span>
                </div>
                <div className="flex items-start justify-between gap-3 xl:block">
                  <span className="text-[10px] font-semibold uppercase text-acsm-muted xl:hidden">Clave</span>
                  <span className="font-semibold text-acsm-ink">{row.code}</span>
                </div>
                <div className="min-w-0">
                  <div className="mb-1 text-[10px] font-semibold uppercase text-acsm-muted xl:hidden">
                    Descripcion
                  </div>
                  <p
                    className={[
                      'break-words leading-snug text-acsm-ink',
                      categoryDetailMode || expanded ? 'whitespace-normal' : 'line-clamp-2',
                    ].join(' ')}
                  >
                    {row.name}
                  </p>
                </div>
                <div className="flex items-center justify-between gap-3 xl:block">
                  <span className="text-[10px] font-semibold uppercase text-acsm-muted xl:hidden">Unidad</span>
                  <span className="text-acsm-muted">{row.unit}</span>
                </div>
                <div className="flex items-center justify-between gap-3 xl:block">
                  <span className="text-[10px] font-semibold uppercase text-acsm-muted xl:hidden">Cantidad</span>
                  <span className="text-acsm-ink">{row.quantity}</span>
                </div>
                <div className="flex items-center justify-between gap-3 xl:block">
                  <span className="text-[10px] font-semibold uppercase text-acsm-muted xl:hidden">Importe</span>
                  <span className="font-semibold text-acsm-ink">{row.amount}</span>
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between gap-2 xl:hidden">
                    <span className="text-[10px] font-semibold uppercase text-acsm-muted">Estado</span>
                  </div>
                  <span
                    className={`inline-flex min-h-8 items-center rounded-full border px-3 py-1 text-[11px] font-semibold ${integrationPillClass(row)}`}
                  >
                    {integrationLabel(row)}
                  </span>
                </div>
                <div className="min-w-0">
                  <div className="mb-1 text-[10px] font-semibold uppercase text-acsm-muted xl:hidden">
                    {catalogLabel}
                  </div>
                  <select
                    value={row.linkedId ?? ''}
                    onChange={(event) =>
                      onLink(row.id, event.target.value ? Number(event.target.value) : null)
                    }
                    disabled={row.status === 'ignored'}
                    className="h-8 w-full rounded-md border border-slate-200 bg-white px-2 text-xs text-acsm-ink disabled:opacity-60"
                  >
                    <option value="">Seleccionar existente</option>
                    {catalogOptions.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  {row.status === 'ignored' ? (
                    <button
                      type="button"
                      onClick={() => onRestore(row.id)}
                      disabled={actionBusyKey === `${document.document_type}:${row.id}`}
                      className="h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      Reactivar
                    </button>
                  ) : row.linkedId ? (
                    <button
                      type="button"
                      onClick={() => onLink(row.id, null)}
                      disabled={actionBusyKey === `${document.document_type}:${row.id}`}
                      className="h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      Desvincular
                    </button>
                  ) : (
                    <div className="grid gap-1">
                      <button
                        type="button"
                        onClick={() => onCreateCatalogItem(row.id)}
                        disabled={actionBusyKey === `${document.document_type}:${row.id}`}
                        className="h-8 w-full rounded-md border border-blue-200 bg-blue-50 px-2 text-xs font-semibold text-blue-800 hover:bg-blue-100 disabled:opacity-50"
                      >
                        Crear nuevo
                      </button>
                      <button
                        type="button"
                        onClick={() => onIgnore(row.id)}
                        disabled={actionBusyKey === `${document.document_type}:${row.id}`}
                        className="h-8 w-full rounded-md border border-amber-200 bg-amber-50 px-2 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                      >
                        Ignorar
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          {filteredRows.length > visibleRows.length || rows.length !== filteredRows.length ? (
            <div className="border-t border-slate-100 px-3 py-2 text-xs text-acsm-muted">
              Mostrando {visibleRows.length} de {filteredRows.length} partidas filtradas.
              {rows.length !== filteredRows.length ? ` Total interpretadas: ${rows.length}.` : ''}
            </div>
          ) : null}
          </div>
        </div>
      ) : (
        <div className="px-3 py-8 text-center text-sm text-acsm-muted">{emptyText}</div>
      )}
    </div>
  )
}

export default function HouseModelsByDeveloperPage() {
  const { hasPermission } = useAuth()
  const [clients, setClients] = useState<Client[]>([])
  const [models, setModels] = useState<HouseModel[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [concepts, setConcepts] = useState<ConstructionConcept[]>([])
  const [selectedClientId, setSelectedClientId] = useState('')
  const [editing, setEditing] = useState<HouseModel | null>(null)
  const [isModelFormOpen, setIsModelFormOpen] = useState(false)
  const [selectedModelId, setSelectedModelId] = useState('')
  const [documents, setDocuments] = useState<HouseModelDocument[]>([])
  const [expandedDetails, setExpandedDetails] = useState({ explosion: false, budget: false })
  const [documentLoading, setDocumentLoading] = useState(false)
  const [documentError, setDocumentError] = useState('')
  const [explosionFile, setExplosionFile] = useState<File | null>(null)
  const [budgetFile, setBudgetFile] = useState<File | null>(null)
  const [uploadingDocumentType, setUploadingDocumentType] = useState<'explosion' | 'budget' | ''>('')
  const [reviewActionKey, setReviewActionKey] = useState('')
  const [form, setForm] = useState<ModelForm>(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const canCreate = hasPermission('house_models:create')
  const canEdit = hasPermission('house_models:edit')
  const canDelete = hasPermission('house_models:delete')

  const selectedClient = useMemo(
    () => clients.find((client) => String(client.id) === selectedClientId),
    [clients, selectedClientId],
  )

  const selectedModels = useMemo(
    () => models.filter((model) => String(model.client_id) === selectedClientId),
    [models, selectedClientId],
  )

  const totalM2 = useMemo(
    () =>
      selectedModels.reduce((total, model) => total + Number(model.construction_m2 || 0), 0),
    [selectedModels],
  )

  const selectedModel = useMemo(
    () => selectedModels.find((model) => String(model.id) === selectedModelId) ?? null,
    [selectedModelId, selectedModels],
  )

  const latestExplosion = useMemo(
    () => documents.find((document) => document.document_type === 'explosion') ?? null,
    [documents],
  )

  const latestBudget = useMemo(
    () => documents.find((document) => document.document_type === 'budget') ?? null,
    [documents],
  )

  const selectedDocumentTotal = useMemo(
    () => numberValue(latestExplosion?.total_amount) + numberValue(latestBudget?.total_amount),
    [latestExplosion, latestBudget],
  )

  const explosionGroups = useMemo(() => buildExplosionGroups(latestExplosion), [latestExplosion])
  const budgetGroups = useMemo(() => buildBudgetGroups(latestBudget), [latestBudget])

  const materialOptions = useMemo(
    () =>
      materials
        .map((material) => ({ id: material.id, label: `${material.name} (${material.unit})` }))
        .sort((left, right) => left.label.localeCompare(right.label, 'es')),
    [materials],
  )

  const conceptOptions = useMemo(
    () =>
      concepts
        .map((concept) => ({ id: concept.id, label: `${concept.code} · ${concept.name}` }))
        .sort((left, right) => left.label.localeCompare(right.label, 'es')),
    [concepts],
  )

  async function loadData(preferredClientId = selectedClientId) {
    setLoading(true)
    setError('')
    try {
      const [clientData, modelData, materialData, conceptData] = await Promise.all([
        apiRequest<Client[]>('/clients'),
        apiRequest<HouseModel[]>('/house-models'),
        apiRequest<Material[]>('/materials?limit=1000'),
        apiRequest<ConstructionConcept[]>('/construction-concepts?limit=1000'),
      ])
      setClients(clientData)
      setModels(modelData)
      setMaterials(materialData)
      setConcepts(conceptData)
      const nextClientId = preferredClientId || (clientData[0] ? String(clientData[0].id) : '')
      setSelectedClientId(nextClientId)
      const clientModels = modelData.filter((model) => String(model.client_id) === nextClientId)
      setSelectedModelId((current) =>
        current && clientModels.some((model) => String(model.id) === current)
          ? current
          : clientModels[0]
            ? String(clientModels[0].id)
            : '',
      )
      if (!preferredClientId && !editing) setForm(emptyForm)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar modelos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  useEffect(() => {
    if (!selectedModelId) {
      setDocuments([])
      return
    }
    void loadDocuments(selectedModelId)
  }, [selectedModelId])

  useEffect(() => {
    if (!selectedModels.length) {
      setSelectedModelId('')
      return
    }
    if (!selectedModels.some((model) => String(model.id) === selectedModelId)) {
      setSelectedModelId(String(selectedModels[0].id))
    }
  }, [selectedModels, selectedModelId])

  async function loadDocuments(modelId = selectedModelId) {
    if (!modelId) return
    setDocumentLoading(true)
    setDocumentError('')
    try {
      const data = await apiRequest<HouseModelDocument[]>(`/house-models/${modelId}/documents`)
      setDocuments(data)
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : 'No fue posible cargar documentos')
    } finally {
      setDocumentLoading(false)
    }
  }

  function selectClient(clientId: string) {
    setSelectedClientId(clientId)
    const nextModel = models.find((model) => String(model.client_id) === clientId)
    setSelectedModelId(nextModel ? String(nextModel.id) : '')
    setEditing(null)
    setIsModelFormOpen(false)
    setForm(emptyForm)
    setDocuments([])
    setError('')
    setNotice('')
  }

  function startCreate() {
    setEditing(null)
    setForm(emptyForm)
    setIsModelFormOpen(true)
    setError('')
    setNotice('')
  }

  function startEdit(model: HouseModel) {
    setSelectedClientId(String(model.client_id))
    setSelectedModelId(String(model.id))
    setEditing(model)
    setForm(formFromModel(model))
    setIsModelFormOpen(true)
    setError('')
    setNotice('')
  }

  function selectModel(model: HouseModel) {
    setSelectedModelId(String(model.id))
    setDocuments([])
    setError('')
      setNotice('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedClientId) return
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const payload = {
        client_id: Number(selectedClientId),
        name: form.name.trim(),
        description: nullableText(form.description),
        construction_m2: Number(form.construction_m2),
        levels: nullableNumber(form.levels),
        bedrooms: nullableNumber(form.bedrooms),
        bathrooms: nullableNumber(form.bathrooms),
        base_notes: nullableText(form.base_notes),
      }
      if (editing) {
        await apiRequest(`/house-models/${editing.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        })
        setNotice('Modelo actualizado')
      } else {
        await apiRequest('/house-models', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        setNotice('Modelo creado')
      }
      setEditing(null)
      setForm(emptyForm)
      setIsModelFormOpen(false)
      await loadData(selectedClientId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar el modelo')
    } finally {
      setSaving(false)
    }
  }

  async function uploadModelDocument(documentType: 'explosion' | 'budget') {
    if (!selectedModelId) return
    const selectedFile = documentType === 'explosion' ? explosionFile : budgetFile
    if (!selectedFile) {
      setDocumentError('Selecciona un PDF antes de cargarlo')
      return
    }
    const body = new FormData()
    body.append('file', selectedFile)
    setUploadingDocumentType(documentType)
    setDocumentError('')
    setNotice('')
    try {
      await apiRequest<HouseModelDocument>(
        `/house-models/${selectedModelId}/documents?document_type=${documentType}`,
        {
          method: 'POST',
          body,
        },
      )
      if (documentType === 'explosion') setExplosionFile(null)
      if (documentType === 'budget') setBudgetFile(null)
      setNotice(documentType === 'explosion' ? 'Explosion cargada' : 'Presupuesto cargado')
      await loadDocuments(selectedModelId)
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : 'No fue posible cargar el documento')
    } finally {
      setUploadingDocumentType('')
    }
  }

  async function updateReviewItem(
    documentType: 'explosion' | 'budget',
    rowId: number,
    payload: Record<string, unknown>,
    successMessage?: string,
  ) {
    if (!selectedModelId) return
    const path =
      documentType === 'explosion'
        ? `/house-models/${selectedModelId}/material-requirements/${rowId}`
        : `/house-models/${selectedModelId}/budget-activities/${rowId}`
    setReviewActionKey(`${documentType}:${rowId}`)
    setDocumentError('')
    try {
      await apiRequest(path, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
      if (successMessage) setNotice(successMessage)
      await loadDocuments(selectedModelId)
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : 'No fue posible actualizar la partida')
    } finally {
      setReviewActionKey('')
    }
  }

  async function createCatalogItem(documentType: 'explosion' | 'budget', rowId: number) {
    if (!selectedModelId) return
    const path =
      documentType === 'explosion'
        ? `/house-models/${selectedModelId}/material-requirements/${rowId}/create-material`
        : `/house-models/${selectedModelId}/budget-activities/${rowId}/create-concept`
    setReviewActionKey(`${documentType}:${rowId}`)
    setDocumentError('')
    try {
      await apiRequest(path, { method: 'POST' })
      setNotice(
        documentType === 'explosion'
          ? 'Material creado y vinculado al catalogo'
          : 'Concepto creado y vinculado al catalogo',
      )
      await loadDocuments(selectedModelId)
      const [materialData, conceptData] = await Promise.all([
        apiRequest<Material[]>('/materials?limit=1000'),
        apiRequest<ConstructionConcept[]>('/construction-concepts?limit=1000'),
      ])
      setMaterials(materialData)
      setConcepts(conceptData)
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : 'No fue posible crear en catalogo')
    } finally {
      setReviewActionKey('')
    }
  }

  async function integratePendingDocumentItems(
    documentType: 'explosion' | 'budget',
    documentId: number,
    pendingCount: number,
  ) {
    if (!selectedModelId || pendingCount === 0) return
    const label = documentType === 'explosion' ? 'materiales' : 'conceptos'
    const confirmed = window.confirm(
      `Vincular todo creara o vinculara ${pendingCount} ${label} pendientes sin revisar cada registro. ` +
        '¿Estas seguro de continuar?',
    )
    if (!confirmed) return
    const path =
      documentType === 'explosion'
        ? `/house-models/${selectedModelId}/documents/${documentId}/integrate-materials`
        : `/house-models/${selectedModelId}/documents/${documentId}/integrate-concepts`
    setReviewActionKey(`${documentType}:bulk`)
    setDocumentError('')
    setNotice('')
    try {
      await apiRequest(path, { method: 'POST' })
      setNotice(
        documentType === 'explosion'
          ? 'Materiales pendientes vinculados al catalogo'
          : 'Conceptos pendientes vinculados al catalogo',
      )
      await loadDocuments(selectedModelId)
      const [materialData, conceptData] = await Promise.all([
        apiRequest<Material[]>('/materials?limit=1000'),
        apiRequest<ConstructionConcept[]>('/construction-concepts?limit=1000'),
      ])
      setMaterials(materialData)
      setConcepts(conceptData)
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : 'No fue posible vincular todo')
    } finally {
      setReviewActionKey('')
    }
  }

  async function deleteModel(model: HouseModel) {
    const confirmed = window.confirm(`Eliminar modelo "${model.name}"?`)
    if (!confirmed) return
    setError('')
    setNotice('')
    try {
      await apiRequest(`/house-models/${model.id}`, { method: 'DELETE' })
      setNotice('Modelo eliminado')
      if (editing?.id === model.id) startCreate()
      await loadData(selectedClientId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible eliminar el modelo')
    }
  }

  return (
    <section className="mx-auto max-w-[1500px] overflow-hidden rounded-md border-2 border-[#8fb4d4] bg-white shadow-[0_20px_50px_rgba(31,66,110,0.18)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#8fb4d4] bg-[linear-gradient(180deg,#ffffff_0%,#e5f0f9_100%)] px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-acsm-green">
            <Home className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-acsm-ink">Modelos por desarrolladora</h2>
            <p className="text-sm text-acsm-muted">
              Selecciona una desarrolladora y administra sus modelos de casa.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void loadData(selectedClientId)}
          disabled={loading}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-acsm-ink hover:bg-slate-50 disabled:opacity-60"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Actualizar
        </button>
      </div>

      <div className="grid min-h-[620px] bg-slate-100/70 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-b border-[#8fb4d4] bg-[#dfeaf3] lg:border-b-0 lg:border-r">
          <div className="border-b border-[#8fb4d4] bg-[#cfdeeb] px-3 py-3">
            <div className="text-xs font-semibold uppercase text-acsm-muted">Desarrolladoras</div>
            <div className="mt-0.5 text-sm font-semibold text-acsm-ink">
              {clients.length} registradas
            </div>
          </div>

          <div className="max-h-[580px] space-y-1.5 overflow-auto p-2">
            {clients.map((client) => {
              const clientModels = models.filter((model) => model.client_id === client.id)
              const isSelected = String(client.id) === selectedClientId
              return (
                <button
                  key={client.id}
                  type="button"
                  onClick={() => selectClient(String(client.id))}
                  className={[
                    'group w-full rounded-md border px-3 py-2 text-left transition',
                    isSelected
                      ? 'border-[#1f5f9d] bg-white shadow-[0_10px_20px_rgba(31,95,157,0.18)]'
                      : 'border-slate-300 bg-white/80 hover:border-blue-300 hover:bg-white',
                  ].join(' ')}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={[
                        'mt-1 h-8 w-1 rounded-full',
                        isSelected ? 'bg-[#1f5f9d]' : 'bg-transparent group-hover:bg-blue-300',
                      ].join(' ')}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-acsm-ink">
                        {client.name}
                      </div>
                      <div className="truncate text-xs text-acsm-muted">
                        {client.contact_name ?? 'Sin contacto'}
                      </div>
                      <div className="mt-2">
                        <span className="rounded-full border border-slate-300 bg-[#edf3f8] px-2 py-0.5 text-[11px] font-semibold text-acsm-muted">
                          {clientModels.length} modelos
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}

            {clients.length === 0 ? (
              <div className="rounded-md border border-dashed border-slate-200 bg-white px-3 py-6 text-center text-sm text-acsm-muted">
                No hay desarrolladoras registradas.
              </div>
            ) : null}
          </div>
        </aside>

        <div className="min-w-0 border-l border-white bg-[#f5f9fd]">
          <div className="border-b border-[#8fb4d4] bg-white px-5 py-3">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-acsm-muted">
                  Desarrolladora seleccionada
                </div>
                <h3 className="mt-0.5 truncate text-lg font-semibold text-acsm-ink">
                  {selectedClient?.name ?? 'Sin seleccion'}
                </h3>
                <p className="mt-0.5 text-xs text-acsm-muted">
                  {selectedClient?.contact_name ?? selectedClient?.contact_email ?? 'Sin contacto capturado'}
                </p>
              </div>
              <div className="grid w-full grid-cols-2 gap-2 sm:w-auto sm:grid-cols-3">
                <div className="rounded-md border border-[#aac5dc] bg-[#f8fbff] px-3 py-1.5 shadow-sm">
                  <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                    Modelos
                  </div>
                  <div className="mt-0.5 text-base font-semibold text-acsm-ink">
                    {selectedModels.length}
                  </div>
                </div>
                <div className="rounded-md border border-[#aac5dc] bg-[#f8fbff] px-3 py-1.5 shadow-sm">
                  <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                    m2 promedio
                  </div>
                  <div className="mt-0.5 text-base font-semibold text-acsm-ink">
                    {selectedModels.length ? formatNumber(totalM2 / selectedModels.length) : '-'}
                  </div>
                </div>
                <div className="rounded-md border border-[#aac5dc] bg-[#f8fbff] px-3 py-1.5 shadow-sm">
                  <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                    m2 total
                  </div>
                  <div className="mt-0.5 text-base font-semibold text-acsm-ink">
                    {formatNumber(totalM2)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="p-5">
            <div className="space-y-4">
            <div className="overflow-hidden rounded-md border-2 border-[#8fb4d4] bg-white shadow-[0_10px_24px_rgba(31,66,110,0.12)]">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#8fb4d4] bg-[#dfeaf5] px-3 py-2">
                <div>
                  <h3 className="text-sm font-semibold text-acsm-ink">Modelos registrados</h3>
                  <p className="text-xs text-acsm-muted">
                    Catalogo de modelos para la desarrolladora seleccionada.
                  </p>
                </div>
                {canCreate ? (
                  <button
                    type="button"
                    onClick={startCreate}
                    className="inline-flex h-8 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-acsm-ink hover:bg-slate-50"
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                    Nuevo
                  </button>
                ) : null}
              </div>

              <div className="divide-y divide-slate-200 bg-white">
                {selectedModels.length ? (
                  selectedModels.map((model) => {
                    const isSelectedModel = String(model.id) === selectedModelId
                    return (
                    <article
                      key={model.id}
                      onClick={() => selectModel(model)}
                      className={[
                        'cursor-pointer px-3 py-3 transition hover:bg-slate-50/70',
                        isSelectedModel
                          ? 'bg-[#f1f8ff] shadow-[inset_4px_0_0_#0b7fbd]'
                          : 'bg-white',
                      ].join(' ')}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h4 className="truncate text-sm font-semibold text-acsm-ink">
                            {model.name}
                          </h4>
                          <p className="mt-0.5 max-w-2xl text-xs text-acsm-muted">
                            {model.description || 'Sin descripcion capturada'}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          {canEdit ? (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                startEdit(model)
                              }}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-acsm-muted hover:bg-slate-50"
                              title="Editar"
                            >
                              <Pencil className="h-4 w-4" aria-hidden="true" />
                            </button>
                          ) : null}
                          {canDelete ? (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation()
                                void deleteModel(model)
                              }}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-red-200 text-red-500 hover:bg-red-50"
                              title="Eliminar"
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
                            </button>
                          ) : null}
                        </div>
                      </div>
                      {isSelectedModel ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span
                            className={[
                              'rounded-full border px-2 py-1 text-[11px] font-semibold',
                              latestExplosion
                                ? 'border-blue-200 bg-blue-50 text-blue-800'
                                : 'border-amber-200 bg-amber-50 text-amber-800',
                            ].join(' ')}
                          >
                            Explosion: {latestExplosion ? `${latestExplosion.total_items} materiales` : 'pendiente'}
                          </span>
                          <span
                            className={[
                              'rounded-full border px-2 py-1 text-[11px] font-semibold',
                              latestBudget
                                ? 'border-blue-200 bg-blue-50 text-blue-800'
                                : 'border-amber-200 bg-amber-50 text-amber-800',
                            ].join(' ')}
                          >
                            Presupuesto: {latestBudget ? `${latestBudget.total_items} actividades` : 'pendiente'}
                          </span>
                        </div>
                      ) : null}
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                        <div className="rounded-md border border-[#aac5dc] bg-white px-3 py-1.5">
                          <div className="text-[10px] font-semibold uppercase text-acsm-muted">m2</div>
                          <div className="mt-0.5 font-semibold text-acsm-ink">
                            {formatNumber(model.construction_m2)}
                          </div>
                        </div>
                        <div className="rounded-md border border-[#aac5dc] bg-white px-3 py-1.5">
                          <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                            Niveles
                          </div>
                          <div className="mt-0.5 font-semibold text-acsm-ink">{model.levels ?? '-'}</div>
                        </div>
                        <div className="rounded-md border border-[#aac5dc] bg-white px-3 py-1.5">
                          <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                            Recamaras
                          </div>
                          <div className="mt-0.5 font-semibold text-acsm-ink">{model.bedrooms ?? '-'}</div>
                        </div>
                        <div className="rounded-md border border-[#aac5dc] bg-white px-3 py-1.5">
                          <div className="text-[10px] font-semibold uppercase text-acsm-muted">Banos</div>
                          <div className="mt-0.5 font-semibold text-acsm-ink">
                            {formatNumber(model.bathrooms)}
                          </div>
                        </div>
                      </div>
                      {isSelectedModel ? (
                        <div className="mt-2 grid grid-cols-1 gap-2 text-xs md:grid-cols-3">
                          <div className="rounded-md border border-[#8fb4d4] bg-white px-3 py-1.5 shadow-sm">
                            <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                              Total explosion
                            </div>
                            <div className="mt-0.5 flex items-center justify-between gap-2">
                              <span className="text-acsm-muted">
                                {latestExplosion ? `${latestExplosion.total_items} partidas` : 'Pendiente'}
                              </span>
                              <span className="font-semibold text-acsm-ink">
                                {formatCurrency(latestExplosion?.total_amount)}
                              </span>
                            </div>
                          </div>
                          <div className="rounded-md border border-[#8fb4d4] bg-white px-3 py-1.5 shadow-sm">
                            <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                              Total presupuesto
                            </div>
                            <div className="mt-0.5 flex items-center justify-between gap-2">
                              <span className="text-acsm-muted">
                                {latestBudget ? `${latestBudget.total_items} partidas` : 'Pendiente'}
                              </span>
                              <span className="font-semibold text-acsm-ink">
                                {formatCurrency(latestBudget?.total_amount)}
                              </span>
                            </div>
                          </div>
                          <div className="rounded-md border border-[#7ba8cc] bg-[#dfeaf5] px-3 py-1.5 shadow-sm">
                            <div className="text-[10px] font-semibold uppercase text-acsm-muted">
                              Total modelo
                            </div>
                            <div className="mt-0.5 flex items-center justify-between gap-2">
                              <span className="text-acsm-muted">Explosion + presupuesto</span>
                              <span className="font-semibold text-acsm-ink">
                                {selectedDocumentTotal ? formatCurrency(selectedDocumentTotal) : '-'}
                              </span>
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </article>
                    )
                  })
                ) : (
                  <div className="px-3 py-12 text-center text-sm text-acsm-muted">
                    Esta desarrolladora aun no tiene modelos. Crea el primer modelo desde el panel derecho.
                  </div>
                )}
              </div>
            </div>

            <div className="overflow-hidden rounded-md border-2 border-[#8fb4d4] bg-white shadow-[0_10px_24px_rgba(31,66,110,0.12)]">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#8fb4d4] bg-[#dfeaf5] px-3 py-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md border border-blue-200 bg-blue-50 text-[#0b7fbd]">
                    <FileText className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-acsm-ink">Documentos del modelo</h3>
                    <p className="text-xs text-acsm-muted">
                      {selectedModel
                        ? `${selectedModel.name}: explosion de materiales y presupuesto de actividades.`
                        : 'Selecciona un modelo para cargar sus documentos.'}
                    </p>
                  </div>
                </div>
                {documentLoading ? (
                  <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-acsm-muted">
                    Cargando
                  </span>
                ) : null}
              </div>

              <div className="grid gap-3 border-b border-slate-200 bg-white p-3 lg:grid-cols-2">
                <div className="rounded-md border border-dashed border-[#7ba8cc] bg-[#f6fbff] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold text-acsm-ink">
                        <FileSpreadsheet className="h-4 w-4 text-[#0b7fbd]" aria-hidden="true" />
                        Explosion de materiales
                      </div>
                      <p className="mt-1 text-xs text-acsm-muted">
                        Insumos, unidades, cantidades, costos e importes por casa.
                      </p>
                    </div>
                    <span className="rounded-full border border-blue-200 bg-white px-2 py-1 text-xs font-semibold text-blue-800">
                      {latestExplosion ? `${latestExplosion.total_items} partidas` : 'Pendiente'}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => setExplosionFile(event.target.files?.[0] ?? null)}
                      disabled={!selectedModelId || uploadingDocumentType !== ''}
                      className="min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => void uploadModelDocument('explosion')}
                      disabled={!selectedModelId || !explosionFile || uploadingDocumentType !== ''}
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#0b6fae] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#07598e] disabled:opacity-60"
                    >
                      <UploadCloud className="h-4 w-4" aria-hidden="true" />
                      {uploadingDocumentType === 'explosion' ? 'Analizando' : 'Cargar'}
                    </button>
                  </div>
                </div>

                <div className="rounded-md border border-dashed border-[#7ba8cc] bg-[#f6fbff] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold text-acsm-ink">
                        <FileText className="h-4 w-4 text-[#0b7fbd]" aria-hidden="true" />
                        Presupuesto de actividades
                      </div>
                      <p className="mt-1 text-xs text-acsm-muted">
                        Conceptos, cantidades, precios unitarios y totales por casa.
                      </p>
                    </div>
                    <span className="rounded-full border border-blue-200 bg-white px-2 py-1 text-xs font-semibold text-blue-800">
                      {latestBudget ? `${latestBudget.total_items} partidas` : 'Pendiente'}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => setBudgetFile(event.target.files?.[0] ?? null)}
                      disabled={!selectedModelId || uploadingDocumentType !== ''}
                      className="min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => void uploadModelDocument('budget')}
                      disabled={!selectedModelId || !budgetFile || uploadingDocumentType !== ''}
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-[#0b6fae] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#07598e] disabled:opacity-60"
                    >
                      <UploadCloud className="h-4 w-4" aria-hidden="true" />
                      {uploadingDocumentType === 'budget' ? 'Analizando' : 'Cargar'}
                    </button>
                  </div>
                </div>
              </div>

              {documentError ? (
                <div className="border-b border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {documentError}
                </div>
              ) : null}

              <div className="space-y-4 p-3">
                <DocumentSummary
                  title="Explosion interpretada"
                  subtitle="Resumen de materiales, familias, cantidades y costo de referencia por casa."
                  catalogLabel="Vincular con material"
                  document={latestExplosion}
                  emptyText="Aun no hay explosion cargada para este modelo."
                  groups={explosionGroups}
                  expanded={expandedDetails.explosion}
                  onToggleExpanded={() =>
                    setExpandedDetails((current) => ({
                      ...current,
                      explosion: !current.explosion,
                    }))
                  }
                  catalogOptions={materialOptions}
                  onLink={(rowId, linkedId) =>
                    void updateReviewItem('explosion', rowId, {
                      material_id: linkedId,
                      validation_status: linkedId ? 'validated' : 'pending',
                    }, linkedId ? 'Material vinculado al catalogo' : 'Material desvinculado')
                  }
                  onCreateCatalogItem={(rowId) => void createCatalogItem('explosion', rowId)}
                  onIntegrateAll={(pendingCount) =>
                    latestExplosion
                      ? void integratePendingDocumentItems('explosion', latestExplosion.id, pendingCount)
                      : undefined
                  }
                  onIgnore={(rowId) =>
                    void updateReviewItem(
                      'explosion',
                      rowId,
                      { material_id: null, validation_status: 'ignored' },
                      'Partida ignorada',
                    )
                  }
                  onRestore={(rowId) =>
                    void updateReviewItem(
                      'explosion',
                      rowId,
                      { validation_status: 'pending' },
                      'Partida reactivada',
                    )
                  }
                  actionBusyKey={reviewActionKey}
                  rows={(latestExplosion?.material_requirements ?? []).map((item, index) => ({
                    id: item.id,
                    order: index + 1,
                    code: item.source_code ?? '-',
                    name: item.description,
                    group: item.family || 'Sin familia',
                    unit: item.unit,
                    quantity: formatNumber(item.quantity_per_house),
                    quantityValue: numberValue(item.quantity_per_house),
                    amount: formatCurrency(item.total_cost_reference),
                    amountValue: numberValue(item.total_cost_reference),
                    status: item.validation_status,
                    linkedId: item.material_id,
                  }))}
                />
                <DocumentSummary
                  title="Presupuesto interpretado"
                  subtitle="Resumen de actividades, capitulos, cantidades y precio de referencia por casa."
                  catalogLabel="Vincular con concepto"
                  document={latestBudget}
                  emptyText="Aun no hay presupuesto cargado para este modelo."
                  groups={budgetGroups}
                  expanded={expandedDetails.budget}
                  onToggleExpanded={() =>
                    setExpandedDetails((current) => ({
                      ...current,
                      budget: !current.budget,
                    }))
                  }
                  catalogOptions={conceptOptions}
                  onLink={(rowId, linkedId) =>
                    void updateReviewItem('budget', rowId, {
                      construction_concept_id: linkedId,
                      validation_status: linkedId ? 'validated' : 'pending',
                    }, linkedId ? 'Concepto vinculado al catalogo' : 'Concepto desvinculado')
                  }
                  onCreateCatalogItem={(rowId) => void createCatalogItem('budget', rowId)}
                  onIntegrateAll={(pendingCount) =>
                    latestBudget
                      ? void integratePendingDocumentItems('budget', latestBudget.id, pendingCount)
                      : undefined
                  }
                  onIgnore={(rowId) =>
                    void updateReviewItem(
                      'budget',
                      rowId,
                      { construction_concept_id: null, validation_status: 'ignored' },
                      'Actividad ignorada',
                    )
                  }
                  onRestore={(rowId) =>
                    void updateReviewItem(
                      'budget',
                      rowId,
                      { validation_status: 'pending' },
                      'Actividad reactivada',
                    )
                  }
                  actionBusyKey={reviewActionKey}
                  rows={(latestBudget?.budget_activities ?? []).map((item, index) => ({
                    id: item.id,
                    order: index + 1,
                    code: item.source_code ?? '-',
                    name: item.description,
                    group: item.chapter_name || item.chapter_code || 'Sin capitulo',
                    unit: item.unit,
                    quantity: formatNumber(item.quantity_per_house),
                    quantityValue: numberValue(item.quantity_per_house),
                    amount: formatCurrency(item.total_price_reference),
                    amountValue: numberValue(item.total_price_reference),
                    status: item.validation_status,
                    linkedId: item.construction_concept_id,
                  }))}
                />
              </div>
            </div>
            </div>
          </div>
        </div>
      </div>

      {isModelFormOpen ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-slate-950/55 px-4 py-8 backdrop-blur-sm">
          <aside className="w-full max-w-2xl rounded-md border border-blue-200 bg-white p-4 shadow-[0_24px_70px_rgba(2,22,45,0.35)]">
              <div className="mb-3 -mx-3 -mt-3 flex items-center justify-between gap-3 border-b border-blue-100 bg-[#eef6ff] px-3 py-3">
                <div>
                  <h3 className="text-sm font-semibold text-acsm-ink">
                    {editing ? 'Editar modelo' : 'Nuevo modelo'}
                  </h3>
                  <p className="text-xs text-acsm-muted">
                    {selectedClient?.name ?? 'Selecciona una desarrolladora'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setIsModelFormOpen(false)
                    setEditing(null)
                    setForm(emptyForm)
                    setError('')
                  }}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-acsm-muted hover:bg-slate-50"
                  title="Cerrar"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-3">
                <label className="block text-sm">
                  <span className="mb-1.5 block font-medium text-acsm-ink">Nombre</span>
                  <input
                    value={form.name}
                    onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                    required
                    className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
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
                    className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                  />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-acsm-ink">m2</span>
                    <input
                      value={form.construction_m2}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, construction_m2: event.target.value }))
                      }
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-acsm-ink">Niveles</span>
                    <input
                      value={form.levels}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, levels: event.target.value }))
                      }
                      type="number"
                      min="0"
                      className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-acsm-ink">Recamaras</span>
                    <input
                      value={form.bedrooms}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, bedrooms: event.target.value }))
                      }
                      type="number"
                      min="0"
                      className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1.5 block font-medium text-acsm-ink">Banos</span>
                    <input
                      value={form.bathrooms}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, bathrooms: event.target.value }))
                      }
                      type="number"
                      min="0"
                      step="0.5"
                      className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                    />
                  </label>
                </div>
                <label className="block text-sm">
                  <span className="mb-1.5 block font-medium text-acsm-ink">Notas base</span>
                  <textarea
                    value={form.base_notes}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, base_notes: event.target.value }))
                    }
                    rows={3}
                    className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                  />
                </label>

                {error ? (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {error}
                  </div>
                ) : null}
                {notice ? (
                  <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
                    {notice}
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={saving || !selectedClientId || (!canCreate && !editing) || (!canEdit && Boolean(editing))}
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:opacity-60"
                >
                  <Check className="h-4 w-4" aria-hidden="true" />
                  {editing ? 'Actualizar modelo' : 'Crear modelo'}
                </button>
              </form>
            </aside>
        </div>
      ) : null}
    </section>
  )
}
