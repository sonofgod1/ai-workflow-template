# ADR-0000: Adoptar Architecture Decision Records

## Estado
Aceptado

## Contexto

A medida que un proyecto crece, las decisiones técnicas (elección de framework, estructura de carpetas, manejo de errores, estrategia de tests) se acumulan y se olvidan. Cuando alguien (humano o agente) llega después y pregunta "¿por qué se hizo así?", la respuesta suele ser "no me acuerdo" o "Fulano lo decidió hace 6 meses". Esto lleva a:

- Reescrituras innecesarias porque nadie recuerda por qué algo está como está.
- Inconsistencias cuando alguien decide diferente sin saber del precedente.
- IA que toma decisiones contradictorias entre sesiones.

## Decisión

Toda decisión técnica con impacto arquitectónico se documenta como ADR en `docs/adr/`.

Formato: nombre `NNNN-titulo-corto.md`, numeración secuencial.

Estructura: Estado, Contexto, Decisión, Consecuencias, Alternativas consideradas.

Las decisiones triviales (nombre de variable, qué color usar) NO requieren ADR.

Una decisión amerita ADR si:
- Cambia el stack o una dependencia mayor.
- Cambia la estructura de módulos.
- Define un patrón que se va a repetir en muchos lugares.
- Es un tradeoff serio entre opciones razonables.
- Cuesta más de un día deshacerla.

## Consecuencias

**Buenas:**
- Histórico de razonamiento, no solo de código.
- Claude Code (vía `CLAUDE.md`) lee los ADRs antes de proponer cambios estructurales.
- Onboarding más rápido de nuevos miembros (humanos o IA).

**Malas:**
- Overhead de escribir el ADR. Mitigación: ADRs cortos, 1 página, no tesis.
- Riesgo de olvidar actualizar un ADR cuando cambia. Mitigación: cuando una decisión se reemplaza, el ADR viejo se marca como "Reemplazado por ADR-XXXX" pero NO se borra.

**Neutras:**
- Aumenta el tamaño del repo en docs, pero son archivos pequeños.

## Alternativas consideradas

- **Wiki externa (Notion, Confluence):** se desincroniza del código. Descartado.
- **Comentarios en código:** se pierden cuando el archivo se borra o reorganiza. Descartado para decisiones arquitectónicas.
- **No documentar:** opción default, ya vimos cómo termina. Descartado.
