import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Check, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'

import { apiRequest } from '../lib/api'

export type FieldType =
  | 'text'
  | 'email'
  | 'password'
  | 'number'
  | 'date'
  | 'textarea'
  | 'select'
  | 'multiselect'
  | 'permission-checklist'
  | 'checkbox'

type FieldValue = string | boolean | string[]
type ResourceItem = Record<string, unknown> & { id: number }

export type FieldConfig = {
  name: string
  label: string
  type?: FieldType
  required?: boolean
  readOnly?: boolean
  valueType?: 'string' | 'number' | 'boolean'
  defaultValue?: string | boolean | string[]
  options?: { label: string; value: string }[]
  relation?: {
    endpoint: string
    labelField: string
    valueField?: string
    formatLabel?: (item: ResourceItem) => string
  }
  valueFromItem?: (item: ResourceItem) => string[]
  step?: string
}

export type ResourceConfig = {
  title: string
  endpoint: string
  createEndpoint?: string
  permissionName: string
  moduleLabel?: string
  createModuleLabel?: string
  editModuleLabel?: string
  fields: FieldConfig[]
  createFields?: FieldConfig[]
  columns: string[]
  columnLabels?: Record<string, string>
}

function emptyValues(fields: FieldConfig[]) {
  return Object.fromEntries(
    fields
      .filter((field) => !field.readOnly)
      .map((field) => [
        field.name,
        field.defaultValue ??
          (field.type === 'checkbox'
            ? false
            : field.type === 'multiselect' || field.type === 'permission-checklist'
              ? []
              : ''),
      ]),
  ) as Record<string, FieldValue>
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'Si' : 'No'
  if (typeof value === 'object') return ''
  return String(value)
}

function castValue(field: FieldConfig, value: FieldValue) {
  if (field.type === 'multiselect' || field.type === 'permission-checklist') {
    const selected = Array.isArray(value) ? value : []
    return selected.map((item) =>
      field.valueType === 'number' || field.type === 'number' ? Number(item) : item,
    )
  }
  if (field.type === 'checkbox' || field.valueType === 'boolean') return Boolean(value)
  if (value === '') return null
  if (field.valueType === 'number' || field.type === 'number') return Number(value)
  return value
}

function selectedValues(value: FieldValue | undefined) {
  return Array.isArray(value) ? value : []
}

const permissionModuleLabels: Record<string, string> = {
  companies: 'Constructoras',
  settings: 'Ajustes',
  users: 'Usuarios',
  roles: 'Roles',
  clients: 'Desarrolladoras',
  projects: 'Desarrollos',
  house_models: 'Modelos',
  materials: 'Materiales',
  labor: 'Mano de obra',
  construction_concepts: 'Conceptos',
  quotes: 'Cotizaciones',
  inventory: 'Inventario',
  suppliers: 'Proveedores',
  supplier_rfq: 'Solicitudes de cotizacion',
  supplier_quotes: 'Cotizaciones de proveedores',
  purchase_orders: 'Ordenes de compra',
  supplier_invoices: 'Facturas de proveedores',
  supplier_payments: 'Pagos a proveedores',
}

const permissionActionLabels: Record<string, string> = {
  view: 'Ver',
  create: 'Crear',
  edit: 'Editar',
  delete: 'Eliminar',
  approve: 'Aprobar',
  send: 'Enviar',
  cancel: 'Cancelar',
  compare: 'Comparar',
  upload: 'Cargar',
  validate: 'Validar',
  reject: 'Rechazar',
  schedule: 'Programar pago',
  pay: 'Pagar',
  receive: 'Recibir material',
  view_costs: 'Ver costos',
  view_profit: 'Ver utilidad',
  test_email: 'Probar correo',
  request_approval: 'Solicitar aprobacion',
}

