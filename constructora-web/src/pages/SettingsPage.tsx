import { FormEvent, useEffect, useState } from 'react'
import { MailCheck, RefreshCw, Save, Send, Settings } from 'lucide-react'

import { brand } from '../config/brand'
import { apiRequest } from '../lib/api'

type EmailSettings = {
  id: number
  company_id: number
  sender_name: string
  sender_email: string
  reply_to_email?: string | null
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_password_set: boolean
  smtp_use_ssl: boolean
  smtp_use_tls: boolean
  imap_host?: string | null
  imap_port?: number | null
  imap_username?: string | null
  imap_password_set: boolean
  is_active: boolean
  last_tested_at?: string | null
  last_test_status?: string | null
  last_test_message?: string | null
}

type EmailForm = {
  sender_name: string
  sender_email: string
  reply_to_email: string
  smtp_host: string
  smtp_port: string
  smtp_username: string
  smtp_password: string
  smtp_use_ssl: boolean
  smtp_use_tls: boolean
  imap_host: string
  imap_port: string
  imap_username: string
  imap_password: string
  is_active: boolean
}

const emptyForm: EmailForm = {
  sender_name: 'ACSM Control',
  sender_email: 'info@acsmcontrol.com',
  reply_to_email: 'info@acsmcontrol.com',
  smtp_host: 'smtp.hostinger.com',
  smtp_port: '465',
  smtp_username: 'info@acsmcontrol.com',
  smtp_password: '',
  smtp_use_ssl: true,
  smtp_use_tls: false,
  imap_host: 'imap.hostinger.com',
  imap_port: '993',
  imap_username: 'info@acsmcontrol.com',
  imap_password: '',
  is_active: true,
}

