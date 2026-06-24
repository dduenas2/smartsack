# Documentación de SmartSack

Índice general de la documentación del trabajo de grado **SmartSack** —
plataforma inteligente de gestión de producción con Digital Twin, analítica
predictiva y asistente conversacional para plantas de fabricación de sacos de
papel.

> Para la puesta en marcha rápida del proyecto, ver el [README principal](../README.md).

---

## 🎓 Documento de cierre

| Documento | Descripción |
|---|---|
| [`Documento_Final.md`](./Documento_Final.md) | Cierre del trabajo de grado: resultados, cumplimiento de los 7 objetivos, lecciones aprendidas, trabajo futuro y conclusiones. |
| [`Guion_Sustentacion.md`](./Guion_Sustentacion.md) | Material de apoyo para la defensa: estructura, diapositivas con notas, guion del demo en vivo y preguntas anticipadas. |

## 📘 Manuales

| Documento | Audiencia |
|---|---|
| [`Manual_Usuario.md`](./Manual_Usuario.md) | Operarios, supervisores y administradores (incluye capturas de pantalla). |
| [`Manual_Tecnico.md`](./Manual_Tecnico.md) | Personal técnico: instalación, despliegue, operación y resolución de problemas. |

## 🔬 Datos y validación (Entregable E7)

| Documento | Contenido |
|---|---|
| [`DATASET.md`](./DATASET.md) | Conjunto de datos sintético a escala: justificación, volumetría, features, etiqueta y modelo de riesgo. |
| [`Informe_Validacion_ML.md`](./Informe_Validacion_ML.md) | Evaluación del modelo de predicción de retrasos (AUC-ROC, F1, matriz de confusión, importancia de variables). |
| [`Instrumento_SUS.md`](./Instrumento_SUS.md) | Cuestionario de usabilidad System Usability Scale (SUS): instrumento, protocolo y puntuación. |
| [`Instrumento_Impacto_Operativo.md`](./Instrumento_Impacto_Operativo.md) | Medición del impacto operativo (tiempo pre/post) y encuesta de satisfacción. |
| [`Instrumento_Chatbot.md`](./Instrumento_Chatbot.md) | Protocolo de 50 preguntas para medir la exactitud del asistente conversacional (hipótesis H3). |
| [`Informe_Validacion_E7.md`](./Informe_Validacion_E7.md) | **Informe maestro** que consolida las 5 dimensiones de validación y las mapea a las hipótesis H1–H4. |

## 🧰 Recursos

| Recurso | Descripción |
|---|---|
| [`figuras/`](./figuras/) | Figuras del informe de ML (curva ROC, matriz de confusión, importancia de variables). |
| [`capturas/`](./capturas/) | Capturas de pantalla de la aplicación usadas en el manual de usuario. |
| [`plantillas/`](./plantillas/) | Plantillas CSV y calculadoras de los instrumentos de evaluación (`sus_score.py`, `impacto_score.py`, `chatbot_score.py`). |

---

## Cómo regenerar los artefactos

```bash
# Dataset determinista + entrenamiento del modelo (escribe el manifest de métricas)
docker compose exec backend python -m scripts.seed --reset
docker compose exec backend python -m ml.train

# Figuras del informe de ML  →  docs/figuras/
docker compose exec backend python -m ml.figures

# Capturas de pantalla del manual  →  docs/capturas/
(cd frontend/e2e && npx playwright test screenshots.spec.js)

# Cálculo de los instrumentos de evaluación (Python del sistema, sin dependencias)
python3 docs/plantillas/sus_score.py docs/plantillas/sus_respuestas_ejemplo.csv
python3 docs/plantillas/impacto_score.py docs/plantillas/impacto_tiempos_ejemplo.csv \
    --satisfaccion docs/plantillas/impacto_satisfaccion_ejemplo.csv
python3 docs/plantillas/chatbot_score.py docs/plantillas/chatbot_respuestas_ejemplo.csv
```
