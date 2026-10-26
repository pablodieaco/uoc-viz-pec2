import json

import pandas as pd
import plotly.graph_objects as go
from loguru import logger

import comun

ARCHIVO_DATOS = "renta_sexo.csv"
AÑOS_ATRAS = 10
PARIDAD = 100
# azul petróleo neutro: nada de rosa/azul por sexo, que refuerza el estereotipo
COLOR_BARRA = "#1d5c73"
COLOR_FONDO_ARCO = "#ececec"
NOMBRES = {"Spain": "España", "European Union (27)": "UE-27", "World": "Mundo"}


def cargar_renta() -> pd.DataFrame:
    renta = pd.read_csv(comun.PROCESSED / ARCHIVO_DATOS)
    renta["entidad"] = renta["entity"].map(NOMBRES)
    return renta.pivot(index="year", columns="entidad", values="ratio")


def elegir_años(ratios: pd.DataFrame) -> tuple[int, int]:
    """Último año con dato y el de AÑOS_ATRAS antes (o el primero disponible)."""
    ultimo = int(ratios["España"].last_valid_index())
    referencia = ultimo - AÑOS_ATRAS
    if referencia not in ratios.index:
        referencia = int(ratios["España"].first_valid_index())
    return ultimo, referencia


def crear_gauge(
    valor: float, referencia: float, año_ref: int, titulo: str, grande: bool
) -> go.Figure:
    """Crea un gráfico de tipo gauge con Plotly.
    Referencia: https://plotly.com/python/gauge-charts/
    """
    indicador = go.Indicator(
        mode="gauge+number+delta",
        value=valor,
        # en los pequeños Plotly monta el título sobre el número: ahí va como etiqueta HTML
        title={
            "text": titulo if grande else "",
            "font": {"size": 18, "color": comun.COLOR_TEXTO},
        },
        number={
            "suffix": " %",
            "valueformat": ".1f",
            "font": {"size": 40 if grande else 20, "color": comun.COLOR_TEXTO},
        },
        delta={
            "reference": referencia,
            "valueformat": ".1f",
            "suffix": f" p. p. desde {año_ref}",
            "increasing": {"symbol": "+", "color": COLOR_BARRA},
            "decreasing": {"symbol": "−", "color": comun.COLOR_SECUNDARIO},
            "font": {"size": 16 if grande else 12},
        },
        gauge={
            # la escala llega a la paridad (100 %): recortarla exageraría lo cerca que está
            "axis": {
                "range": [0, PARIDAD],
                "tickvals": [0, 25, 50, 75, 100] if grande else [0, 100],
                "ticktext": ["0 %", "25 %", "50 %", "75 %", "Paridad"]
                if grande
                else ["0 %", "100 %"],
                "tickcolor": comun.COLOR_EJES,
                "tickfont": {
                    "color": comun.COLOR_SECUNDARIO,
                    "size": 12 if grande else 10,
                },
            },
            "bar": {"color": COLOR_BARRA, "thickness": 0.6},
            "bgcolor": COLOR_FONDO_ARCO,
            "borderwidth": 0,
            "threshold": {
                "value": PARIDAD,
                "line": {"color": comun.COLOR_TEXTO, "width": 3},
                "thickness": 1,
            },
        },
    )
    fig = go.Figure(indicador)
    fig.update_layout(
        height=320 if grande else 130,
        margin={"t": 60, "b": 10, "l": 60, "r": 60}
        if grande
        else {"t": 0, "b": 5, "l": 40, "r": 40},
        font={"family": comun.FUENTE},
        separators=",.",
        paper_bgcolor="white",
    )
    return fig


