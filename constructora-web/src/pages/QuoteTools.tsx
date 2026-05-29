import { FormEvent, useState } from 'react'
import { BadgeCheck, Calculator } from 'lucide-react'

import { apiRequest } from '../lib/api'

export default function QuoteTools() {
  const [projectId, setProjectId] = useState('')
  const [quoteId, setQuoteId] = useState('')
  const [profitPercent, setProfitPercent] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setResult('')
    try {
      const data = await apiRequest(`/quotes/calculate/project/${projectId}`, {
        method: 'POST',
        body: JSON.stringify({
          profit_percent: profitPercent ? Number(profitPercent) : null,
        }),
      })
      setResult(JSON.stringify(data, null, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible calcular')
    }
  }

  async function approve() {
    setError('')
    setResult('')
    try {
      const data = await apiRequest(`/quotes/${quoteId}/approve`, { method: 'POST' })
      setResult(JSON.stringify(data, null, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No fue posible aprobar')
    }
  }

  return (
    <section className="mb-5 rounded-md border border-acsm-line bg-white p-4 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold">Calculo</h2>
        <Calculator className="h-4 w-4 text-acsm-green" aria-hidden="true" />
      </div>

      <form onSubmit={calculate} className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <input
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          placeholder="Desarrollo ID"
          type="number"
          required
          className="h-10 rounded-md border border-acsm-line px-3 text-sm"
        />
        <input
          value={profitPercent}
          onChange={(event) => setProfitPercent(event.target.value)}
          placeholder="Utilidad decimal"
          type="number"
          min="0"
          step="0.0001"
          className="h-10 rounded-md border border-acsm-line px-3 text-sm"
        />
        <button
          type="submit"
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-acsm-green px-4 text-sm font-semibold text-white hover:bg-acsm-green-hover"
        >
          <Calculator className="h-4 w-4" aria-hidden="true" />
          Calcular
        </button>
      </form>

      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
        <input
          value={quoteId}
          onChange={(event) => setQuoteId(event.target.value)}
          placeholder="Cotizacion ID"
          type="number"
          className="h-10 rounded-md border border-acsm-line px-3 text-sm"
        />
        <button
          type="button"
          onClick={approve}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-acsm-line px-4 text-sm font-semibold text-acsm-ink hover:bg-acsm-paper"
        >
          <BadgeCheck className="h-4 w-4" aria-hidden="true" />
          Aprobar
        </button>
      </div>

      {error ? (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {result ? (
        <pre className="mt-3 max-h-52 overflow-auto rounded-md border border-acsm-line bg-acsm-paper p-3 text-xs">
          {result}
        </pre>
      ) : null}
    </section>
  )
}
