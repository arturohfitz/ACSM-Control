# ACSM Control API

Backend FastAPI para la primera etapa de **ACSM Control**, sistema web modular para constructora residencial. La empresa propietaria del sistema es **ACSM S.A de C.V.**

Incluye:
- Base multiempresa para licenciar ACSM Control por empresa.
- Estado de licencia y limite de usuarios por empresa.
- Autenticacion JWT.
- Usuarios, roles y permisos por modulo/accion.
- Desarrolladoras, desarrollos, modelos de casa, catalogo de materiales, tabulador por desarrollo, mano de obra y conceptos de obra.
- Asignacion de modelos a proyectos.
- Calculo y aprobacion de cotizaciones.
- Alembic para migraciones PostgreSQL.

## Modelo de licenciamiento

ACSM Control queda preparado para venderse por empresa:

- `companies`: empresas licenciadas.
- `users.company_id`: usuarios ligados a una empresa.
- `max_users`: limite de usuarios activos incluidos.
- `license_status`: `trial`, `active`, `expired`, `suspended` o `cancelled`.
- `license_expires_at`: fecha de vencimiento.

El usuario `is_master_admin=true` pertenece a ACSM S.A de C.V. y puede ver todas las empresas. Los usuarios normales solo ven registros de su propia empresa. Si la licencia esta vencida o suspendida, el login y el uso del API quedan bloqueados para esa empresa.

## Instalacion local

Desde la carpeta raiz del repo:

```bash
cd constructora-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para interpretar cotizaciones PDF se recomienda instalar Poppler. El OCR de
documentos escaneados es opcional y requiere Tesseract:

```bash
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-spa
```

Los PDF con texto digital se procesan aunque Tesseract no este instalado. Si un
archivo escaneado requiere OCR y la dependencia no existe, el sistema lo deja
en revision manual sin incorporar precios.

## Configuracion `.env`

El archivo `.env` ya trae valores locales de arranque. Ajusta al menos:

```env
DATABASE_URL=postgresql+psycopg://constructora:constructora@localhost:5432/constructora_db
SECRET_KEY=change-this-secret-key
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
ADMIN_EMAIL=admin@acsm-control.local
ADMIN_PASSWORD=Admin12345!
SUPPLIER_INVOICE_UPLOAD_DIR=storage/supplier_invoice_documents
SUPPLIER_INVOICE_PDF_MAX_MB=15
SUPPLIER_INVOICE_XML_MAX_MB=6
```

Para produccion el sistema bloquea el arranque si detecta valores inseguros. Define:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://usuario:password@host:5432/base
SECRET_KEY=una-cadena-larga-y-unica-de-al-menos-32-caracteres
CORS_ORIGINS=https://acsmcontrol.com,https://www.acsmcontrol.com
ADMIN_EMAIL=correo-admin-real@dominio.com
ADMIN_PASSWORD=una-contrasena-fuerte-unica
EMAIL_ENCRYPTION_KEY=llave-fernet-generada
```

La llave `EMAIL_ENCRYPTION_KEY` cifra las credenciales SMTP/IMAP guardadas en Ajustes. Puedes generar una llave con:

```bash
cd constructora-api
source .venv/bin/activate
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Crear base de datos PostgreSQL

Ejemplo usando un usuario administrador de PostgreSQL:

```bash
sudo -u postgres psql
```

Dentro de `psql`:

```sql
CREATE USER constructora WITH PASSWORD 'constructora';
CREATE DATABASE constructora_db OWNER constructora;
GRANT ALL PRIVILEGES ON DATABASE constructora_db TO constructora;
```

Si tu PostgreSQL local ya tiene otro usuario o password, solo actualiza `DATABASE_URL`.

## Ejecutar migraciones

```bash
cd constructora-api
source .venv/bin/activate
alembic upgrade head
```

## Crear usuario administrador inicial

```bash
cd constructora-api
source .venv/bin/activate
PYTHONPATH=. python -m app.seed
```

El seed es idempotente: crea permisos base, rol `master_admin` y el usuario de `.env`. El usuario `is_master_admin=true` puede hacer todo aunque no tenga permisos asignados.

Tambien puedes activar `AUTO_SEED_ADMIN=true` para ejecutar el seed al iniciar FastAPI.

## Cargar datos demo conectados

Para probar clientes, desarrollos, modelos, cotizaciones e inventario con datos relacionados:

```bash
cd constructora-api
source .venv/bin/activate
PYTHONPATH=. python -m app.seed_demo
```

El seed demo es idempotente y carga:

- 3 desarrolladoras demo.
- 2 desarrollos por desarrolladora.
- 3 modelos de casa.
- Materiales, mano de obra y conceptos de obra.
- Tabuladores de precios de material por desarrollo y modelo.
- Asignacion de modelos a proyectos.
- Cotizaciones por desarrollo.
- Bodegas, listas esperadas, recepciones parciales y stock por proyecto.
- Flujo rapido de inventario para importar PDF, texto pegado desde Excel o texto extraido por OCR desde imagenes y generar listas esperadas.

## Limpiar datos operativos/demo

Antes de capturar informacion real o preparar una demo limpia, puedes borrar los datos operativos sin perder usuarios, roles, permisos, empresas ni configuracion SMTP:

```bash
cd constructora-api
source .venv/bin/activate
PYTHONPATH=. python -m app.clear_operational_data --yes --files
```

El comando elimina desarrolladoras, desarrollos, modelos, documentos cargados, materiales, mano de obra, conceptos, cotizaciones, proveedores, compras, ordenes de compra, inventario, pagos, correos en bandeja de salida y eventos de auditoria.

Si quieres revisar primero que se borraria, ejecuta el mismo comando sin `--yes`.

## Levantar FastAPI

```bash
cd constructora-api
source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload
```

## Proceso obligatorio de versionado

Para evitar ejecutar una version anterior o perder cambios de desarrollo, usa siempre estos scripts desde la raiz del proyecto:

```bash
# Verifica backend y frontend
scripts/verify.sh

