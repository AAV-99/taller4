# Taller 2 — Análisis de notas de un grupo

## Contexto
El coordinador del curso tiene las notas finales de un grupo en una lista de números reales entre 0.0 y 5.0, por ejemplo `notas = [4.5, 2.9, 3.0, 3.8, 1.5, 4.9]`. Debes escribir funciones que permitan analizarlas. No se permite usar pandas ni librerías externas en este taller.

## Ejercicio 1 — calcular_promedio
Escribe la función `calcular_promedio(notas)` que reciba una lista de notas y devuelva (con `return`) su promedio redondeado a 2 decimales. Si la lista está vacía debe devolver `0.0`.
- Conceptos evaluados: funciones, acumuladores, ciclos, `return`, casos borde.

## Ejercicio 2 — filtrar_aprobados
Escribe la función `filtrar_aprobados(notas, minimo=3.0)` que devuelva una NUEVA lista solo con las notas mayores o iguales a `minimo`, sin modificar la lista original.
- Conceptos evaluados: listas, condicionales, construcción de listas filtradas, parámetros por defecto.

## Ejercicio 3 — contar_por_rango
Escribe la función `contar_por_rango(notas)` que devuelva un diccionario con la cantidad de notas en cada rango: `"bajo"` (menor que 3.0), `"medio"` (de 3.0 a menor que 4.0) y `"alto"` (4.0 o más).
- Conceptos evaluados: diccionarios, condicionales encadenados `if/elif/else`, contadores.

## Pruebas mínimas que deben pasar
- El promedio de `[4.0, 3.0]` es `3.5` y el de una lista vacía es `0.0`.
- `filtrar_aprobados([2.0, 3.0, 4.5])` devuelve `[3.0, 4.5]`.
- `contar_por_rango([2.0, 3.0, 4.5, 4.0])` devuelve `{"bajo": 1, "medio": 1, "alto": 2}`.

## Rúbrica
| Criterio | Peso |
|---|---|
| Las funciones devuelven (no imprimen) el resultado correcto | 40 % |
| Manejo de casos borde | 20 % |
| Código legible: nombres, docstrings | 20 % |
| Pruebas con `assert` incluidas | 20 % |

## Entrega
Un notebook `taller2_<usuario>.ipynb` con las tres funciones, sus docstrings y las pruebas. Fecha límite: semana 8.
