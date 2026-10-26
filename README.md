# uoc-viz-pec2

Proyecto para el desarrollo de la PEC2 de la asignatura Visualización de datos del máster universitario de Ciencia de Datos de la UOC de Pablo de Diego Acosta.

En esta PEC trabajo tres técnicas de visualización partiendo de la técnica y buscando después unos datos abiertos que encajen con ella: un **heatmap de calendario**, un **gauge** y un **horizon graph**. Cada una se publica como una página HTML en GitHub Pages.

## Datos

Uso tres conjuntos de datos abiertos. Los descargo con un script (ver más abajo) y guardo una copia, para que el resultado se pueda reproducir aunque la fuente cambie.

### Demanda eléctrica diaria de España en 2025 (heatmap)

Es la demanda eléctrica nacional de cada día de 2025, en MWh (en las gráficas la paso a GWh). Son 365 valores, uno por día. Viene de la API pública **REData** de Red Eléctrica, que no necesita clave.

- Documentación de la API: <https://www.ree.es/es/datos/apidatos>
- Consulta que uso: <https://apidatos.ree.es/es/datos/demanda/evolucion?start_date=2025-01-01T00:00&end_date=2025-12-31T23:59&time_trunc=day>
- Cita: *Fuente: Red Eléctrica, REData (apidatos.ree.es).* El [aviso legal de REE](https://www.ree.es/es/aviso-legal) permite reutilizar los datos con fines informativos y no comerciales, siempre que se cite a REE como fuente y se indique la fecha de actualización.

### Renta per cápita de mujeres y hombres (gauge)

Es la renta nacional bruta per cápita estimada de mujeres y de hombres, por país y año (1990-2023), en dólares internacionales a precios de 2021. A partir de ella calculo cuánto ingresan las mujeres por cada 100 que ingresan los hombres. Es una **estimación** del PNUD: reparte la renta total de cada país entre sexos según la brecha salarial y la participación de cada sexo en el mercado laboral. Por eso mide a la vez ambas cosas.

- Página: <https://ourworldindata.org/grapher/gross-national-income-per-capita-males-vs-females>
- Cita: *UNDP, Human Development Report (2025) – with minor processing by Our World in Data.*
- Licencia: CC BY 4.0 ([Our World in Data](https://ourworldindata.org/faqs#can-i-use-or-reproduce-your-data)).

### Anomalías mensuales de temperatura por país (horizon graph)

Es la diferencia entre la temperatura media de cada mes y la media de ese mismo mes en 1991-2020, en °C, por país y desde 1940. Me quedo con 16 países europeos, ordenados de norte a sur, desde enero de 1980. Our World in Data la calcula a partir del reanálisis ERA5 de Copernicus.

- Página: <https://ourworldindata.org/grapher/country-level-monthly-temperature-anomalies>
- Cita: *Contains modified Copernicus Climate Change Service information (2026) – with major processing by Our World in Data.*
- Licencia: CC BY 4.0 ([Our World in Data](https://ourworldindata.org/faqs#can-i-use-or-reproduce-your-data)).

## Cómo ejecutarlo

Necesitas Python 3.11 o superior.

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

python src/descargar_datos.py
```

El script descarga las tres fuentes y deja dos copias:

- `data/raw/`: los datos tal como llegan: el JSON de REE, los CSV de OWID con sus metadatos y la fecha de la descarga.
- `data/processed/`: los CSV ya preparados para graficar (`demanda_diaria_2025.csv`, `renta_sexo.csv` y `anomalias_europa.csv`).

Mientras descarga, muestra en consola algunas comprobaciones: que hay 365 días sin huecos, los valores de España por año, el rango entre países, etc.

El CSV completo de temperaturas pesa bastante y no lo subo al repositorio, pero los CSV de `data/processed/` sí están versionados. Si solo quieres generar las gráficas, no hace falta volver a descargar nada.
