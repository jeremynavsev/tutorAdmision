# Plan de desarrollo de MAEstro

Desde el prototipo (interfaz completa con tutor simulado) hasta un tutor que use un banco
de ejercicios de admisión de la UCR, la UNA y el TEC.

**Idea central:** "entrenar" no significa reentrenar un modelo desde el principio. Primero
se hace que el modelo consulte un banco de ejercicios revisados mientras conversa (RAG) y
se mide con evaluaciones. El ajuste fino (fine-tuning) queda para el final, solo si las
evaluaciones muestran que hace falta.

## Cómo trabajamos: una rama por fase

Cada fase se hace en su propia rama, que sale de `main` actualizado. Al terminarla, se
abre un pull request hacia `main`; se fusiona cuando pasan las pruebas
(`pytest` en `backend/` y `npm run build` en `web/`). La siguiente fase sale de `main`
ya con la anterior incluida.

| Fase | Rama                    |
| ---- | ----------------------- |
| 0    | `fase-0-contrato`       |
| 1    | `fase-1-backend-ia`     |
| 2    | `fase-2-conexion`       |
| 3    | `fase-3-seguridad`      |
| 4    | `fase-4-banco`          |
| 5    | `fase-5-entrenamiento`  |
| 6    | `fase-6-despliegue`     |

La fase 4 (banco de ejercicios) puede avanzar en paralelo a las fases 1–3, porque toca
otros archivos.

## Fase 0 — Cerrar el prototipo (1–2 días)

- [x] `git init` y primer commit (incluyendo `flake.nix` y `flake.lock`: Nix solo ve los
      archivos que git rastrea).
- [x] Definir el **contrato del tutor** en `backend/app/esquemas.py`: lo que recibe
      (mensaje, foto, historial, enunciado en la pizarra, pistas dadas) y lo que devuelve
      (`texto`, `pista`, `anotaciones`). Quedó en `backend/app/esquemas.py` y su espejo
      en `web/lib/contrato.ts`, con pruebas en `backend/tests/test_chat.py`.

## Fase 1 — Backend con IA real (1–2 semanas)

- [x] `servicios/modelos_ia.py`: cadena Groq → Gemini → Mistral con el cliente `openai`,
      con tiempo máximo y paso automático al siguiente proveedor si uno falla.
- [x] `servicios/agente.py`: instrucciones del sistema (voseo, guiar con preguntas, pistas
      que se adaptan al estudiante, nunca dar la respuesta) y respuesta en **JSON estructurado** con el
      texto y las anotaciones de la pizarra.
- [x] `servicios/verificador.py`: con SymPy, revisar que el tutor no filtre el resultado
      final; si lo filtra, regenerar la respuesta.
- [x] `servicios/imagenes.py`: quitar metadatos y reducir la foto antes de pasarla al
      modelo con visión.
- [x] Pruebas con pytest para cada servicio, con los proveedores simulados.
- [x] `servicios/tutor.py` une todo y `POST /api/chat` ya responde con IA real.

**Lo que se aprendió sobre los proveedores (octubre de 2026):**

- **Groq** va primero: responde en unos 2 segundos y su límite gratuito aguanta las
  pruebas, pero no lee fotos y a veces se sale del voseo.
- **Gemini** gratuito permite solo 20 pedidos por día por modelo y se satura seguido
  (errores 503). Se usa para las fotos, con modelos de respaldo que suman cuota
  (`GEMINI_MODELOS_RESPALDO`) y con poco razonamiento para que responda más rápido.
- **Mistral**: su API ya no es gratuita (pago por uso o plan Pro). Sigue soportado en el
  código por si se consigue una llave.
- **Los planes gratuitos no alcanzan para el piloto** con estudiantes: hay que
  presupuestar un plan de pago antes de la fase 6. Groq gratuito da 200 000 tokens por
  día y cada mensaje del tutor gasta unos 2700 (las instrucciones solas son unos 2000):
  alcanza para unos 70 mensajes al día entre todos los estudiantes.
- **Conviene achicar las instrucciones del tutor:** cada token se paga en cada mensaje
  de cada estudiante. Hacerlo con la evaluación automática, para no perder calidad.
- **Ollama** (modelos en un servidor propio) es gratis, sin cuotas y más privado, pero
  necesita un servidor con tarjeta de video. Es una opción si la universidad presta uno,
  o para servir un modelo con ajuste fino en la fase 5.

## Fase 2 — Conectar el frontend (3–5 días)

- [x] Reemplazar `tutorSimulado` por una función que llame a `POST /api/chat`:
      `web/lib/tutorRemoto.ts`. El simulado queda con `NEXT_PUBLIC_TUTOR=simulado`.
- [x] Reducir la foto en el navegador antes de subirla (`web/lib/fotos.ts`): menos datos
      móviles, nunca pasa el límite del backend y los metadatos no salen del teléfono.
