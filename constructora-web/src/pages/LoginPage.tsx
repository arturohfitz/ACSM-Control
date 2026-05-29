import { FormEvent, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Building2, LockKeyhole, Mail } from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { brand } from '../config/brand'

export default function LoginPage() {
  const { login, user } = useAuth()
  const [email, setEmail] = useState('admin@acsm-control.local')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/'

  if (user) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible iniciar sesion')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen bg-[linear-gradient(135deg,#f7fbff_0%,#e8f0f9_44%,#ffffff_100%)] lg:grid-cols-[minmax(420px,520px)_1fr]">
      <section className="flex min-h-screen items-center justify-center border-r border-acsm-line bg-white px-6 py-10">
        <div className="w-full max-w-sm">
          <div className="mb-10 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-md border border-acsm-line bg-acsm-paper">
              {brand.logoPath ? (
                <img src={brand.logoPath} alt={brand.logoAlt} className="h-8 w-8 object-contain" />
              ) : (
                <Building2 className="h-6 w-6 text-acsm-green" aria-hidden="true" />
              )}
            </div>
            <div>
              <h1 className="text-xl font-semibold text-acsm-ink">{brand.appName}</h1>
              <p className="text-sm text-acsm-muted">{brand.companyName}</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="mb-2 block text-sm font-medium text-acsm-ink" htmlFor="email">
                Correo
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-acsm-muted" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="h-11 w-full rounded-md border border-acsm-line bg-white pl-10 pr-3 text-sm"
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-acsm-ink" htmlFor="password">
                Contrasena
              </label>
              <div className="relative">
                <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-acsm-muted" />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-11 w-full rounded-md border border-acsm-line bg-white pl-10 pr-3 text-sm"
                  autoComplete="current-password"
                  required
                />
              </div>
            </div>

            {error ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={submitting}
              className="h-11 w-full rounded-md bg-acsm-green px-4 text-sm font-semibold text-white transition hover:bg-acsm-green-hover disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? 'Entrando...' : 'Entrar'}
            </button>
          </form>
        </div>
      </section>

      <section className="hidden min-h-screen bg-[linear-gradient(145deg,#0d1f37_0%,#1f4a78_42%,#14385f_66%,#0b1a2f_100%)] lg:block">
        <div className="flex h-full items-end p-12">
          <div className="max-w-xl">
            <p className="text-sm font-medium uppercase tracking-[0.12em] text-blue-100">
              Residencial
            </p>
            <h2 className="mt-4 text-4xl font-semibold leading-tight text-white">
              Control operativo para proyectos, modelos y cotizaciones de obra.
            </h2>
          </div>
        </div>
      </section>
    </main>
  )
}
