import { ReactNode, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

type FormDrawerProps = {
  open: boolean
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  onClose: () => void
}

export default function FormDrawer({
  open,
  title,
  description,
  children,
  footer,
  onClose,
}: FormDrawerProps) {
  useEffect(() => {
    if (!open) return undefined

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose, open])

  useEffect(() => {
    if (!open) return undefined
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-slate-950/58 backdrop-blur-[2px]"
        aria-label="Cerrar formulario"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="form-drawer-title"
        className="acsm-form-drawer absolute inset-y-0 right-0 flex w-full max-w-[560px] flex-col overflow-hidden rounded-l-[24px] border-l border-sky-200/45 bg-[linear-gradient(180deg,#f9fcff_0%,#e5f0f8_100%)] shadow-[0_0_60px_rgba(2,17,34,0.36)] sm:w-[min(560px,calc(100vw-32px))]"
      >
        <div className="flex min-h-[78px] items-start justify-between gap-4 border-b border-acsm-line bg-white/72 px-5 py-4">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-acsm-muted">
              Registro
            </p>
            <h2 id="form-drawer-title" className="mt-1 text-xl font-bold text-acsm-ink">
              {title}
            </h2>
            {description ? <p className="mt-1 text-sm text-acsm-muted">{description}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-acsm-line bg-white text-acsm-muted hover:bg-acsm-paper"
            title="Cerrar"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer ? (
          <div className="border-t border-acsm-line bg-white/78 px-5 py-4 shadow-[0_-18px_34px_rgba(10,40,70,0.08)]">
            {footer}
          </div>
        ) : null}
      </aside>
    </div>,
    document.body,
  )
}
