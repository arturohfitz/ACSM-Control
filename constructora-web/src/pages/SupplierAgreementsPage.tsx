import { useEffect, useMemo, useState } from 'react'
import { Check, Handshake, Plus, RefreshCw } from 'lucide-react'

import { apiRequest } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'
import FormDrawer from '../components/FormDrawer'

type Supplier = {
  id: number
  name: string
  payment_terms_days: number
  average_delivery_days?: number | null
}

type Client = {
  id: number
  name: string
}

type HouseModel = {
  id: number
  client_id: number
  name: string
  construction_m2: string
}

type SupplierAgreement = {
  id: number
  supplier_id: number
  client_id: number
  house_model_id: number
  agreement_number?: string | null
  name: string
  status: string
  valid_from?: string | null
  valid_until?: string | null
  payment_terms_days?: number | null
  average_delivery_days?: number | null
  notes?: string | null
  supplier?: Supplier | null
}

const emptyAgreement = {
  supplier_id: '',
  client_id: '',
  house_model_id: '',
  agreement_number: '',
  name: '',
  valid_from: '',
  valid_until: '',
  payment_terms_days: '30',
  average_delivery_days: '',
  notes: '',
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    active: 'Activo',
    suspended: 'Suspendido',
    expired: 'Vencido',
  }
  return labels[status] ?? status
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return value
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  )
}

