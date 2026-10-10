# Assignment 2 — Analyzing the grades of a class

## Context
The course coordinator has the final grades of a class in a list of real numbers between 0.0 and 5.0, for example `notas = [4.5, 2.9, 3.0, 3.8, 1.5, 4.9]`. You must write functions to analyze them. Using pandas or any external library is not allowed in this assignment. Function names and dictionary keys must be written exactly as specified (in Spanish).

## Exercise 1 — calcular_promedio
Write the function `calcular_promedio(notas)` that receives a list of grades and returns (with `return`) their average rounded to 2 decimals. If the list is empty it must return `0.0`.
- Concepts assessed: functions, accumulators, loops, `return`, edge cases.

## Exercise 2 — filtrar_aprobados
Write the function `filtrar_aprobados(notas, minimo=3.0)` that returns a NEW list containing only the grades greater than or equal to `minimo`, without modifying the original list.
- Concepts assessed: lists, conditionals, building filtered lists, default parameters.

## Exercise 3 — contar_por_rango
Write the function `contar_por_rango(notas)` that returns a dictionary with the number of grades in each range: `"bajo"` (below 3.0), `"medio"` (from 3.0 up to, but not including, 4.0) and `"alto"` (4.0 or more).
- Concepts assessed: dictionaries, chained conditionals `if/elif/else`, counters.

## Required tests
- The average of `[4.0, 3.0]` is `3.5` and the average of an empty list is `0.0`.
- `filtrar_aprobados([2.0, 3.0, 4.5])` returns `[3.0, 4.5]`.
- `contar_por_rango([2.0, 3.0, 4.5, 4.0])` returns `{"bajo": 1, "medio": 1, "alto": 2}`.

## Rubric
| Criterion | Weight |
|---|---|
| Functions return (not print) the correct result | 40 % |
| Edge case handling | 20 % |
| Readable code: names, docstrings | 20 % |
| `assert` tests included | 20 % |

## Submission
A notebook `taller2_<username>.ipynb` with the three functions, their docstrings and the tests. Deadline: week 8.
