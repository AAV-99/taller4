# Slides Unidad 4 — Listas y diccionarios

## Listas
- Una lista es una colección ordenada y mutable: `notas = [3.5, 4.0, 2.8]`.
- Se accede por índice desde 0: `notas[0]` es el primer elemento y `notas[-1]` el último. Acceder a un índice que no existe produce `IndexError`.
- Métodos útiles: `append` agrega al final, `len(lista)` da la cantidad de elementos, `sum(lista)` suma valores numéricos.

## Construir una lista filtrada
- Patrón: crear una lista vacía antes del ciclo, recorrer la lista original y hacer `append` solo de los elementos que cumplen la condición.
- Las comprensiones de listas expresan el mismo patrón en una línea: `[x for x in datos if condicion(x)]`. Primero domina la versión con ciclo; la comprensión es un atajo, no un requisito.

## Diccionarios
- Un diccionario asocia claves con valores: `conteo = {"bajo": 0, "medio": 0, "alto": 0}`.
- Se lee un valor con `conteo["bajo"]` y se actualiza con `conteo["bajo"] += 1`. Leer una clave que no existe produce `KeyError`.
- `dic.get(clave, valor_por_defecto)` evita el `KeyError` cuando la clave puede no existir.

## Recorrer un diccionario
- `for clave in dic:` recorre las claves.
- `for clave, valor in dic.items():` recorre pares clave-valor; es la forma más clara cuando se necesitan ambos.
- `dic.values()` entrega solo los valores.

## Contar por categorías con un diccionario
- Patrón de conteo: (1) inicializar el diccionario con todas las categorías en 0 o empezar vacío y usar `get`; (2) recorrer los datos; (3) decidir con `if/elif` a qué categoría pertenece cada dato; (4) incrementar el contador de esa categoría.
- Error frecuente: crear el diccionario dentro del ciclo (se reinicia en cada vuelta) o usar como clave el dato en lugar de la categoría.

## Errores frecuentes de la unidad
1. `IndexError` por usar `range(len(lista) + 1)` o índices fijos.
2. `KeyError` por leer claves no inicializadas.
3. Confundir `dic.items()` con `dic.keys()`.
4. Modificar una lista mientras se recorre.
5. Comparar listas con `is` en vez de `==`.
