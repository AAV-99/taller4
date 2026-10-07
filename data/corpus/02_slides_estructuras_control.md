# Slides Unidad 2 — Estructuras de control y repetición

## Condicionales
- `if condicion:` ejecuta el bloque indentado solo si la condición es verdadera.
- `elif` permite evaluar condiciones adicionales en orden; la primera verdadera gana.
- `else` captura todos los casos restantes.
- Regla de oro: el bloque de un `if` se define por la indentación (4 espacios). Un error de indentación cambia el significado del programa o produce `IndentationError`.

## Ciclo for y range
- `for elemento in coleccion:` recorre cada elemento de una lista, cadena o diccionario.
- `range(n)` genera los números 0, 1, ..., n-1. `range(a, b)` va de a hasta b-1. `range(a, b, paso)` usa un incremento.
- Ejemplo mental: para recorrer una lista de notas no se necesita `range`; basta `for nota in notas:`.

## Ciclo while
- `while condicion:` repite mientras la condición sea verdadera.
- Siempre debe existir algo dentro del ciclo que haga falsa la condición; si no, se produce un ciclo infinito.

## Acumuladores y contadores
- Un acumulador es una variable que guarda una suma parcial. Se inicializa ANTES del ciclo (por ejemplo en 0) y se actualiza DENTRO del ciclo (`total = total + nota` o `total += nota`).
- Un contador cuenta cuántas veces ocurre algo: se inicializa en 0 y se incrementa en 1 cuando se cumple una condición.
- Error frecuente: inicializar el acumulador dentro del ciclo, lo que lo reinicia en cada vuelta y el resultado queda igual al último elemento.

## Errores frecuentes de la unidad
1. Olvidar los dos puntos `:` al final de `if`, `for` o `while`.
2. Indentación inconsistente (mezclar tabuladores y espacios).
3. Usar `range(len(lista))` cuando solo se necesitan los valores, y luego confundir índice con valor.
4. Modificar una lista mientras se recorre con `for`.
5. Dividir entre la cantidad de elementos sin verificar que la lista no esté vacía (`ZeroDivisionError`).

## Estrategia para resolver un ejercicio de ciclos
1. Escribe en español qué debe pasar con UN elemento.
2. Identifica qué variable acumula o cuenta y con qué valor empieza.
3. Escribe el ciclo y prueba con una lista de 2 o 3 elementos a mano (prueba de escritorio).
4. Revisa los casos borde: lista vacía, un solo elemento, valores repetidos.
