import { FormEvent, useEffect, useState } from 'react'
import { Bell, MailCheck, RefreshCw, Save, Send, Settings, Volume2 } from 'lucide-react'

import { brand } from '../config/brand'
import { useAuth } from '../auth/AuthContext'
import { apiRequest } from '../lib/api'
import { showActionNotice } from '../lib/actionNotice'
import { NOTIFICATION_SETTINGS_UPDATED_EVENT } from '../components/AppLayout'

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

type NotificationSettings = {
  id: number
  company_id: number
  sound_enabled: boolean
  sound_volume: number
  flash_enabled: boolean
  repeat_alert_minutes: number
}

type NotificationForm = {
  sound_enabled: boolean
  sound_volume: string
  flash_enabled: boolean
  repeat_alert_minutes: string
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

const emptyNotificationForm: NotificationForm = {
  sound_enabled: true,
  sound_volume: '45',
  flash_enabled: true,
  repeat_alert_minutes: '5',
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

function fromNotificationSettings(settings: NotificationSettings | null): NotificationForm {
  if (!settings) return { ...emptyNotificationForm }
  return {
    sound_enabled: settings.sound_enabled,
    sound_volume: String(settings.sound_volume),
    flash_enabled: settings.flash_enabled,
    repeat_alert_minutes: String(settings.repeat_alert_minutes),
  }
}

export default function SettingsPage() {
  const { hasPermission } = useAuth()
  const canEditSettings = hasPermission('settings:edit')
  const canTestEmail = hasPermission('settings:test_email')
  const [settings, setSettings] = useState<EmailSettings | null>(null)
  const [form, setForm] = useState<EmailForm>(emptyForm)
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings | null>(null)
  const [notificationForm, setNotificationForm] = useState<NotificationForm>(emptyNotificationForm)
  const [testRecipient, setTestRecipient] = useState('info@acsmcontrol.com')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savingNotifications, setSavingNotifications] = useState(false)

  async function loadSettings() {
    setLoading(true)
    setError('')
    try {
      const [data, notificationData] = await Promise.all([
        apiRequest<EmailSettings | null>('/settings/email'),
        apiRequest<NotificationSettings>('/settings/notifications'),
      ])
      setSettings(data)
      setForm(fromSettings(data))
      setTestRecipient(data?.sender_email ?? emptyForm.sender_email)
      setNotificationSettings(notificationData)
      setNotificationForm(fromNotificationSettings(notificationData))
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

  function patchNotificationForm(patch: Partial<NotificationForm>) {
    setNotificationForm((current) => ({ ...current, ...patch }))
  }

  async function saveEmailSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canEditSettings) {
      setError('No tienes permiso para editar la configuracion.')
      return
    }
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
      const successMessage = 'Configuracion de correo guardada.'
      setMessage(successMessage)
      showActionNotice(successMessage)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar ajustes')
    } finally {
      setSaving(false)
    }
  }

  async function sendTestEmail() {
    if (!canTestEmail) {
      setError('No tienes permiso para probar el correo.')
      return
    }
    setError('')
    setMessage('')
    try {
      const result = await apiRequest<{ ok: boolean; message: string }>('/settings/email/test', {
        method: 'POST',
        body: JSON.stringify({ recipient_email: testRecipient || null }),
      })
      setMessage(result.message)
      showActionNotice(result.message)
      await loadSettings()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible enviar la prueba')
    }
  }

  async function saveNotificationSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canEditSettings) {
      setError('No tienes permiso para editar la configuracion.')
      return
    }
    setSavingNotifications(true)
    setError('')
    setMessage('')
    try {
      const payload = {
        sound_enabled: notificationForm.sound_enabled,
        sound_volume: Number(notificationForm.sound_volume || 0),
        flash_enabled: notificationForm.flash_enabled,
        repeat_alert_minutes: Number(notificationForm.repeat_alert_minutes || 5),
      }
      const data = await apiRequest<NotificationSettings>('/settings/notifications', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setNotificationSettings(data)
      setNotificationForm(fromNotificationSettings(data))
      window.dispatchEvent(new CustomEvent(NOTIFICATION_SETTINGS_UPDATED_EVENT, { detail: data }))
      const successMessage = 'Configuracion de notificaciones guardada.'
      setMessage(successMessage)
      showActionNotice(successMessage)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible guardar notificaciones')
    } finally {
      setSavingNotifications(false)
    }
  }

  return (
    <div className="space-y-5">
      {error && (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
        >
          {error}
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
          <div className="space-y-5">
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
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ sender_name: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Correo remitente
                  <input
                    type="email"
                    value={form.sender_email}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ sender_email: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Responder a
                  <input
                    type="email"
                    value={form.reply_to_email}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ reply_to_email: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Usuario SMTP
                  <input
                    value={form.smtp_username}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ smtp_username: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Servidor SMTP
                  <input
                    value={form.smtp_host}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ smtp_host: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Puerto SMTP
                  <input
                    type="number"
                    value={form.smtp_port}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ smtp_port: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink md:col-span-2">
                  Contrasena SMTP
                  <input
                    type="password"
                    value={form.smtp_password}
                    disabled={!canEditSettings}
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
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ smtp_use_ssl: event.target.checked })}
                  />
                  Usar SSL
                </label>
                <label className="inline-flex items-center gap-2 rounded-xl border border-acsm-line bg-white px-3 py-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={form.smtp_use_tls}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ smtp_use_tls: event.target.checked })}
                  />
                  Usar TLS
                </label>
                <label className="inline-flex items-center gap-2 rounded-xl border border-acsm-line bg-white px-3 py-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    disabled={!canEditSettings}
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
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ imap_host: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Puerto IMAP
                  <input
                    type="number"
                    value={form.imap_port}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ imap_port: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Usuario IMAP
                  <input
                    value={form.imap_username}
                    disabled={!canEditSettings}
                    onChange={(event) => patchForm({ imap_username: event.target.value })}
                    className="mt-1 h-11 w-full rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                </label>
                <label className="text-sm font-semibold text-acsm-ink">
                  Contrasena IMAP
                  <input
                    type="password"
                    value={form.imap_password}
                    disabled={!canEditSettings}
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
                disabled={saving || !canEditSettings}
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-blue-800 to-sky-600 px-5 text-sm font-bold text-white shadow-lg shadow-blue-900/20 hover:from-blue-900 hover:to-sky-700 disabled:opacity-60"
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                {saving ? 'Guardando...' : 'Guardar configuracion'}
              </button>
            </div>
          </form>

          <form
            onSubmit={(event) => void saveNotificationSettings(event)}
            className="rounded-2xl border border-acsm-line bg-white p-4"
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-sky-200 bg-sky-50 text-sky-700">
                  <Bell className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <h3 className="font-bold text-acsm-ink">Alertas del sistema</h3>
                  <p className="text-sm text-acsm-muted">
                    Controla sonido, destello y recordatorios de notificaciones pendientes.
                  </p>
                </div>
              </div>
              <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-bold text-sky-800">
                {notificationSettings ? 'Configurado' : 'Predeterminado'}
              </span>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="rounded-2xl border border-acsm-line bg-slate-50/80 p-4">
                <span className="flex items-center justify-between gap-3 text-sm font-bold text-acsm-ink">
                  Sonido de notificacion
                  <input
                    type="checkbox"
                    checked={notificationForm.sound_enabled}
                    disabled={!canEditSettings}
                    onChange={(event) => patchNotificationForm({ sound_enabled: event.target.checked })}
                  />
                </span>
                <p className="mt-1 text-xs text-acsm-muted">Reproduce un tono corto al detectar nuevas alertas.</p>
              </label>
              <label className="rounded-2xl border border-acsm-line bg-slate-50/80 p-4">
                <span className="flex items-center justify-between gap-3 text-sm font-bold text-acsm-ink">
                  Destello visual
                  <input
                    type="checkbox"
                    checked={notificationForm.flash_enabled}
                    disabled={!canEditSettings}
                    onChange={(event) => patchNotificationForm({ flash_enabled: event.target.checked })}
                  />
                </span>
                <p className="mt-1 text-xs text-acsm-muted">Ilumina la interfaz brevemente cuando llega una alerta.</p>
              </label>
              <label className="text-sm font-semibold text-acsm-ink">
                <span className="mb-2 flex items-center gap-2">
                  <Volume2 className="h-4 w-4 text-sky-700" aria-hidden="true" />
                  Volumen: {notificationForm.sound_volume}%
                </span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={notificationForm.sound_volume}
                  disabled={!canEditSettings || !notificationForm.sound_enabled}
                  onChange={(event) => patchNotificationForm({ sound_volume: event.target.value })}
                  className="w-full"
                />
              </label>
              <label className="text-sm font-semibold text-acsm-ink">
                Repetir alerta cada
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={notificationForm.repeat_alert_minutes}
                    disabled={!canEditSettings}
                    onChange={(event) => patchNotificationForm({ repeat_alert_minutes: event.target.value })}
                    className="h-11 w-28 rounded-xl border border-acsm-line bg-white px-3 text-sm"
                  />
                  <span className="text-sm font-semibold text-acsm-muted">minutos si sigue pendiente</span>
                </div>
              </label>
            </div>

            <div className="mt-4 flex justify-end">
              <button
                type="submit"
                disabled={savingNotifications || !canEditSettings}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-gradient-to-r from-blue-800 to-sky-600 px-4 text-sm font-bold text-white shadow-lg shadow-blue-900/20 hover:from-blue-900 hover:to-sky-700 disabled:opacity-60"
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                {savingNotifications ? 'Guardando...' : 'Guardar alertas'}
              </button>
            </div>
          </form>
          </div>

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
                disabled={!canTestEmail}
                onChange={(event) => setTestRecipient(event.target.value)}
                className="h-11 w-full rounded-xl border border-acsm-line px-3 text-sm"
              />
              <button
                type="button"
                onClick={() => void sendTestEmail()}
                disabled={!canTestEmail}
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