function PermissionChecklist({
  field,
  options,
  value,
  onChange,
}: {
  field: FieldConfig
  options: { label: string; value: string }[]
  value: string[]
  onChange: (value: string[]) => void
}) {
  const selected = new Set(value)
  const groups = useMemo(() => {
    return options.reduce<Record<string, { label: string; value: string }[]>>((current, option) => {
      const code = option.label.match(/\(([^)]+)\)$/)?.[1] ?? ''
      const moduleName = code.split(':')[0] || 'otros'
      current[moduleName] = [...(current[moduleName] ?? []), option]
      return current
    }, {})
  }, [options])

  function toggle(permissionId: string) {
    const next = new Set(selected)
    if (next.has(permissionId)) next.delete(permissionId)
    else next.add(permissionId)
    onChange(Array.from(next))
  }

  function setGroup(groupOptions: { value: string }[], checked: boolean) {
    const next = new Set(selected)
    groupOptions.forEach((option) => {
      if (checked) next.add(option.value)
      else next.delete(option.value)
    })
    onChange(Array.from(next))
  }

  return (
    <div className="rounded-md border border-acsm-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-acsm-line px-3 py-2">
        <span className="text-xs font-semibold uppercase text-acsm-muted">{field.label}</span>
        <span className="rounded-full bg-acsm-paper px-2 py-1 text-xs font-semibold text-acsm-muted">
          {value.length} seleccionados
        </span>
      </div>
      <div className="max-h-[420px] space-y-3 overflow-auto p-3">
        {Object.entries(groups).map(([moduleName, groupOptions]) => {
          const checkedCount = groupOptions.filter((option) => selected.has(option.value)).length
          return (
            <section key={moduleName} className="rounded-md border border-acsm-line bg-acsm-paper/70">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-acsm-line px-3 py-2">
                <div>
                  <h3 className="text-sm font-semibold text-acsm-ink">
                    {permissionModuleLabels[moduleName] ?? moduleName}
                  </h3>
                  <p className="text-xs text-acsm-muted">
                    {checkedCount} de {groupOptions.length} funciones
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setGroup(groupOptions, true)}
                    className="inline-flex h-8 items-center rounded-md border border-acsm-line bg-white px-2 text-xs font-semibold text-acsm-ink hover:bg-acsm-paper"
                  >
                    Todo
                  </button>
                  <button
                    type="button"
                    onClick={() => setGroup(groupOptions, false)}
                    className="inline-flex h-8 items-center rounded-md border border-acsm-line bg-white px-2 text-xs font-semibold text-acsm-muted hover:bg-acsm-paper"
                  >
                    Ninguno
                  </button>
                </div>
              </div>
              <div className="grid gap-1 p-2">
                {groupOptions.map((option) => {
                  const code = option.label.match(/\(([^)]+)\)$/)?.[1] ?? ''
                  const action = code.split(':')[1] ?? option.label
                  const checked = selected.has(option.value)
                  return (
                    <label
                      key={option.value}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-white"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(option.value)}
                        className="h-4 w-4 rounded border-acsm-line accent-acsm-green"
                      />
                      <span className="font-medium text-acsm-ink">
                        {permissionActionLabels[action] ?? option.label.replace(/\s*\([^)]+\)$/, '')}
                      </span>
                      <span className="ml-auto text-xs text-acsm-muted">{code}</span>
                    </label>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}

function payloadFromValues(fields: FieldConfig[], values: Record<string, FieldValue>) {
  return Object.fromEntries(
    fields
      .filter((field) => !field.readOnly)
      .map((field) => [field.name, castValue(field, values[field.name])]),
  )
}

export default function ResourcePage({ config }: { config: ResourceConfig }) {
  const [editing, setEditing] = useState<ResourceItem | null>(null)
  const editableFields = useMemo(
    () => config.fields.filter((field) => !field.readOnly),
    [config.fields],
  )
  const createEditableFields = useMemo(
    () => (config.createFields ?? config.fields).filter((field) => !field.readOnly),
    [config.createFields, config.fields],
  )
  const formFields = editing ? editableFields : createEditableFields
  const fieldsByName = useMemo(
    () =>
      Object.fromEntries(
        [...config.fields, ...(config.createFields ?? [])].map((field) => [field.name, field]),
      ),
    [config.createFields, config.fields],
  )
  const [items, setItems] = useState<ResourceItem[]>([])
  const [values, setValues] = useState<Record<string, FieldValue>>(() =>
    emptyValues(config.createFields ?? config.fields),
  )
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [relationOptions, setRelationOptions] = useState<
    Record<string, { label: string; value: string }[]>
  >({})

  async function loadItems() {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest<ResourceItem[]>(config.endpoint)
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar registros')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadItems()
  }, [config.endpoint])

  useEffect(() => {
    const relationFields = formFields.filter((field) => field.relation)
    if (relationFields.length === 0) {
      setRelationOptions({})
      return
    }

    async function loadRelationOptions() {
      const entries = await Promise.all(
        relationFields.map(async (field) => {
          try {
            const relation = field.relation!
            const data = await apiRequest<ResourceItem[]>(relation.endpoint)
            const options = data.map((item) => ({
              value: String(item[relation.valueField ?? 'id']),
              label:
                relation.formatLabel?.(item) ??
                (formatValue(item[relation.labelField]) || `#${item.id}`),
            }))
            return [field.name, options] as const
          } catch {
            return [field.name, []] as const
          }
        }),
      )
      setRelationOptions(Object.fromEntries(entries))
    }

    void loadRelationOptions()
  }, [formFields])

  function startCreate() {
    setEditing(null)
    setValues(emptyValues(config.createFields ?? config.fields))
    setNotice('')
    setError('')
  }

  function valuesFromItem(item: ResourceItem) {
    return Object.fromEntries(
      editableFields.map((field) => {
        if (field.type === 'multiselect' || field.type === 'permission-checklist') {
          return [field.name, field.valueFromItem?.(item) ?? []]
        }
        const raw = item[field.name]
        if (field.type === 'checkbox') return [field.name, Boolean(raw)]
        return [field.name, raw === null || raw === undefined ? '' : String(raw)]
      }),
    ) as Record<string, FieldValue>
  }

  async function startEdit(item: ResourceItem) {
    const needsFullRecord = editableFields.some((field) => field.valueFromItem)
    setNotice('')
    setError('')

    let itemToEdit = item
    if (needsFullRecord) {
      try {
        itemToEdit = await apiRequest<ResourceItem>(`${config.endpoint}/${item.id}`)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'No fue posible cargar el registro')
        return
      }
    }

    setEditing(itemToEdit)
    setValues(
      valuesFromItem(itemToEdit),
    )
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const currentFields = editing ? config.fields : config.createFields ?? config.fields
      const payload = payloadFromValues(currentFields, values)
      if (editing) {
        await apiRequest(`${config.endpoint}/${editing.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        })
        setNotice('Registro actualizado')
      } else {
        await apiRequest(config.createEndpoint ?? config.endpoint, {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        setNotice('Registro creado')
      }
      startCreate()
      await loadItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(item: ResourceItem) {
    const confirmed = window.confirm('Eliminar registro?')
    if (!confirmed) return

    setError('')
    setNotice('')
    try {
      await apiRequest(`${config.endpoint}/${item.id}`, { method: 'DELETE' })
      setNotice('Registro eliminado')
      await loadItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible eliminar')
    }
  }

  function columnLabel(column: string) {
    return config.columnLabels?.[column] ?? fieldsByName[column]?.label ?? column
  }

  function columnValue(column: string, value: unknown) {
    const field = fieldsByName[column]
    if (field?.options) {
      const option = field.options.find((item) => item.value === String(value))
      return option?.label ?? formatValue(value)
    }
    if (field?.relation) {
      const option = relationOptions[column]?.find((item) => item.value === String(value))
      return option?.label ?? formatValue(value)
    }
    return formatValue(value)
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(320px,380px)_1fr]">
      <section className="rounded-md border border-acsm-line bg-white p-4 shadow-panel">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">{editing ? 'Editar' : 'Nuevo'}</h2>
            <p className="text-sm text-acsm-muted">
              {editing
                ? config.editModuleLabel ?? config.moduleLabel ?? config.title
                : config.createModuleLabel ?? config.moduleLabel ?? config.title}
            </p>
          </div>
          {editing ? (
            <button
              type="button"
              onClick={startCreate}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line text-acsm-muted hover:bg-acsm-paper"
              title="Cancelar edicion"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : (
            <Plus className="h-5 w-5 text-acsm-green" aria-hidden="true" />
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {formFields.map((field) => (
            <label key={field.name} className="block text-sm">
              <span className="mb-1.5 block font-medium text-acsm-ink">{field.label}</span>
              {field.type === 'textarea' ? (
                <textarea
                  value={String(values[field.name] ?? '')}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                  required={field.required}
                  rows={3}
                  className="w-full rounded-md border border-acsm-line bg-white px-3 py-2 text-sm"
                />
              ) : field.type === 'permission-checklist' ? (
                <PermissionChecklist
                  field={field}
                  options={field.options ?? relationOptions[field.name] ?? []}
                  value={selectedValues(values[field.name])}
                  onChange={(nextValue) =>
                    setValues((current) => ({ ...current, [field.name]: nextValue }))
                  }
                />
              ) : field.type === 'multiselect' ? (
                <select
                  multiple
                  value={selectedValues(values[field.name])}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      [field.name]: Array.from(event.target.selectedOptions).map(
                        (option) => option.value,
                      ),
                    }))
                  }
                  required={field.required}
                  className="min-h-28 w-full rounded-md border border-acsm-line bg-white px-3 py-2 text-sm"
                >
                  {(field.options ?? relationOptions[field.name] ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : field.type === 'select' || field.relation ? (
                <select
                  value={String(values[field.name] ?? '')}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                  required={field.required}
                  className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
                >
                  <option value="">Seleccionar</option>
                  {(field.options ?? relationOptions[field.name] ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : field.type === 'checkbox' ? (
                <input
                  type="checkbox"
                  checked={Boolean(values[field.name])}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.checked }))
                  }
                  className="h-4 w-4 rounded border-acsm-line text-acsm-green"
                />
              ) : (
                <input
                  type={field.type ?? 'text'}
                  value={String(values[field.name] ?? '')}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                  required={field.required}
                  step={field.step}
                  className="h-10 w-full rounded-md border border-acsm-line bg-white px-3 text-sm"
                />
              )}
            </label>
          ))}

          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}
          {notice ? (
            <div className="rounded-md border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm text-zinc-700">
              {notice}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={saving}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover disabled:cursor-not-allowed disabled:opacity-70"
          >
            <Check className="h-4 w-4" aria-hidden="true" />
            {saving ? 'Guardando...' : editing ? 'Actualizar' : 'Crear'}
          </button>
        </form>
      </section>

      <section className="min-w-0 rounded-md border border-acsm-line bg-white shadow-panel">
        <div className="flex h-14 items-center justify-between gap-3 border-b border-acsm-line px-4">
          <h2 className="text-base font-semibold">{config.title}</h2>
          <button
            type="button"
            onClick={loadItems}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-acsm-line text-acsm-muted hover:bg-acsm-paper"
            title="Actualizar"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead className="bg-acsm-paper text-left text-xs uppercase text-acsm-muted">
              <tr>
                {config.columns.map((column) => (
                  <th key={column} className="border-b border-acsm-line px-4 py-3 font-semibold">
                    {columnLabel(column)}
                  </th>
                ))}
                <th className="border-b border-acsm-line px-4 py-3 text-right font-semibold">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={config.columns.length + 1} className="px-4 py-8 text-center text-acsm-muted">
                    Cargando...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={config.columns.length + 1} className="px-4 py-8 text-center text-acsm-muted">
                    Sin registros
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id} className="border-b border-acsm-line last:border-0">
                    {config.columns.map((column) => (
                      <td key={column} className="max-w-[220px] truncate px-4 py-3">
                        {columnValue(column, item[column])}
                      </td>
                    ))}
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => startEdit(item)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-acsm-line text-acsm-muted hover:bg-acsm-paper"
                          title="Editar"
                        >
                          <Pencil className="h-4 w-4" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(item)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-red-200 text-red-600 hover:bg-red-50"
                          title="Eliminar"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
