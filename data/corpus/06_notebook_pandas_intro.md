# Notebook Unidad 5 — Introducción a pandas

## Series y DataFrame
- Una `Series` es una columna de datos con índice. Un `DataFrame` es una tabla formada por varias `Series` que comparten índice.
- Se importa con `import pandas as pd` por convención.

## Leer datos
- `pd.read_csv("archivo.csv")` carga un CSV en un DataFrame.
- `df.head()` muestra las primeras filas; `df.info()` muestra columnas, tipos y valores nulos; `df.describe()` da estadísticas básicas.

## Seleccionar y filtrar
- `df["columna"]` selecciona una columna (Series). `df[["a", "b"]]` selecciona varias (DataFrame).
- Filtrado con máscaras booleanas: `df[df["nota"] >= 3.0]` devuelve solo las filas que cumplen la condición.
- Para combinar condiciones se usan `&` y `|` con paréntesis: `df[(df["nota"] >= 3.0) & (df["grupo"] == "A")]`. Usar `and`/`or` produce un `ValueError` de ambigüedad.

## Agrupar
- `df.groupby("grupo")["nota"].mean()` calcula el promedio de nota por grupo.
- `df["nota"].value_counts()` cuenta ocurrencias de cada valor.

## Relación con el Taller 2
Las funciones del Taller 2 (promedio, filtrado y conteo por rangos) son la versión "a mano" de lo que pandas hace con `mean()`, máscaras booleanas y `pd.cut` + `value_counts()`. Primero se aprende la lógica con listas y diccionarios; luego pandas la abrevia.

## Errores frecuentes de la unidad
1. `KeyError` por escribir mal el nombre de una columna (mayúsculas, espacios).
2. Usar `and`/`or` en lugar de `&`/`|` al filtrar.
3. Olvidar los paréntesis alrededor de cada condición.
4. Modificar una copia de un filtro y esperar que cambie el DataFrame original (`SettingWithCopyWarning`).
