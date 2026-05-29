import { Calculator, FolderKanban, Hammer, Package, Users } from 'lucide-react'

const metrics = [
  { label: 'Desarrollos', value: '0', icon: FolderKanban },
  { label: 'Cotizaciones', value: '0', icon: Calculator },
  { label: 'Materiales', value: '0', icon: Package },
  { label: 'Mano de obra', value: '0', icon: Hammer },
  { label: 'Usuarios', value: '0', icon: Users },
]

export default function DashboardPage() {
  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-md border border-acsm-line bg-white p-4 shadow-panel">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-sm font-medium text-acsm-muted">{metric.label}</span>
              <metric.icon className="h-4 w-4 text-acsm-green" aria-hidden="true" />
            </div>
            <div className="text-2xl font-semibold text-acsm-ink">{metric.value}</div>
          </div>
        ))}
      </section>

      <section className="rounded-md border border-acsm-line bg-white p-5 shadow-panel">
        <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <h2 className="text-base font-semibold">Operacion inicial</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-acsm-muted">
              Captura desarrolladoras, desarrollos, modelos, conceptos, materiales y mano de obra
              para calcular cotizaciones por desarrollo.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-md border border-acsm-line bg-acsm-paper px-3 py-2">
              Estado API
              <div className="mt-1 font-semibold text-acsm-green">Conectable</div>
            </div>
            <div className="rounded-md border border-acsm-line bg-acsm-paper px-3 py-2">
              Etapa
              <div className="mt-1 font-semibold text-acsm-green">Base web</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