- [x] Avisos de error: se distinguen de las confirmaciones, no tapan la conversación y,
      si el tutor no responde, el mensaje ofrece "Reintentar" sin volver a escribirlo.
- [ ] Opcional: mostrar la respuesta mientras el modelo la genera (streaming).

## Fase 3 — Seguridad y límites (1 semana)

- [x] `servicios/limites.py`: 40 mensajes por estudiante y 1000 por conexión al día, en
      hora de Costa Rica. Se cuentan solo si el tutor respondió. De la conexión se guarda
      una huella diaria, nunca la IP.
- [x] La página crea la sesión al aceptar el aviso (y otra sola si se venció), avisa
      cuando quedan 5 mensajes o menos y bloquea el campo al llegar al límite.
- [x] Detectar datos personales (cédulas, teléfonos, correos y nombres completos): la
      página pregunta antes de enviar y el backend los oculta antes de mandarlos a la IA.
      Las direcciones no se detectan; para eso queda la regla de las instrucciones.
- [x] Probar intentos de sacar al tutor de su papel: 8 casos en la evaluación (respuesta
      en clave o en la pizarra, "modo desarrollador", presión emocional, insultos, pedir
      sus instrucciones, un ensayo de otra materia y "solo decime si es 7 u 8").
      En los que corrieron con IA no filtró la respuesta; falta correrlos todos cuando
      haya cuota.

## Fase 4 — Banco de ejercicios (2–4 semanas, en paralelo con las fases 1–3)

- [ ] Reunir fuentes: materiales de práctica publicados por la UCR, la UNA y el TEC, y
      ejercicios originales escritos por docentes. **Revisar los derechos de uso de cada
      fuente** antes de copiarla; si no se puede, usarla solo como referencia.
- [x] Usar el formato de `backend/ejercicios/banco.json` y agregar etiquetas: universidad,
      área (razonamiento matemático o verbal), tema y dificultad. La universidad queda
      vacía hasta confirmar de qué examen sale cada ejercicio.
- [ ] Revisión humana de cada ejercicio; verificar la solución con SymPy cuando se pueda.
      `python -m app.datos.revision` calcula la `comprobacion` de cada ejercicio, la compara
      con la clave y lista los que faltan por revisar (`revisado: true` cuando una persona
      ya lo revisó).
- [ ] Meta inicial: 150–300 ejercicios bien revisados.

## Fase 5 — "Entrenamiento" con el banco (2–3 semanas)

1. [x] **Consulta del banco (RAG):** al recibir un problema, buscar los ejercicios más
       parecidos y pasarle al modelo, en privado, sus pasos y errores comunes.
       `servicios/buscador.py` usa TF-IDF en Python puro (sin embeddings ni otra API).
       Si el problema es uno del banco, su clave va al verificador. Límite: compara
       palabras, no ideas; si con más ejercicios trae parecidos que no ayudan, probar
       embeddings.
2. [ ] **Ejemplos en las instrucciones:** 2–3 conversaciones modelo de buena tutoría.
3. [ ] **Evaluación automática** (empezada en la fase 3: `backend/evaluacion/`, con 10
       conversaciones y revisiones por patrones; falta ampliarla y sumar un evaluador
       con IA que califique la calidad de las pistas). Meta: 50–100 conversaciones de
       prueba que midan si filtró la respuesta, si la pista es correcta, si respeta el
       nivel de pista y si usa voseo.
       Correrla cada vez que cambien las instrucciones o el modelo.
4. [ ] **Ajuste fino, solo si la evaluación lo justifica:** entrenar con *conversaciones de
       tutoría* generadas a partir del banco y revisadas por personas (LoRA sobre un
       modelo abierto o el servicio de ajuste del proveedor).

## Fase 6 — Despliegue y piloto (2–3 semanas)

- [ ] Decidir y presupuestar los proveedores de IA: los planes gratuitos no alcanzan para
      varios estudiantes a la vez. Revisar también qué hace cada proveedor con los datos.
- [ ] Frontend estático en un hosting gratuito; backend con el `Containerfile` en un
      servicio de contenedores; base de datos en Neon.
- [ ] Piloto con colegios de la Región Brunca. Son menores de edad: hace falta el
      consentimiento de los encargados y, si es parte de una investigación, la
      aprobación del comité de ética correspondiente.
- [ ] Métricas: aciertos antes y después, pistas usadas por ejercicio, abandono y
      comentarios de estudiantes y docentes.

## Calendario tentativo

| Semanas  | Trabajo                                             |
| -------- | --------------------------------------------------- |
| 1–2      | Fases 0 y 1; arranque del banco (fase 4)            |
| 3        | Fases 2 y 3                                         |
| 4–6      | Terminar el banco y la fase 5 (RAG y evaluación)    |
| 7–9      | Despliegue y piloto                                 |
| Después  | Ajuste fino, solo si los datos lo piden             |
