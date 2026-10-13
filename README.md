# MAEstro

Tutor de inteligencia artificial **gratuito** que ayuda a estudiantes de colegio de la
Región Brunca de Costa Rica a prepararse para las pruebas de admisión de la **UCR**, la
**UNA** y el **TEC**.

MAEstro guía con preguntas y pistas graduales: **nunca da la respuesta**. La idea es que el
estudiante llegue solo a la solución y aprenda el razonamiento, no que copie un resultado.

## El nombre

Es un juego de palabras: **mae** (como se llaman entre amigos en Costa Rica) + **maestro**.
Un mae que te acompaña a estudiar.

## Estado

**Prototipo.** El frontend ya tiene la interfaz completa de agente (menú de chats,
conversación y pizarra), pero responde con un **tutor simulado** (`web/lib/tutorSimulado.ts`).
En el backend, las rutas devuelven datos fijos de ejemplo y los servicios (agente,
proveedores de IA, verificación con SymPy, imágenes, límites y base de datos) solo tienen
docstrings y firmas. El plan de desarrollo está en [`docs/PLAN.md`](docs/PLAN.md).

## Estructura

```
prototipo/
├── backend/                 API en Python 3.12 + FastAPI
│   ├── app/
│   │   ├── main.py          Crea la app, CORS y registra los routers
│   │   ├── config.py        Lee variables de entorno y el .env (sin dependencias extra)
│   │   ├── esquemas.py      Modelos Pydantic de entrada y salida
│   │   ├── rutas/           salud, ejercicios, sesiones, chat
│   │   ├── servicios/       agente, modelos_ia, verificador, imagenes, limites
│   │   └── datos/db.py      SQLAlchemy: SQLite local, PostgreSQL (Neon) en producción
│   ├── ejercicios/banco.json  Banco de ejercicios de ejemplo
│   ├── tests/               Pruebas con pytest
│   ├── requirements.txt
│   ├── .env.example
│   └── Containerfile        Imagen para Podman
├── web/                     Next.js 15 (App Router, TypeScript), exportado como sitio estático
│   ├── app/                 layout (fuentes y tema), página principal y globals.css
│   ├── components/          BarraLateral, Bienvenida, Conversacion, Redactor, Pizarra,
│   │                        AvisoEntrada, Toasts, BotonTema, Logo, Iconos
│   └── lib/
│       ├── api.ts           Funciones para llamar al backend
│       ├── tutorSimulado.ts Tutor de prueba (se reemplaza por la llamada real)
│       ├── chats.ts         Historial de chats (por ahora en localStorage)
│       ├── trazos.ts        Círculos y trazos "a mano" de la pizarra
│       └── tema.ts          Modo claro/oscuro
├── docs/PLAN.md             Plan de desarrollo
├── flake.nix                Entorno de desarrollo con Nix (arranque automático)
├── .envrc                   Activa el flake con direnv al entrar a la carpeta
├── detener.sh               Detiene los servidores que arrancó el entorno
├── README.md
└── .gitignore
```

### Rutas de la API

| Método | Ruta              | Respuesta actual                                      |
| ------ | ----------------- | ----------------------------------------------------- |
| GET    | `/api/salud`      | `{"ok": true}`                                        |
| GET    | `/api/ejercicios` | Dos ejercicios de ejemplo (sin solución)              |
| POST   | `/api/sesiones`   | `{"ok": true}`                                        |
| POST   | `/api/chat`       | `"Modo de prueba: aquí responderá el tutor."`         |

## Cómo correrlo en Fedora

### Automático (direnv + Nix)

Con [direnv](https://direnv.net) y Nix instalados, basta con entrar a la carpeta:

```bash
cd /home/jeremy/semestreII2026/Examen/prototipo
```

La primera vez hay que autorizarla con `direnv allow`. El entorno (`flake.nix`) trae
Python 3.12 y Node 22, crea `backend/.venv` y `web/node_modules` si faltan, y arranca en
segundo plano el backend (<http://localhost:8100>) y el frontend (<http://localhost:3100>).
Si alguno de esos puertos ya está ocupado (por ejemplo, por otro proyecto), avisa y no
lo arranca.

- Logs: `tail -f .dev/logs/backend.log .dev/logs/frontend.log`
- Detener: `./detener.sh`

### Manual

Requisitos: Python 3.12 o más reciente (`python3`), Node.js 20+ y npm.

```bash
sudo dnf install python3 nodejs npm
```

### Backend

```bash
cd /home/jeremy/semestreII2026/Examen/prototipo/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # completá las llaves cuando las tengás
uvicorn app.main:app --reload --port 8100
```

La API queda en <http://localhost:8100> y la documentación interactiva en
<http://localhost:8100/docs>.

Pruebas:

```bash
cd /home/jeremy/semestreII2026/Examen/prototipo/backend
source .venv/bin/activate
pytest
```

Con Podman:

```bash
cd /home/jeremy/semestreII2026/Examen/prototipo/backend
podman build -t maestro-backend -f Containerfile .
podman run --rm -p 8100:8100 --env-file .env maestro-backend
```

### Frontend

```bash
cd /home/jeremy/semestreII2026/Examen/prototipo/web
npm install
cp .env.example .env.local  # NEXT_PUBLIC_API_URL=http://localhost:8100
npm run dev
```

Abrí <http://localhost:3100>.

Para generar el sitio estático (queda en `web/out/`):

```bash
cd /home/jeremy/semestreII2026/Examen/prototipo/web
npm run build
```

## Interfaz

Tiene la estructura de un agente de chat:

- **Menú de chats** a la izquierda: chat nuevo e historial agrupado por fecha. Se guarda
  solo en el navegador; las fotos no se guardan.
- **Conversación** al centro. No hay ejercicios precargados: el estudiante trae su problema
  (escrito o en foto) y el tutor lo guía con hasta tres pistas, sin dar la respuesta.
- **Pizarra** a la derecha: el tutor copia el problema, encierra los datos con tiza y
  escribe sus apuntes. En celular se abre con el botón "Pizarra".

## Identidad visual

La pizarra verde de las aulas ticas y el verde del bosque. La guaria (morado de la
orquídea nacional) es el único acento: pistas, trazo del logo y anillo de foco. Los
tokens de color, con modo claro, oscuro y el botón de tema, están en
`web/app/globals.css`. Fuentes: Bricolage Grotesque (títulos), Atkinson Hyperlegible
(texto) y Caveat (lo que se escribe con tiza).