function fromSettings(settings: EmailSettings | null): EmailForm {
  if (!settings) return { ...emptyForm }
  return {
    sender_name: settings.sender_name,
    sender_email: settings.sender_email,
    reply_to_email: settings.reply_to_email ?? '',
    smtp_host: settings.smtp_host,
    smtp_port: String(settings.smtp_port),
    smtp_username: settings.smtp_username,
    smtp_password: '',
    smtp_use_ssl: settings.smtp_use_ssl,
    smtp_use_tls: settings.smtp_use_tls,
    imap_host: settings.imap_host ?? '',
    imap_port: settings.imap_port ? String(settings.imap_port) : '',
    imap_username: settings.imap_username ?? '',
    imap_password: '',
    is_active: settings.is_active,
  }
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<EmailSettings | null>(null)
  const [form, setForm] = useState<EmailForm>(emptyForm)
  const [testRecipient, setTestRecipient] = useState('info@acsmcontrol.com')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  async function loadSettings() {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest<EmailSettings | null>('/settings/email')
      setSettings(data)
      setForm(fromSettings(data))
      setTestRecipient(data?.sender_email ?? emptyForm.sender_email)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible cargar ajustes')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadSettings()
  }, [])

  function patchForm(patch: Partial<EmailForm>) {
    setForm((current) => ({ ...current, ...patch }))
  }

  async function saveEmailSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const payload = {
        ...form,
        reply_to_email: form.reply_to_email || null,
        smtp_port: Number(form.smtp_port || 465),
        smtp_password: form.smtp_password || null,
        imap_host: form.imap_host || null,
        imap_port: form.imap_port ? Number(form.imap_port) : null,
        imap_username: form.imap_username || null,
        imap_password: form.imap_password || null,
      }
      const data = await apiRequest<EmailSettings>('/settings/email', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setSettings(data)
      setForm(fromSettings(data))
      setMessage('Configuracion de correo guardada.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar ajustes')
    } finally {
      setSaving(false)
    }
  }

  async function sendTestEmail() {
    setError('')
    setMessage('')
    try {
      const result = await apiRequest<{ ok: boolean; message: string }>('/settings/email/test', {
        method: 'POST',
        body: JSON.stringify({ recipient_email: testRecipient || null }),
      })
      setMessage(result.message)
      await loadSettings()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la prueba')
    }
  }

  return (
    <div className="space-y-5">
      {(message || error) && (
        <div
          className={[
            'rounded-md border px-4 py-3 text-sm font-semibold',
            error
              ? 'border-red-200 bg-red-50 text-red-700'
              : 'border-blue-200 bg-blue-50 text-blue-800',
          ].join(' ')}
        >
          {error || message}
        </div>
      )}

      <section className="overflow-hidden rounded-[22px] border border-acsm-line bg-white shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-acsm-line bg-gradient-to-r from-white to-sky-50 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-200 bg-blue-50 text-blue-700">
              <Settings className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-acsm-muted">Sistema</p>
              <h2 className="text-lg font-bold text-acsm-ink">Ajustes generales</h2>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void loadSettings()}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-acsm-line bg-white px-4 text-sm font-bold text-acsm-ink shadow-sm hover:bg-blue-50"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {loading ? 'Cargando...' : 'Actualizar'}
          </button>
        </div>

        <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <form onSubmit={(event) => void saveEmailSettings(event)} className="space-y-5">
            <div className="rounded-2xl border border-acsm-line bg-slate-50/70 p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-bold text-acsm-ink">Correo saliente</h3>
                  <p className="text-sm text-acsm-muted">
                    Estos datos se usan para enviar solicitudes de cotizacion a proveedores.
                  </p>
                </div>
                <span
                  className={[
                    'rounded-full px-3 py-1 text-xs font-bold',
                    form.is_active
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-slate-200 text-slate-600',
                  ].join(' ')}
                >
                  {form.is_active ? 'Activo' : 'Inactivo'}
                </span>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm font-semibold text-acsm-ink">
                  Nombre remitente
                  <input
                    value={form.sender_name}
                    onChange={(event) => patchForm({ sender_name: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Correo remitente
                  <input
                    type="email"
                    value={form.sender_email}
                    onChange={(event) => patchForm({ sender_email: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Responder a
                  <input
                    type="email"
                    value={form.reply_to_email}
                    onChange={(event) => patchForm({ reply_to_email: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Usuario SMTP
                  <input
                    value={form.smtp_username}
                    onChange={(event) => patchForm({ smtp_username: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Servidor SMTP
                  <input
                    value={form.smtp_host}
                    onChange={(event) => patchForm({ smtp_host: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Puerto SMTP
                  <input
                    type="number"
                    value={form.smtp_port}
                    onChange={(event) => patchForm({ smtp_port: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink md:col-span-2">
                  Contrasena SMTP
                  <input
                    type="password"
                    value={form.smtp_password}
                    onChange={(event) => patchForm({ smtp_password: event.target.value })}
                    placeholder={
                      settings?.smtp_password_set
                        ? 'Configurada. Deja vacio para conservarla.'
                        : 'Captura la contrasena del correo'
                    }
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
              </div>

              <div className="mt-4 flex flex-wrap gap-4">
                <label className="inline-flex items-center gap-2 rounded-xl border border-acsm-line bg-white px-3 py-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={form.smtp_use_ssl}
                    onChange={(event) => patchForm({ smtp_use_ssl: event.target.checked })}
                  />
                  Usar SSL
                </label>
                <label className="inline-flex items-center gap-2 rounded-xl border border-acsm-line bg-white px-3 py-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={form.smtp_use_tls}
                    onChange={(event) => patchForm({ smtp_use_tls: event.target.checked })}
                  />
                  Usar TLS
                </label>
                <label className="inline-flex items-center gap-2 rounded-xl border border-acsm-line bg-white px-3 py-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(event) => patchForm({ is_active: event.target.checked })}
                  />
                  Configuracion activa
                </label>
              </div>
            </div>

            <div className="rounded-2xl border border-acsm-line bg-white p-4">
              <h3 className="font-bold text-acsm-ink">Correo entrante</h3>
              <p className="mb-4 text-sm text-acsm-muted">
                Preparado para leer respuestas o comprobantes cuando integremos recepcion automatica.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="text-sm font-semibold text-acsm-ink">
                  Servidor IMAP
                  <input
                    value={form.imap_host}
                    onChange={(event) => patchForm({ imap_host: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Puerto IMAP
                  <input
                    type="number"
                    value={form.imap_port}
                    onChange={(event) => patchForm({ imap_port: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Usuario IMAP
                  <input
                    value={form.imap_username}
                    onChange={(event) => patchForm({ imap_username: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Contrasena IMAP
                  <input
                    type="password"
                    value={form.imap_password}
                    onChange={(event) => patchForm({ imap_password: event.target.value })}
                    placeholder={
                      settings?.imap_password_set
                        ? 'Configurada. Deja vacio para conservarla.'
                        : 'Opcional'
                    }
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-blue-800 to-sky-600 px-5 text-sm font-bold text-white shadow-lg shadow-blue-900/20 hover:from-blue-900 hover:to-sky-700 disabled:opacity-60"
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                {saving ? 'Guardando...' : 'Guardar configuracion'}
              </button>
            </div>
          </form>

          <aside className="space-y-4">
            <div className="rounded-2xl border border-acsm-line bg-slate-50/80 p-4">
              <div className="mb-3 flex items-center gap-2">
                <MailCheck className="h-5 w-5 text-blue-700" aria-hidden="true" />
                <h3 className="font-bold text-acsm-ink">Estado</h3>
              </div>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-acsm-muted">Sistema</dt>
                  <dd className="font-semibold">{brand.appName}</dd>
                </div>
                <div>
                  <dt className="text-acsm-muted">Constructora</dt>
                  <dd className="font-semibold">{brand.companyName}</dd>
                </div>
                <div>
                  <dt className="text-acsm-muted">SMTP</dt>
                  <dd className="font-semibold">
                    {settings?.smtp_password_set ? 'Con credenciales' : 'Pendiente de contrasena'}
                  </dd>
                </div>
                <div>
                  <dt className="text-acsm-muted">Ultima prueba</dt>
                  <dd className="font-semibold">
                    {settings?.last_test_status
                      ? `${settings.last_test_status}: ${settings.last_test_message ?? ''}`
                      : 'Sin pruebas registradas'}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="rounded-2xl border border-acsm-line bg-white p-4">
              <h3 className="font-bold text-acsm-ink">Probar envio</h3>
              <p className="mb-3 text-sm text-acsm-muted">
                Envia un correo de prueba usando la configuracion guardada.
              </p>
              <input
                type="email"
                value={testRecipient}
                onChange={(event) => setTestRecipient(event.target.value)}
                className="h-11 w-full rounded-xl border border-acsm-line px-3 text-sm"
              />
              <button
                type="button"
                onClick={() => void sendTestEmail()}
                className="mt-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 text-sm font-bold text-blue-800 hover:bg-blue-100"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
                Enviar prueba
              </button>
            </div>
          </aside>
        </div>
      </section>
    </div>
  )
}
