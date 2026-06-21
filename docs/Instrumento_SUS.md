# Instrumento de evaluación de usabilidad — SUS

**Proyecto:** SmartSack · **Entregable:** E7 (validación con usuarios) ·
**Instrumento:** System Usability Scale (Brooke, 1996)

Este documento contiene el cuestionario, el protocolo de aplicación, las reglas
de puntuación y la interpretación para medir la **usabilidad percibida** de
SmartSack por parte de operarios y supervisores de planta.

---

## 1. Objetivo

Medir, de forma estandarizada y comparable, la usabilidad de la plataforma
SmartSack tras una sesión de uso guiada con tareas representativas de cada rol.
Se elige la **System Usability Scale (SUS)** por ser un instrumento validado,
breve (10 ítems), independiente de la tecnología y con amplias referencias de
comparación (la media poblacional es 68).

## 2. El cuestionario

### 2.1. Datos del participante (anónimo)

| Campo | Valor |
|---|---|
| Código de participante | (asignado por el evaluador, p. ej. OP-01) |
| Rol | ☐ Operario ☐ Supervisor |
| Antigüedad en la planta | ____ años |
| Experiencia previa con software de producción | ☐ Ninguna ☐ Básica ☐ Avanzada |

> No se recogen datos personales identificables. La participación es voluntaria.

### 2.2. Escala de respuesta

Cada afirmación se responde en una escala Likert de 5 puntos:

| 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|
| Totalmente en desacuerdo | En desacuerdo | Neutral | De acuerdo | Totalmente de acuerdo |

### 2.3. Ítems

Responda pensando en su experiencia usando **SmartSack**:

| # | Afirmación |
|---|---|
| 1 | Creo que usaría SmartSack frecuentemente. |
| 2 | Encuentro SmartSack innecesariamente complejo. |
| 3 | Creo que SmartSack es fácil de usar. |
| 4 | Creo que necesitaría el apoyo de un técnico para poder usar SmartSack. |
| 5 | Encuentro que las diversas funciones de SmartSack están bien integradas. |
| 6 | Creo que SmartSack es demasiado inconsistente. |
| 7 | Imagino que la mayoría de la gente aprendería a usar SmartSack muy rápidamente. |
| 8 | Encuentro SmartSack muy engorroso de usar. |
| 9 | Me sentí muy seguro/a usando SmartSack. |
| 10 | Necesité aprender muchas cosas antes de poder empezar a usar SmartSack. |

Los ítems impares son afirmaciones positivas y los pares, negativas (formato
estándar del SUS). Esta alternancia mitiga el sesgo de aquiescencia.

## 3. Protocolo de aplicación

### 3.1. Participantes

Muestra objetivo: **mínimo 8–12 participantes** que cubran ambos roles
(operarios y supervisores). El SUS produce estimaciones estables del promedio a
partir de ~8 respuestas; con 12–15 se obtiene buena precisión.

### 3.2. Procedimiento

1. **Bienvenida y consentimiento** (2 min): se explica el propósito, el carácter
   anónimo y voluntario, y que se evalúa el sistema, no a la persona.
2. **Sesión guiada de tareas** (10–15 min): el participante realiza un conjunto
   de tareas representativas de su rol (ver 3.3) en un entorno con datos de
   demostración.
3. **Cuestionario SUS** (3 min): el participante responde los 10 ítems de forma
   individual e inmediata, sin intervención del evaluador.
4. **Comentario abierto opcional** (2 min): observaciones cualitativas que
   complementan el puntaje.

### 3.3. Tareas representativas por rol

**Operario** (vista de operario):
- Iniciar la operación de la orden en curso en su máquina.
- Registrar un avance de producción y una parada (cambio de bobina).
- Reportar una incidencia de calidad.
- Consultar la cola de órdenes pendientes de su máquina.