export default function SupplierAgreementsPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [houseModels, setHouseModels] = useState<HouseModel[]>([])
  const [agreements, setAgreements] = useState<SupplierAgreement[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [agreementForm, setAgreementForm] = useState({ ...emptyAgreement })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)

  const selectedAgreement = useMemo(
    () => agreements.find((agreement) => agreement.id === selectedId) ?? agreements[0] ?? null,
    [agreements, selectedId],
  )

  const filteredModels = useMemo(
    () =>
      houseModels.filter((model) =>
        agreementForm.client_id ? model.client_id === Number(agreementForm.client_id) : true,
      ),
    [agreementForm.client_id, houseModels],
  )

  const supplierById = useMemo(
    () => new Map(suppliers.map((supplier) => [supplier.id, supplier])),
    [suppliers],
  )
  const clientById = useMemo(() => new Map(clients.map((client) => [client.id, client])), [clients])
  const modelById = useMemo(() => new Map(houseModels.map((model) => [model.id, model])), [houseModels])

  async function loadData(nextId = selectedAgreement?.id) {
    setLoading(true)
    setError('')
    try {
      const [supplierData, clientData, modelData, agreementData] = await Promise.all([
        apiRequest<Supplier[]>('/purchasing/suppliers'),
        apiRequest<Client[]>('/clients'),
        apiRequest<HouseModel[]>('/house-models'),
        apiRequest<SupplierAgreement[]>('/purchasing/supplier-agreements?limit=250'),
      ])
      setSuppliers(supplierData)
      setClients(clientData)
      setHouseModels(modelData)
      setAgreements(agreementData)
      setSelectedId(nextId ?? agreementData[0]?.id ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar convenios')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  function updateAgreementField(name: keyof typeof agreementForm, value: string) {
    setAgreementForm((current) => {
      const next = { ...current, [name]: value }
      if (name === 'client_id') next.house_model_id = ''
      return next
    })
  }

  function startCreateAgreement() {
    setAgreementForm({ ...emptyAgreement })
    setError('')
    setDrawerOpen(true)
  }

  function closeDrawer() {
    setDrawerOpen(false)
    setError('')
  }

  async function createAgreement() {
    setError('')
    if (!agreementForm.supplier_id || !agreementForm.client_id || !agreementForm.house_model_id) {
      setError('Selecciona proveedor, inmobiliaria y modelo.')
      return
    }
    try {
      const supplier = supplierById.get(Number(agreementForm.supplier_id))
      const client = clientById.get(Number(agreementForm.client_id))
      const model = modelById.get(Number(agreementForm.house_model_id))
      const created = await apiRequest<SupplierAgreement>('/purchasing/supplier-agreements', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: Number(agreementForm.supplier_id),
          client_id: Number(agreementForm.client_id),
          house_model_id: Number(agreementForm.house_model_id),
          agreement_number: agreementForm.agreement_number || null,
          name:
            agreementForm.name ||
            `Convenio ${supplier?.name ?? 'Proveedor'} - ${client?.name ?? 'Inmobiliaria'} - ${model?.name ?? 'Modelo'}`,
          status: 'active',
          valid_from: agreementForm.valid_from || null,
          valid_until: agreementForm.valid_until || null,
          payment_terms_days: Number(agreementForm.payment_terms_days || 30),
          average_delivery_days: agreementForm.average_delivery_days
            ? Number(agreementForm.average_delivery_days)
            : null,
          notes: agreementForm.notes || null,
        }),
      })
      setAgreementForm({ ...emptyAgreement })
      setDrawerOpen(false)
      showActionNotice('Convenio creado. Ya puede usarse para cotizacion directa.', 'success')
      await loadData(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible crear el convenio')
    }
  }

  const selectedSupplier = selectedAgreement ? supplierById.get(selectedAgreement.supplier_id) : null
  const selectedClient = selectedAgreement ? clientById.get(selectedAgreement.client_id) : null
  const selectedModel = selectedAgreement ? modelById.get(selectedAgreement.house_model_id) : null

  return (
    <div className="mx-auto max-w-[1680px] px-4 py-8">
      {error ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      ) : null}
      <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">Compras</p>
            <h2 className="text-xl font-bold text-acsm-ink">Convenios de proveedores</h2>
            <p className="text-sm text-acsm-muted">
              Marca proveedores con convenio por inmobiliaria y modelo. No requiere capturar materiales.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={startCreateAgreement}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-acsm-green px-4 text-sm font-bold text-white shadow-button hover:bg-acsm-green-hover"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Nuevo convenio
            </button>
            <button
              type="button"
              onClick={() => void loadData()}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink hover:bg-acsm-paper"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Actualizar
            </button>
          </div>
        </div>

        <div className="grid gap-0 xl:grid-cols-[minmax(360px,0.8fr)_minmax(0,1fr)]">
          <div className="border-r border-acsm-line bg-white">
            <div className="border-b border-acsm-line px-4 py-3">
              <h3 className="font-bold text-acsm-ink">Convenios registrados</h3>
              <p className="text-xs text-acsm-muted">{agreements.length} convenios</p>
            </div>
            <div className="max-h-[650px] divide-y divide-acsm-line overflow-y-auto">
              {agreements.map((agreement) => {
                const supplier = supplierById.get(agreement.supplier_id)
                const client = clientById.get(agreement.client_id)
                const model = modelById.get(agreement.house_model_id)
                return (
                  <button
                    key={agreement.id}
                    type="button"
                    onClick={() => setSelectedId(agreement.id)}
                    className={[
                      'block w-full px-4 py-4 text-left hover:bg-sky-50',
                      selectedAgreement?.id === agreement.id ? 'bg-sky-50 ring-1 ring-inset ring-acsm-blue' : '',
                    ].join(' ')}
                  >
                    <div className="font-bold text-acsm-ink">{agreement.name}</div>
                    <div className="mt-1 text-xs text-acsm-muted">
                      {supplier?.name ?? 'Proveedor'} · {client?.name ?? 'Inmobiliaria'} · {model?.name ?? 'Modelo'}
                    </div>
                    <span className="mt-2 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-700">
                      {statusLabel(agreement.status)}
                    </span>
                  </button>
                )
              })}
              {!agreements.length ? (
                <div className="px-4 py-8 text-center text-sm text-acsm-muted">
                  Sin convenios registrados.
                </div>
              ) : null}
            </div>
          </div>

          <div className="min-w-0 bg-white p-5">
            {selectedAgreement ? (
              <div className="rounded-2xl border border-acsm-line bg-gradient-to-br from-white to-sky-50 p-5">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-blue-200 bg-blue-50 text-acsm-blue">
                    <Handshake className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-acsm-muted">
                      Convenio seleccionado
                    </p>
                    <h3 className="text-2xl font-bold text-acsm-ink">{selectedAgreement.name}</h3>
                    <p className="text-sm text-acsm-muted">
                      Este proveedor puede recibir cotizacion directa para el modelo seleccionado.
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <div className="rounded-xl border border-acsm-line bg-white p-4">
                    <span className="text-xs font-bold uppercase text-acsm-muted">Proveedor</span>
                    <div className="mt-1 font-bold text-acsm-ink">{selectedSupplier?.name ?? 'Proveedor'}</div>
                  </div>
                  <div className="rounded-xl border border-acsm-line bg-white p-4">
                    <span className="text-xs font-bold uppercase text-acsm-muted">Inmobiliaria</span>
                    <div className="mt-1 font-bold text-acsm-ink">{selectedClient?.name ?? 'Inmobiliaria'}</div>
                  </div>
                  <div className="rounded-xl border border-acsm-line bg-white p-4">
                    <span className="text-xs font-bold uppercase text-acsm-muted">Modelo</span>
                    <div className="mt-1 font-bold text-acsm-ink">{selectedModel?.name ?? 'Modelo'}</div>
                  </div>
                  <div className="rounded-xl border border-acsm-line bg-white p-4">
                    <span className="text-xs font-bold uppercase text-acsm-muted">Credito</span>
                    <div className="mt-1 font-bold text-acsm-ink">
                      {selectedAgreement.payment_terms_days ?? selectedSupplier?.payment_terms_days ?? 0} dias
                    </div>
                  </div>
                  <div className="rounded-xl border border-acsm-line bg-white p-4">
                    <span className="text-xs font-bold uppercase text-acsm-muted">Entrega</span>
                    <div className="mt-1 font-bold text-acsm-ink">
                      {selectedAgreement.average_delivery_days ?? selectedSupplier?.average_delivery_days ?? '-'} dias
                    </div>
                  </div>
                  <div className="rounded-xl border border-acsm-line bg-white p-4">
                    <span className="text-xs font-bold uppercase text-acsm-muted">Vigencia</span>
                    <div className="mt-1 font-bold text-acsm-ink">
                      {formatDate(selectedAgreement.valid_from)} - {formatDate(selectedAgreement.valid_until)}
                    </div>
                  </div>
                </div>

                {selectedAgreement.notes ? (
                  <div className="mt-4 rounded-xl border border-acsm-line bg-white p-4">
                    <span className="text-xs font-bold uppercase text-acsm-muted">Notas</span>
                    <p className="mt-1 text-sm text-acsm-ink">{selectedAgreement.notes}</p>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-acsm-line bg-acsm-paper p-10 text-center text-acsm-muted">
                Crea o selecciona un convenio para ver su detalle.
              </div>
            )}
          </div>
        </div>
      </section>

      <FormDrawer
        open={drawerOpen}
        title="Nuevo convenio"
        description="Proveedor, inmobiliaria y modelo para cotizacion directa."
        onClose={closeDrawer}
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={closeDrawer}
              className="inline-flex h-10 items-center justify-center rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-muted hover:bg-acsm-paper"
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="agreement-drawer-form"
              disabled={loading}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-acsm-green px-5 text-sm font-bold text-white hover:bg-acsm-green-hover disabled:opacity-60"
            >
              <Check className="h-4 w-4" aria-hidden="true" />
              Guardar
            </button>
          </div>
        }
      >
        <form
          id="agreement-drawer-form"
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            void createAgreement()
          }}
        >
          <select
            value={agreementForm.supplier_id}
            onChange={(event) => updateAgreementField('supplier_id', event.target.value)}
            className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
            required
          >
            <option value="">Proveedor</option>
            {suppliers.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
              </option>
            ))}
          </select>
          <select
            value={agreementForm.client_id}
            onChange={(event) => updateAgreementField('client_id', event.target.value)}
            className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
            required
          >
            <option value="">Inmobiliaria</option>
            {clients.map((client) => (
              <option key={client.id} value={client.id}>
                {client.name}
              </option>
            ))}
          </select>
          <select
            value={agreementForm.house_model_id}
            onChange={(event) => updateAgreementField('house_model_id', event.target.value)}
            className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
            required
          >
            <option value="">Modelo de casa</option>
            {filteredModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
          <input
            value={agreementForm.name}
            onChange={(event) => updateAgreementField('name', event.target.value)}
            placeholder="Nombre del convenio opcional"
            className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
          />
          <input
            value={agreementForm.agreement_number}
            onChange={(event) => updateAgreementField('agreement_number', event.target.value)}
            placeholder="Referencia o folio opcional"
            className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              type="date"
              value={agreementForm.valid_from}
              onChange={(event) => updateAgreementField('valid_from', event.target.value)}
              className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
            />
            <input
              type="date"
              value={agreementForm.valid_until}
              onChange={(event) => updateAgreementField('valid_until', event.target.value)}
              className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="number"
              value={agreementForm.payment_terms_days}
              onChange={(event) => updateAgreementField('payment_terms_days', event.target.value)}
              placeholder="Credito dias"
              className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
            />
            <input
              type="number"
              value={agreementForm.average_delivery_days}
              onChange={(event) => updateAgreementField('average_delivery_days', event.target.value)}
              placeholder="Entrega dias"
              className="h-10 w-full rounded-xl border border-acsm-line bg-white px-3"
            />
          </div>
          <textarea
            value={agreementForm.notes}
            onChange={(event) => updateAgreementField('notes', event.target.value)}
            placeholder="Notas del convenio"
            className="min-h-24 w-full rounded-xl border border-acsm-line bg-white px-3 py-2"
          />
          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </form>
      </FormDrawer>
    </div>
  )
}
