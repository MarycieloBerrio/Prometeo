# PROMETEO

**Scientific Intelligence for Fire Safety in Space.**
*From microgravity fire data to scientific evidence.*

NASA Space Apps Challenge 2026: *Flame in Freefall: AI-Powered Fire Safety Insights from
Microgravity Combustion Data*.

Prometeo is a multimodal scientific intelligence platform. It brings together NASA microgravity
combustion research, experimental data and video (BASS-II, FLEX, SAFFIRE) so engineers can
search, compare and interpret combustion trials. Every conclusion stays traceable to the
experiments behind it, and the platform refuses to extrapolate when the evidence isn't there.

## Quick start (curated MVP)

Default API serves **curated BASS-II JSON** (7 trials, 0 synthetic). No Anthropic key required.
Postgres is started by the Windows initializer (Docker) but the MVP API still reads curated JSON
unless you switch `PROMETEO_DOCUMENT_STORE` / trial store in `.env`.

**Windows (recommended):** double-click `start-prometeo.bat` in the repo root. First time on a
machine, double-click `init-prometeo.bat`. Step-by-step guide (Spanish, for teammates who have
never used PostgreSQL): [Cómo ejecutar Prometeo en Windows](#cómo-ejecutar-prometeo-en-windows).

Manual equivalent (any OS):

```powershell
Copy-Item .env.example .env   # optional; defaults already point at curated JSON
pnpm install
cd apps/backend; uv sync --inexact --extra knowledge; cd ../..   # a bare `uv sync` removes the KB packages

# Terminal 1 — Evidence Engine (curated)
pnpm dev:api              # http://127.0.0.1:8000  (or: uv run prometeo serve --no-reload)

# Terminal 2 — web
pnpm dev:web              # http://localhost:3000
```

Sanity check before demos:

```powershell
cd apps/backend
uv run prometeo validate-data   # expect: OK: 7 trials (0 synthetic)
```

UI-only work without curated semantics: `pnpm dev:api:synthetic` (labels data as
`SYNTHETIC` — never mix into jury claims). Verified smoke notes:
[`docs/integration/mvp-quickstart-smoke-yulian.md`](docs/integration/mvp-quickstart-smoke-yulian.md).

Other settings go in the repo-root `.env` (copy `.env.example`). Keep only that one file: an
`apps/backend/.env` would override it.
Run all checks with `pnpm check`.

## Cómo ejecutar Prometeo en Windows

Guía para cualquier integrante del equipo, aunque nunca haya usado PostgreSQL.

### 1. Instalar una sola vez

| Programa | Para qué | Cómo instalarlo |
|---|---|---|
| **Node.js 22 LTS** | la web (Next.js) | <https://nodejs.org> o `winget install OpenJS.NodeJS.LTS` |
| **uv** | Python 3.12 y la API (FastAPI) | `winget install astral-sh.uv` |
| **Docker Desktop** | la base de datos PostgreSQL + pgvector | <https://www.docker.com/products/docker-desktop/> |
| **Git** | clonar el repositorio | `winget install Git.Git` |

pnpm no hace falta instalarlo: si no está, los `.bat` usan `corepack pnpm`, que viene con Node.
(Para escribir `pnpm ...` a mano en una terminal: `npm install -g pnpm@11`.)
Tras instalar, **cierra y vuelve a abrir** las terminales para que Windows encuentre los programas.

### 2. Los tres archivos `.bat` (doble clic, en la carpeta raíz del repo)

| Archivo | Cuándo usarlo | Qué hace |
|---|---|---|
| `init-prometeo.bat` | la **primera vez**, y después de un `git pull` que cambie dependencias | revisa herramientas, crea `.env` si no existe, instala dependencias, enciende PostgreSQL, comprueba tablas y pgvector, valida los datos curados y arranca Prometeo |
| `start-prometeo.bat` | **cada día** | enciende PostgreSQL solo si está apagado, arranca la API y la web solo si no están ya funcionando, comprueba que respondan y abre <http://localhost:3000> |
| `prometeo.bat` | menú | 1 Iniciar · 2 Configuración inicial · 3 Preparar Knowledge Base · 4 Verificar servicios · 5 Detener · 6 Salir |

Si algo falla, la ventana **no se cierra**: lee las líneas `[ERROR]`, que dicen qué pasó y cómo
arreglarlo. Ejecutar un `.bat` otra vez es seguro: no duplica servicios, no reinstala lo que ya
está, no borra datos y no reconstruye la Knowledge Base.

### 3. El archivo `.env` (configuración)

- Hay **un solo** `.env`, en la **raíz** del repo. Lo leen la API, la web y Docker.
  `init-prometeo.bat` lo crea a partir de `.env.example` si no existe (nunca lo sobrescribe).
- No crees `apps/backend/.env` (sobrescribiría al de la raíz). `.env.local` **no** se usa; si
  tienes uno antiguo, el menú → *Configuración inicial* ofrece copiar sus valores a `.env` (con backup).
- `.env` está en `.gitignore`: **nunca** lo subas ni pegues su contenido en chats o capturas.
- Para usar Claude en el Research Assistant: `PROMETEO_EXPLAINER=anthropic` y **tu propia**
  `ANTHROPIC_API_KEY`. Sin clave, deja `PROMETEO_EXPLAINER=offline` (todo funciona sin Internet).

Configuración típica del equipo:

```dotenv
POSTGRES_PORT=5433
PROMETEO_DATABASE_URL=postgresql://prometeo:prometeo@localhost:5433/prometeo
PROMETEO_DOCUMENT_STORE=postgres   # el asistente busca en la Knowledge Base (paso 5)
PROMETEO_EXPLAINER=anthropic       # u offline
ANTHROPIC_API_KEY=                 # tu clave, solo en tu .env
```

### 4. Qué se enciende

| Servicio | Dirección | Qué es |
|---|---|---|
| Web (Next.js) | <http://localhost:3000> | la aplicación: Explorer, Compare + CFD Physics Lab, FlameVision, Assistant |
| API (FastAPI) | <http://127.0.0.1:8000/docs> | el Evidence Engine; salud en <http://127.0.0.1:8000/health> |
| PostgreSQL + pgvector | `localhost:5433` (o el `POSTGRES_PORT` de tu `.env`) | guarda la Knowledge Base de documentos NASA; corre dentro de Docker |

La API y la web se abren en dos ventanas: **"Prometeo API :8000"** y **"Prometeo Web :3000"**.

**¿Funciona el backend?** Abre <http://127.0.0.1:8000/health> (debe decir `ok`) o usa
`prometeo.bat` → **4. Verificar servicios**, que también comprueba ensayos, casos CFD, modelos,
la base de datos y la Knowledge Base.

**Cerrar Prometeo:** cierra las dos ventanas, o `prometeo.bat` → **5. Detener** (solo detiene
procesos de este repositorio y pregunta si apagar PostgreSQL). Apagar PostgreSQL **no borra**
datos: quedan en el volumen de Docker hasta el próximo arranque.

### 5. Knowledge Base (documentos NASA para el Research Assistant)

Se construye **una vez** por computador: `prometeo.bat` → **3. Preparar Knowledge Base**.
Elige *1 = solo BASS-II* (rápido, ~2 min) o *2 = todos los estudios de combustión de NASA PSI*
(completo, ~15–30 min y varios cientos de MB de PDFs en `data\raw\psi`). Necesita Internet.
Si ya existe, el menú lo dice y pregunta antes de actualizar; nunca borra tablas ni documentos.
Con `PROMETEO_DOCUMENT_STORE=json` el asistente usa los extractos curados del repo y no necesita
la Knowledge Base.

### 6. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| **"El puerto 5433 ya lo usa otro programa"** | Otro PostgreSQL ocupa ese puerto. Elige uno libre (el mensaje sugiere uno) y ponlo en **las dos** líneas: `POSTGRES_PORT=5434` y `PROMETEO_DATABASE_URL=...@localhost:5434/prometeo`. Prometeo nunca cierra ese otro programa. |
| **"El puerto 8000/3000 lo usa otro programa"** | Cierra la otra aplicación (el mensaje dice cuál) y vuelve a ejecutar `start-prometeo.bat`. |
| **"Docker no responde"** | Abre Docker Desktop y espera a "Engine running". El `.bat` intenta abrirlo solo. Si Docker pide WSL 2, acepta la actualización y reinicia Windows. |
| **"POSTGRES_PORT=... pero PROMETEO_DATABASE_URL apunta a ..."** | Los dos puertos del `.env` deben ser iguales. |
| **"Credenciales incorrectas"** | La base se creó con otra contraseña. Pon en `PROMETEO_DATABASE_URL` la misma que `POSTGRES_PASSWORD` tenía al crearla. |
| **El asistente no encuentra documentos** | Menú → 4 *Verificar*: si dice *Knowledge base is EMPTY*, usa la opción 3. Si dice que faltan *fastembed/pypdf*, ejecuta `init-prometeo.bat`. |
| **El asistente no ofrece modelos Claude** | `PROMETEO_EXPLAINER=anthropic` y `ANTHROPIC_API_KEY` en `.env`; luego menú → 5 *Detener* y 1 *Iniciar*. |
| **Cambié `.env` y no pasa nada** | La API lee `.env` al arrancar: menú → 5 *Detener* y 1 *Iniciar*. `start-prometeo.bat` avisa cuando la API es más antigua que tu `.env`. |
| **"Se aplica una ejecución de scripts deshabilitada"** | Usa los `.bat` (ya pasan `-ExecutionPolicy Bypass` solo para su script). |

Más detalle técnico (variables, base compartida en la nube): [`docs/dev-local-windows.md`](docs/dev-local-windows.md).

## Repository

| Path | What |
|---|---|
| `apps/backend` | Evidence Engine API: FastAPI, hexagonal architecture |
| `apps/frontend` | Next.js dashboard: Explorer, Comparison Lab, FlameVision, Assistant |
| `packages/contracts` | TypeScript API types generated from OpenAPI |
| `data` | Curated evidence (git), synthetic fixtures, raw downloads (ignored) |
| `infra` | Postgres + pgvector schema |
| `docs` | [Architecture](docs/architecture.md) · [Science & limits](docs/science.md) · [ADRs](docs/adr) |

AI agents: start with [AGENTS.md](AGENTS.md).

## Scope and limitations

Prometeo supports knowledge discovery, experimental analysis and preliminary engineering
decisions. It does **not** replace flammability testing, certification, safety standards or
validated full-scale fire models. Microgravity results don't transfer directly to lunar or
Martian partial gravity, and small samples don't predict full-scale fires.