**Supervisor** (Digital Twin + dashboard + chatbot):
- Localizar en el mapa de planta una máquina detenida y su causa.
- Consultar el dashboard de KPIs (OEE, cumplimiento) y una alerta de retraso.
- Hacer dos preguntas en lenguaje natural al chatbot (p. ej. "¿qué órdenes
  están retrasadas hoy?").

### 3.4. Consideraciones éticas

Respuestas anónimas, participación voluntaria con posibilidad de retirarse en
cualquier momento, y uso de los datos exclusivamente agregado para el trabajo de
grado.

## 4. Puntuación

Regla estándar de Brooke (1996), por participante:

- **Ítems impares** (1, 3, 5, 7, 9): contribución = `respuesta − 1`.
- **Ítems pares** (2, 4, 6, 8, 10): contribución = `5 − respuesta`.
- **Puntaje SUS** = (suma de las 10 contribuciones) × **2,5** → escala **0–100**.

> El puntaje SUS **no es un porcentaje**: es un valor en una escala de 0 a 100
> que debe interpretarse contra las referencias de la sección 5.

**Ejemplo** (participante OP-01 del archivo de ejemplo): respuestas impares
4,5,4,5,4 → 3+4+3+4+3 = 17; respuestas pares 2,2,1,2,2 → 3+3+4+3+3 = 16;
total 33 × 2,5 = **82,5**.

## 5. Interpretación

| Rango SUS | Adjetivo (Bangor et al., 2009) | Grado |
|---|---|---|
| 0 – 50,9 | Pobre | F |
| 51 – 67,9 | Aceptable (OK) | D |
| 68 – 73,9 | Bueno | C |
| 74 – 80,2 | Bueno | B |
| 80,3 – 100 | Excelente | A |

**Aceptabilidad** (escala independiente): SUS < 50 → *No aceptable*;
50 – 70 → *Marginal*; > 70 → *Aceptable*.

Referencia clave: la **media poblacional del SUS es 68** (percentil 50). Un
promedio por encima de 68 indica una usabilidad superior a la media; por encima
de 80,3 se considera excelente (decil superior). Estos mismos umbrales están
implementados en `sus_score.py`.

## 6. Tabulación y cálculo

Las respuestas se vuelcan en una hoja con una fila por participante:

- **Plantilla en blanco:** [`plantillas/sus_respuestas_plantilla.csv`](./plantillas/sus_respuestas_plantilla.csv)
- **Calculadora:** [`plantillas/sus_score.py`](./plantillas/sus_score.py) — sin
  dependencias externas.

```bash
python3 docs/plantillas/sus_score.py docs/plantillas/sus_respuestas_ejemplo.csv
```

La calculadora devuelve el puntaje de cada participante, el promedio, la
desviación estándar, la interpretación y un desglose por rol.

### 6.1. Ejemplo de salida (datos ilustrativos, no reales)

El archivo [`plantillas/sus_respuestas_ejemplo.csv`](./plantillas/sus_respuestas_ejemplo.csv)
contiene 10 respuestas **de ejemplo** para demostrar el flujo de cálculo:

```
N participantes        : 10
SUS promedio           : 83.8
Desviación estándar    : 10.5
Mínimo / Máximo        : 67.5 / 97.5
Interpretación         : Excelente  ·  Aceptable  ·  grado A

Por rol:
  operario       n=6   SUS=82.1
  supervisor     n=4   SUS=86.2
```

> Estos valores son ficticios y sirven únicamente para validar el instrumento y
> la calculadora. Los resultados reales se obtendrán al aplicar el cuestionario
> a los participantes de la planta.

## Referencias

- Brooke, J. (1996). *SUS: A "quick and dirty" usability scale.* En P. W.
  Jordan et al. (Eds.), *Usability Evaluation in Industry*. Taylor & Francis.
- Bangor, A., Kortum, P., & Miller, J. (2009). *Determining what individual SUS
  scores mean: Adding an adjective rating scale.* Journal of Usability Studies,
  4(3), 114–123.
- Sauro, J., & Lewis, J. R. (2016). *Quantifying the User Experience* (2.ª ed.).
  Morgan Kaufmann.
