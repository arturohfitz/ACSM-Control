import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useAuth } from '../auth/AuthContext'

type ProtectedRouteProps = {
  children?: ReactNode
  permission?: string | string[]
  requireAll?: boolean
}

export default function ProtectedRoute({ children, permission, requireAll = false }: ProtectedRouteProps) {
  const { user, loading, hasPermission } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-acsm-paper text-sm text-acsm-muted">
        Cargando...
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  const permissions = Array.isArray(permission) ? permission : permission ? [permission] : []
  const allowed =
    permissions.length === 0 ||
    (requireAll
      ? permissions.every((item) => hasPermission(item))
      : permissions.some((item) => hasPermission(item)))

  if (!allowed) {
    return <Navigate to="/" replace />
  }

  return children ?? <Outlet />
}
