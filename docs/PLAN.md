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

Pendiente de esta fase: Gemini tarda de 6 a 9 segundos por respuesta; revisar si se puede
bajar ajustando el razonamiento del modelo.

## Fase 2 — Conectar el frontend (3–5 días)

- [ ] Reemplazar `tutorSimulado` por una función que llame a `POST /api/chat`
      (línea `const tutor = …` en `web/app/page.tsx`).
- [ ] Mensajes de error con toasts: sin conexión, proveedor caído o límite alcanzado.
- [ ] Opcional: mostrar la respuesta mientras el modelo la genera (streaming).

## Fase 3 — Seguridad y límites (1 semana)

- [ ] `servicios/limites.py`: mensajes por sesión y por día (SQLite local, Neon en
      producción).
- [ ] Detectar datos personales (cédulas, teléfonos) y pedir que no se compartan.
- [ ] Probar intentos de sacar al tutor de su papel (que dé la respuesta, otros temas).

## Fase 4 — Banco de ejercicios (2–4 semanas, en paralelo con las fases 1–3)

- [ ] Reunir fuentes: materiales de práctica publicados por la UCR, la UNA y el TEC, y
      ejercicios originales escritos por docentes. **Revisar los derechos de uso de cada
      fuente** antes de copiarla; si no se puede, usarla solo como referencia.
- [ ] Usar el formato de `backend/ejercicios/banco.json` y agregar etiquetas: universidad,
      área (razonamiento matemático o verbal), tema y dificultad.
- [ ] Revisión humana de cada ejercicio; verificar la solución con SymPy cuando se pueda.
- [ ] Meta inicial: 150–300 ejercicios bien revisados.

## Fase 5 — "Entrenamiento" con el banco (2–3 semanas)

1. [ ] **Consulta del banco (RAG):** al recibir un problema, buscar los ejercicios más
       parecidos y pasarle al modelo, en privado, sus pasos y errores comunes.
2. [ ] **Ejemplos en las instrucciones:** 2–3 conversaciones modelo de buena tutoría.
3. [ ] **Evaluación automática:** 50–100 conversaciones de prueba que midan si filtró la
       respuesta, si la pista es correcta, si respeta el nivel de pista y si usa voseo.
       Correrla cada vez que cambien las instrucciones o el modelo.
4. [ ] **Ajuste fino, solo si la evaluación lo justifica:** entrenar con *conversaciones de
       tutoría* generadas a partir del banco y revisadas por personas (LoRA sobre un
       modelo abierto o el servicio de ajuste del proveedor).

## Fase 6 — Despliegue y piloto (2–3 semanas)

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