# Guarda un checkpoint local con commit
scripts/checkpoint.sh "descripcion del cambio"

# Reinicia API y Web desde esta carpeta, cerrando procesos viejos en 8000/5173
scripts/restart-dev.sh
```

Tambien puedes instalar el candado local de Git:

```bash
scripts/install-hooks.sh
```

Con ese hook, cada `git commit` ejecuta validacion de backend y build frontend antes de permitir guardar el cambio.

La version visible del sistema se actualiza automaticamente antes de `npm run dev` y `npm run build`, y aparece en el menu lateral.

Swagger de ACSM Control queda disponible en:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Endpoints principales

Autenticacion:
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

CRUD:
- `/api/v1/users`
- `/api/v1/companies`
- `/api/v1/roles`
- `/api/v1/permissions`
- `/api/v1/clients`
- `/api/v1/projects`
- `/api/v1/house-models`
- `/api/v1/materials`
- `/api/v1/purchasing/suppliers`
- `/api/v1/construction-concepts`

Especiales:
- `POST /api/v1/companies/onboard`
- `POST /api/v1/projects/{project_id}/house-models`
- `GET /api/v1/projects/{project_id}/summary`
- `POST /api/v1/house-models/{house_model_id}/concepts`
- `POST /api/v1/inventory/projects/{project_id}/quick-documents/parse-pdf`
- `POST /api/v1/inventory/projects/{project_id}/quick-documents/parse-text`
- `POST /api/v1/inventory/projects/{project_id}/quick-documents`
- `GET /api/v1/settings/email/outbox`
- `POST /api/v1/settings/email/outbox/process`
- `POST /api/v1/purchasing/supplier-rfqs`
- `POST /api/v1/purchasing/supplier-rfqs/{rfq_id}/send`
- `POST /api/v1/purchasing/supplier-rfqs/{rfq_id}/quotes`
- `GET /api/v1/purchasing/supplier-rfqs/{rfq_id}/comparison`
- `POST /api/v1/purchasing/supplier-quotes/{quote_id}/approve`
- `GET /api/v1/purchasing/purchase-orders`
- `POST /api/v1/purchasing/purchase-orders/{purchase_order_id}/send`
- `POST /api/v1/purchasing/supplier-invoices/register`
- `POST /api/v1/purchasing/supplier-invoice-documents/analyze-xml`
- `POST /api/v1/purchasing/supplier-invoices/{invoice_id}/documents`
- `GET /api/v1/purchasing/supplier-invoice-documents/{document_id}/download`
- `POST /api/v1/purchasing/supplier-invoices/{invoice_id}/validate`
- `POST /api/v1/purchasing/supplier-payments`

## Flujo de compras a proveedores

El sistema controla el proceso:

1. Compras crea una solicitud de cotizacion de materiales para un desarrollo.
2. La solicitud exige al menos 3 proveedores invitados.
3. El proveedor carga su PDF y el sistema propone folio, identidad, precios,
   entrega e importes. Compras revisa la evidencia antes de incorporarla.
4. El comparativo permite aprobar una cotizacion.
5. Al aprobar, se genera una orden de compra y una lista esperada en inventario.
6. Inventario recibe material contra esa lista y actualiza el avance de la orden.
7. Cuentas por pagar registra la factura con al menos un PDF o XML. El XML CFDI cruza UUID, RFC, fecha e importes contra la orden, el proveedor y la constructora; una captura solo con PDF requiere revision fiscal manual.
8. La factura se valida contra las cantidades recibidas. Si hay material pendiente queda bloqueada; cuando la recepcion es suficiente pasa a pago.
9. Una orden puede tener varias facturas y cada factura puede pagarse en una o varias exhibiciones sin superar su saldo.
10. Al completar los pagos de todas las cantidades facturadas y recibidas se cierra la orden de compra.

Los archivos se guardan fuera del directorio publico, con nombre aleatorio, permisos privados, validacion de firma o estructura y escaneo con ClamAV cuando esta instalado. Para habilitar la validacion automatica del XML deben estar capturados el RFC de la constructora y el RFC del proveedor.

## Alta de constructora con licencia

El administrador maestro puede crear una constructora nueva junto con su cuenta administradora inicial:

```http
POST /api/v1/companies/onboard
```

Este flujo crea en una sola transaccion:

- La constructora/licencia.
- El usuario administrador de esa constructora.
- El rol `Administrador de constructora`.
- Roles base operativos:
  `Proyectos y desarrolladoras`,
  `Inventario`,
  `Cotizaciones y costos`,
  `Compras`,
  `Gerencia de compras`,
  `Pagos a proveedores`,
  `Auditoria` y
  `Solo lectura`.

El administrador creado no es `master_admin`; solo ve y administra datos de su propia constructora.

## Verificacion y calidad

```bash
cd ..
./scripts/verify.sh
```

La verificacion ejecuta:

- Compilacion Python del backend.
- Pruebas unitarias en `constructora-api/tests`.
- Build completo del frontend.

Las migraciones se aplican con:

```bash
cd constructora-api
source .venv/bin/activate
alembic upgrade head
```

Nota: `alembic upgrade head` requiere que `DATABASE_URL` apunte a una base PostgreSQL accesible con credenciales validas.

GitHub Actions ejecuta `./scripts/verify.sh` en cada push o pull request contra `main`.
