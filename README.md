# Diagnóstico del consumo eléctrico con lógica difusa

Proyecto de Inteligencia Artificial · Tecnológico Nacional de México, Campus Culiacán.

La aplicación pronostica el consumo eléctrico de los electrodomésticos para el siguiente
intervalo de 10 minutos con **Chronos-Bolt Tiny**, lo compara con el consumo habitual,
calcula una prioridad de verificación con un **sistema difuso de Sugeno de orden cero** y
sugiere acciones de ahorro respaldadas por publicaciones de la **CFE**.

## Datos y modelo

- Modelo: [Chronos-Bolt Tiny](https://huggingface.co/amazon/chronos-bolt-tiny) (`amazon/chronos-bolt-tiny`).
  Se descarga automáticamente la primera vez que se ejecuta.
- Dataset: Smart Home Appliance Energy Prediction (Hugging Face), partición `train`.
  Se usan solo las columnas `date` y `Appliances`. Enlace: `<PEGAR AQUÍ EL ENLACE DEL DATASET>`.
- Ficha del conjunto original en UCI: <https://archive.ics.uci.edu/dataset/374/appliances+energy+prediction>
- Fuentes de las recomendaciones (CFE): *Somos más que ahorro* y *¡Y se hizo la luz!*.
  Enlaces: `<https://app.cfe.mx/Libros/LIBRO_Somos_mas_que_ahorro.pdf> <https://app.cfe.mx/Libros/LIBRO_se_hizo_la_luz.pdf>  `.

El archivo `data/train.parquet` ya está incluido en el repositorio.

## Instalación

Requiere Python 3.10 o superior (probado con 3.14).

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS
python -m pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`. Modos de la aplicación:

1. **Históricos (H1–H3)**: corre Chronos en los cortes de la tarea y muestra pronóstico,
   referencia, entradas difusas, reglas activadas, prioridad y recomendaciones. La lectura
   real se revela después, con el error de Chronos y el de la última lectura.
2. **Pruebas controladas (C1–C5)**: valores de la tabla 6.2 cargados directamente.
3. **Corte libre**: cualquier corte real del dataset.
4. **Diseño del sistema**: funciones de pertenencia, matriz de Sugeno y registro de reglas.

Scripts de apoyo:

```bash
python run_chronos.py data/train.parquet        # P10/P50/P90 de H1-H3 -> resultados_chronos.json
python buscar_traslape.py data/train.parquet    # busca un corte real en el traslape
python probar_logica_difusa.py                  # pruebas del sistema difuso
python probar_recomendaciones.py                # pruebas de las reglas de la CFE
```

## Estructura

```
app.py                  interfaz Streamlit
pronostico.py           carga de datos, validación de cortes, referencia y Chronos
logica_difusa.py        funciones de pertenencia, 9 reglas de Sugeno e inferencia
recomendaciones.py      reglas de recomendación derivadas de la CFE
run_chronos.py          corre Chronos en H1-H3
buscar_traslape.py      busca un caso real en el traslape
data/train.parquet      dataset (columnas date y Appliances usadas)
```