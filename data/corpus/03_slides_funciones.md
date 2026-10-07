# Slides Unidad 3 — Funciones

## Definir una función
- Se define con `def nombre(parametros):` y un bloque indentado.
- Los parámetros son variables locales que reciben los valores (argumentos) con los que se llama la función.
- Una buena función hace una sola cosa y tiene un nombre que describe esa cosa con un verbo: `calcular_total`, `es_par`, `filtrar_validos`.

## Return vs print
- `return valor` termina la función y ENTREGA el valor a quien la llamó; ese valor puede guardarse en una variable o usarse en otra operación.
- `print(valor)` solo MUESTRA el valor en pantalla; la función devuelve `None` si no tiene `return`.
- Síntoma clásico de confundirlos: `resultado = mi_funcion(datos)` y luego `resultado` vale `None`, o una prueba con `assert` falla aunque "en pantalla se ve bien".
- Analogía: `print` es decir la respuesta en voz alta; `return` es escribirla en un papel y entregárselo a quien preguntó.

## Alcance de variables
- Las variables creadas dentro de la función son locales: no existen fuera de ella.
- Si una función necesita un dato, debe recibirlo como parámetro; evita depender de variables globales.

## Docstrings y pruebas con assert
- Un docstring es una cadena entre triples comillas justo debajo del `def` que explica qué hace la función, qué recibe y qué devuelve.
- `assert expresion` verifica una condición; si es falsa, el programa se detiene con `AssertionError`. Sirve para probar funciones con casos conocidos, por ejemplo `assert es_par(4) == True`.

## Casos borde
- Antes de entregar una función, pruébala con entradas extremas: lista vacía, un solo elemento, valores negativos, valores en el límite de un rango.
- Decide y documenta qué devuelve la función en un caso borde (por ejemplo, 0 o `None` para una lista vacía).

## Errores frecuentes de la unidad
1. Usar `print` en lugar de `return`.
2. Poner el `return` dentro del ciclo, lo que termina la función en la primera iteración.
3. Llamar la función sin paréntesis (`mi_funcion` en vez de `mi_funcion(x)`).
4. Olvidar pasar argumentos o pasarlos en otro orden.
5. Redefinir sin querer el nombre de una función con una variable.
