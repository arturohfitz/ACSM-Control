# ACSM Control Web

Frontend web administrativo de **ACSM Control**, propiedad de **ACSM S.A de C.V.**

La interfaz debe contemplar un logo futuro. Por ahora la marca queda centralizada en:

```text
src/config/brand.ts
```

Cuando exista el logo, se puede colocar en `public/` y actualizar `logoPath`.

## Requisitos

- Node.js 20 o superior.
- Backend `constructora-api` levantado.

## Configuracion

Crear `.env` si necesitas cambiar la URL del backend:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## Instalacion

```bash
cd constructora-web
npm install
```

## Ejecutar en local

```bash
npm run dev
```

La app abre en:

```text
http://127.0.0.1:5173
```

## Compilar

```bash
npm run build
```

## Pantallas incluidas

- Login.
- Layout administrativo con menu lateral.
- Rutas protegidas.
- Inicio.
- Desarrolladoras.
- Desarrollos con asignacion de modelos y resumen.
- Modelos de casa por desarrolladora.
- Tabulador del desarrollo para precios unitarios por proyecto/modelo.
- Catalogo de materiales.
- Mano de obra.
- Conceptos de obra.
- Cotizaciones con calculo por desarrollo y aprobacion.
- Inventario rapido con importacion de PDF, OCR de imagenes JPG/PNG, pegado desde Excel y tabla editable.
- Usuarios.
- Roles.
- Ajustes de marca.
- Empresas/licencias para administrar clientes SaaS desde ACSM.

## Licenciamiento por empresa

La pantalla `Empresas` permite registrar empresas cliente, plan, usuarios incluidos, estado de licencia y vencimiento. Los usuarios se asocian a una empresa mediante `Empresa ID`.