def html_gauges(ratios: pd.DataFrame, ultimo: int, referencia: int) -> str:
    """España en grande y, debajo, la UE-27 y el mundo en pequeño como referencia."""
    config = {"displayModeBar": False, "responsive": True}
    figuras = [
        crear_gauge(
            ratios.loc[ultimo, entidad],
            ratios.loc[referencia, entidad],
            referencia,
            f"{entidad}, {ultimo}",
            entidad == "España",
        )
        for entidad in ["España", "UE-27", "Mundo"]
    ]
    # plotly.js se carga una sola vez, con el primer gráfico
    html = [
        fig.to_html(
            full_html=False, include_plotlyjs="cdn" if i == 0 else False, config=config
        )
        for i, fig in enumerate(figuras)
    ]
    pequenos = "".join(
        f'<div><p class="etiqueta">{entidad}, {ultimo}</p>{grafico}</div>\n'
        for entidad, grafico in zip(["UE-27", "Mundo"], html[1:])
    )
    return f'{html[0]}\n<div class="gauges-pequenos">\n{pequenos}</div>'


if __name__ == "__main__":
    ratios = cargar_renta()
    ultimo, referencia = elegir_años(ratios)
    espana = ratios["España"]
    logger.info(f"Año: {ultimo}, referencia: {referencia}")
    logger.info(
        f"Ratios en esos años:\n{ratios.loc[[referencia, ultimo]].round(1).to_string()}"
    )
    logger.info(f"Máximo de España: {espana.max():.1f} % en {espana.idxmax()}")
    logger.info(f"España, últimos años: {espana.tail(5).round(1).to_dict()}")

    metadata = json.loads(
        (comun.RAW / "gni_sexo_metadata.json").read_text(encoding="utf-8")
    )
    cita = metadata["columns"]["gni_pc__sex_female"]["citationShort"]

    contexto = (
        f'<p class="contexto">En {ultimo}, por cada 100 dólares de renta per cápita de los hombres, '
        f"las mujeres tenían {comun.numero(espana[ultimo], 0)}. En {referencia} eran "
        f"{comun.numero(espana[referencia], 0)}. El máximo fue en {espana.idxmax()}, con "
        f"{comun.numero(espana.max(), 0)}.</p>"
    )

    comun.guardar_pagina(
        "gauge.html",
        tecnica="Gauge",
        titulo="¿Cuánto le falta a España para la paridad de ingresos?",
        subtitulo=(
            f"Las mujeres ingresan {comun.numero(espana[ultimo], 0)} de cada 100 que ingresan los "
            f"hombres: faltan {comun.numero(PARIDAD - espana[ultimo], 0)} puntos para la paridad. "
            f"En diez años la brecha se ha reducido "
            f"{comun.numero(espana[ultimo] - espana[referencia], 0)} puntos."
        ),
        descripcion=(
            f"Indicador semicircular de 0 a 100 %: la renta per cápita de las mujeres en España es el "
            f"{comun.numero(espana[ultimo])} % de la de los hombres en {ultimo}, frente al "
            f"{comun.numero(espana[referencia])} % de {referencia}. Debajo, la UE-27 y el mundo."
        ),
        grafico=html_gauges(ratios, ultimo, referencia) + contexto,
        como_se_lee=(
            "<p>El arco va de 0 a 100 %. La barra muestra cuánto ingresan las mujeres por cada 100 "
            "que ingresan los hombres, y la línea negra del final marca la <strong>paridad</strong> "
            "(100 %): cuanto más cerca está la barra de la línea, menor es la brecha. Debajo del "
            f"número aparece cuántos puntos ha cambiado desde {referencia}. Los dos indicadores "
            "pequeños dan contexto con la Unión Europea y el mundo.</p>"
            "<p>Es una <strong>estimación</strong> del PNUD. La renta de cada país no se mide por "
            "sexo, sino que se reparte entre mujeres y hombres según la brecha salarial y el peso de "
            "cada sexo en la población activa. Por eso el indicador recoge a la vez la diferencia de "
            "salarios y la menor participación de las mujeres en el trabajo remunerado.</p>"
        ),
        fuente=(
            f"Fuente: {cita} "
            '(<a href="https://ourworldindata.org/grapher/gross-national-income-per-capita-males-vs-females">'
            "Our World in Data</a>). Renta nacional bruta per cápita en dólares internacionales a "
            "precios de 2021; el ratio es renta de las mujeres / renta de los hombres × 100. Licencia "
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.'
        ),
        datos=ARCHIVO_DATOS,
        codigo="gauge_brecha_renta.py",
    )
    logger.success("Guardado docs/gauge.html")
