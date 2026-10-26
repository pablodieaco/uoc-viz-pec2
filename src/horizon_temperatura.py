import json

import altair as alt
import pandas as pd
from loguru import logger

import comun

ARCHIVO_DATOS = "anomalias_europa.csv"
# las bandas son 4 filas por mes y país (unas 36.000 por gráfico): incrustadas en la página
# pesarían varios MB, así que cada gráfico las lee de un CSV aparte
ARCHIVO_MENSUAL = "datos/horizon_mensual.csv"
ARCHIVO_12M = "datos/horizon_12m.csv"
# la anomalía de un mes cambia de signo respecto al anterior el 40 % de las veces;
# con la media de los últimos 12 meses solo el 7 %, y se ve la tendencia
MESES_MEDIA = 12
# anchos elegidos para que en los dos gráficos el 65 % de los valores quede en la banda
# clara y solo sature un 7 % (ver notebook)
ANCHO_MENSUAL = 1.5
ANCHO_12M = 0.75
INICIO_DIDACTICO = "2015-01-01"
ANCHO_GRAFICO = 760
ALTO_FILA = 28
# RdBu de ColorBrewer: rojo para el calor, azul para el frío; más oscuro en la banda 2
COLORES = ["#f4a582", "#b2182b", "#92c5de", "#2166ac"]
# step-after: un valor por mes, en escalones, sin inventar una curva entre meses
INTERPOLACION = "step-after"
TOOLTIP_MES = [
    alt.Tooltip("pais:N", title="País"),
    alt.Tooltip("fecha:T", title="Mes", format="%m/%Y"),
    alt.Tooltip("anomalia:Q", title="Anomalía del mes (°C)", format="+,.1f"),
]
TOOLTIP_12M = TOOLTIP_MES[:2] + [
    alt.Tooltip("media_12m:Q", title="Media últimos 12 meses (°C)", format="+,.2f"),
    TOOLTIP_MES[2],
]


def cargar_temperatura() -> pd.DataFrame:
    temperatura = pd.read_csv(comun.PROCESSED / ARCHIVO_DATOS, parse_dates=["fecha"])
    logger.info(
        f"{temperatura['pais'].nunique()} países, de {temperatura['fecha'].min():%m/%Y} "
        f"a {temperatura['fecha'].max():%m/%Y}, {len(temperatura)} filas"
    )
    return temperatura


def calcular_media_movil(temperatura: pd.DataFrame) -> pd.DataFrame:
    """Añade la anomalía media de los últimos 12 meses; los 11 primeros meses de cada país no la tienen."""
    media = temperatura.groupby("pais")["anomalia"].transform(
        lambda s: s.rolling(MESES_MEDIA).mean()
    )
    return temperatura.assign(media_12m=media).dropna(subset=["media_12m"])


def leyenda(ancho: float) -> list[str]:
    """Textos de las 4 bandas, en el mismo orden que COLORES."""
    a, b = (f"{valor:g}".replace(".", ",") for valor in [ancho, 2 * ancho])
    return [
        f"+0 a +{a} °C",
        f"+{a} a +{b} °C o más",
        f"−0 a −{a} °C",
        f"−{a} a −{b} °C o menos",
    ]


def bandas_horizonte(df: pd.DataFrame, columna: str, ancho: float) -> pd.DataFrame:
    """Parte cada valor en 2 bandas de altura `ancho`, por separado para el calor y el frío."""
    partes = []
    for signo, valor in [
        ("+", df[columna].clip(lower=0)),
        ("−", (-df[columna]).clip(lower=0)),
    ]:
        # el signo contrario queda con altura 0 en vez de quitarlo: si no, el área uniría los huecos
        partes.append(df.assign(signo=signo, banda=1, altura=valor.clip(upper=ancho)))
        partes.append(
            df.assign(
                signo=signo, banda=2, altura=(valor - ancho).clip(lower=0, upper=ancho)
            )
        )
    bandas = pd.concat(partes, ignore_index=True)
    bandas["tono"] = (bandas["signo"] + bandas["banda"].astype(str)).map(
        dict(zip(["+1", "+2", "−1", "−2"], leyenda(ancho)))
    )
    satura = (df[columna].abs() > 2 * ancho).mean() * 100
    logger.info(f"Bandas de {columna} con ancho {ancho} °C: satura el {satura:.1f} %")
    return bandas


def calcular_insight(temperatura: pd.DataFrame) -> dict:
    decada = temperatura["fecha"].dt.year // 10 * 10
    calidos = temperatura.groupby(decada)["anomalia"].apply(
        lambda s: (s > 0).mean() * 100
    )
    logger.info(
        f"% de meses más cálidos que 1991-2020, por década: {calidos.round(1).to_dict()}"
    )
    recientes = temperatura[decada == decada.max()]
    por_pais = (
        recientes.groupby("pais")["anomalia"]
        .apply(lambda s: (s > 0).mean() * 100)
        .sort_values()
    )
    logger.info(
        f"% de meses cálidos desde {decada.max()}, por país:\n{por_pais.round(1).to_string()}"
    )
    columnas = ["pais", "fecha", "anomalia"]
    logger.info(
        "Meses más cálidos:\n"
        + temperatura.nlargest(5, "anomalia")[columnas].to_string(index=False)
    )
    logger.info(
        "Meses más fríos:\n"
        + temperatura.nsmallest(5, "anomalia")[columnas].to_string(index=False)
    )
    return {"calidos": calidos, "por_pais": por_pais}


def guardar_bandas(bandas: pd.DataFrame, archivo: str) -> None:
    columnas = [
        "pais",
        "fecha",
        "anomalia",
        "media_12m",
        "signo",
        "banda",
        "tono",
        "altura",
    ]
    columnas = [columna for columna in columnas if columna in bandas]
    ruta = comun.DOCS / archivo
    ruta.parent.mkdir(exist_ok=True)
    bandas[columnas].round({"anomalia": 2, "media_12m": 2, "altura": 3}).to_csv(
        ruta, index=False, date_format="%Y-%m-%dT00:00"
    )
    logger.info(
        f"Guardado docs/{archivo}: {len(bandas)} filas, {ruta.stat().st_size / 1e6:.1f} MB"
    )


def color_bandas(ancho: float, leyenda_visible: bool = True) -> alt.Color:
    return alt.Color(
        "tono:N",
        scale=alt.Scale(domain=leyenda(ancho), range=COLORES),
        legend=(
            alt.Legend(
                title=None,
                orient="top",
                direction="horizontal",
                columns=4,
                symbolType="square",
                labelFontSize=12,
            )
            if leyenda_visible
            else None
        ),
    )


def crear_horizon(
    archivo: str, ancho: float, tooltip: list, paises: list[str]
) -> alt.FacetChart:
    # el número de marcas se adapta al zoom: solo el año en enero y mes y año en el resto
    etiqueta = "month(datum.value) == 0 ? timeFormat(datum.value, '%Y') : timeFormat(datum.value, '%b %Y')"
    x = alt.X("fecha:T", title=None, axis=alt.Axis(tickCount=10, labelExpr=etiqueta))
    y = alt.Y("altura:Q", stack=None, scale=alt.Scale(domain=[0, ancho]), axis=None)
    base = (
        alt.Chart()
        .mark_area(interpolate=INTERPOLACION, clip=True)
        .encode(x=x, y=y, color=color_bandas(ancho))
    )
    # una capa por banda para que la oscura se pinte siempre encima de la clara
    # zoom solo en el eje X (rueda del ratón o pellizco) y arrastrar para moverse;
    # doble clic vuelve a la vista completa. Todas las filas comparten el eje y se mueven juntas
    zoom = alt.selection_interval(bind="scales", encodings=["x"])
    banda_1 = base.transform_filter("datum.banda == 1").add_params(zoom)
    banda_2 = base.transform_filter("datum.banda == 2")
    # barras invisibles de un mes de ancho, solo para el tooltip (una por mes y país)
    barras_tooltip = (
        alt.Chart()
        .mark_bar(opacity=0, clip=True)
        .encode(x=alt.X("yearmonth(fecha):T"), tooltip=tooltip)
        .transform_filter("datum.banda == 1 && datum.signo == '+'")
    )
    return (
        alt.layer(banda_1, banda_2, barras_tooltip, data=archivo)
        .properties(width=ANCHO_GRAFICO, height=ALTO_FILA)
        .facet(
            row=alt.Row(
                "pais:N",
                sort=paises,
                title=None,
                header=alt.Header(
                    labelAngle=0,
                    labelAlign="left",
                    labelBaseline="middle",
                    labelAnchor="middle",
                    labelOrient="left",
                    labelFontSize=12,
                ),
            ),
            spacing=2,
        )
    )


def crear_didactico(bandas: pd.DataFrame) -> alt.HConcatChart:
    """Los tres pasos de la técnica con España: área, área cortada en bandas y bandas plegadas."""
    espana = bandas[
        (bandas["pais"] == "España") & (bandas["fecha"] >= INICIO_DIDACTICO)
    ].copy()
    sentido = espana["signo"].map({"+": 1, "−": -1})
    # sin plegar: la banda 2 empieza donde acaba la 1, hacia arriba o hacia abajo según el signo
    espana["desde"] = (espana["banda"] - 1) * ANCHO_12M * sentido
    espana["hasta"] = espana["desde"] + espana["altura"] * sentido

    x = alt.X(
        "fecha:T",
        title=None,
        axis=alt.Axis(format="%Y", tickCount={"interval": "year", "step": 5}),
    )
    escala = alt.Scale(domain=[-2 * ANCHO_12M, 2 * ANCHO_12M])
    eje = alt.Axis(values=[-1.5, -0.75, 0, 0.75, 1.5], format="+,.2f", title="°C")
    color = color_bandas(ANCHO_12M, leyenda_visible=False)
    base = (
        alt.Chart(espana)
        .mark_area(interpolate=INTERPOLACION)
        .encode(x=x)
        .properties(width=210, height=120)
    )
    titulo = {
        "font": comun.FUENTE,
        "fontSize": 12,
        "fontWeight": "normal",
        "anchor": "start",
        "color": comun.COLOR_TEXTO,
    }

    # paso 1: las dos bandas de cada signo juntas, sin cortar
    area = (
        base.transform_filter("datum.banda == 1")
        .encode(
            y=alt.Y("valor:Q", scale=escala, axis=eje),
            color=alt.Color(
                "signo:N",
                scale=alt.Scale(domain=["+", "−"], range=["#d6604d", "#4393c3"]),
                legend=None,
            ),
        )
        .transform_calculate(
            valor="datum.signo == '+' ? max(datum.media_12m, 0) : min(datum.media_12m, 0)"
        )
    )
    cortada = base.encode(
        y=alt.Y("hasta:Q", scale=escala, axis=eje), y2="desde:Q", color=color
    )
    y_plegada = alt.Y(
        "altura:Q", stack=None, scale=alt.Scale(domain=[0, ANCHO_12M]), axis=None
    )
    plegada = base.encode(y=y_plegada, color=color).properties(height=ALTO_FILA * 2)
    plegada = plegada.transform_filter("datum.banda == 1") + plegada.transform_filter(
        "datum.banda == 2"
    )

    return alt.hconcat(
        area.properties(title=alt.Title("1. Área respecto a 0", **titulo)),
        cortada.properties(
            title=alt.Title("2. Cortada en bandas de 0,75 °C", **titulo)
        ),
        plegada.properties(title=alt.Title("3. Plegada y superpuesta", **titulo)),
        spacing=24,
    ).resolve_scale(
        color="independent"
    )  # el paso 1 colorea por signo; los otros, por banda


if __name__ == "__main__":
    temperatura = cargar_temperatura()
    paises = list(temperatura["pais"].unique())
    insight = calcular_insight(temperatura)
    media = calcular_media_movil(temperatura)
    bandas_mes = bandas_horizonte(temperatura, "anomalia", ANCHO_MENSUAL)
    bandas_12m = bandas_horizonte(media, "media_12m", ANCHO_12M)
    guardar_bandas(bandas_mes, ARCHIVO_MENSUAL)
    guardar_bandas(bandas_12m, ARCHIVO_12M)

    calidos, por_pais = insight["calidos"], insight["por_pais"]
    metadata = json.loads(
        (comun.RAW / "temperatura_metadata.json").read_text(encoding="utf-8")
    )
    cita = metadata["chart"]["citation"]
    primer_mes, ultimo_mes = temperatura["fecha"].min(), temperatura["fecha"].max()

    comun.guardar_pagina(
        "horizon.html",
        scripts=comun.SCRIPTS_VEGA,
        tecnica="Horizon graph",
        titulo="Europa ya vive más meses de calor que de frío",
        subtitulo=(
            f"En los años {calidos.index[0] % 100}, solo el {comun.numero(calidos.iloc[0], 0)} % de los "
            f"meses fueron más cálidos que la media de 1991-2020 en estos 16 países. Desde "
            f"{calidos.index[-1]}, lo son el {comun.numero(calidos.iloc[-1], 0)} %, y en "
            f"{por_pais.index[-1]}, el {comun.numero(por_pais.iloc[-1], 0)} %."
        ),
        descripcion=(
            f"Dos horizon graphs con una fila por país europeo, de norte a sur, y la anomalía de "
            f"temperatura de {primer_mes:%m/%Y} a {ultimo_mes:%m/%Y}: uno con cada mes y otro con "
            "la media de los últimos 12 meses. El azul domina al principio y el rojo, en los "
            "últimos años."
        ),
        grafico=(
            "<details>\n<summary>Cómo se construye un horizon graph (España, desde 2015)</summary>\n"
            + comun.html_altair(crear_didactico(bandas_12m), "didactico")
            + "\n</details>\n"
            + "<h2>Mes a mes</h2>\n"
            + comun.html_altair(
                crear_horizon(ARCHIVO_MENSUAL, ANCHO_MENSUAL, TOOLTIP_MES, paises),
                "mensual",
            )
            + "\n<h2>Media de los últimos 12 meses</h2>\n"
            + comun.html_altair(
                crear_horizon(ARCHIVO_12M, ANCHO_12M, TOOLTIP_12M, paises), "media-12m"
            )
        ),
        como_se_lee=(
            "<p>Cada fila es un país, ordenados de norte a sur. El color indica si hizo más calor "
            "(rojo) o más frío (azul) de lo normal, y la altura, cuánto. «Lo normal» es la media "
            "de 1991-2020 para cada mes del año.</p>"
            "<p><strong>Mes a mes</strong> muestra la anomalía de cada mes: se ven los meses "
            "extremos, pero cambia tanto de un mes a otro que la tendencia cuesta de ver. "
            "<strong>Media de los últimos 12 meses</strong> suaviza ese vaivén: cada punto resume "
            "el año anterior y la tendencia se lee de un vistazo. Como la media varía menos, sus "
            "bandas son la mitad de anchas (0,75 °C en vez de 1,5 °C), así que los tonos de los "
            "dos gráficos no son comparables entre sí.</p>"
            "<p>Para que quepan 16 países en poco espacio, el gráfico se <strong>pliega</strong>: "
            "el frío se dibuja hacia arriba, igual que el calor, y lo que pasa del ancho de la "
            "primera banda se pinta encima con un tono más oscuro. El desplegable de arriba "
            "muestra estos pasos con los datos de España.</p>"
            "<p>Pasa el ratón (o el dedo) por encima de un mes para ver su valor exacto. Con la "
            "rueda del ratón (o pellizcando) puedes acercarte a un periodo y arrastrar para moverte; "
            "las 16 filas se mueven a la vez. Doble clic para volver a la vista completa.</p>"
        ),
        fuente=(
            f"Fuente: {cita}, a partir del reanálisis ERA5 "
            '(<a href="https://ourworldindata.org/grapher/country-level-monthly-temperature-anomalies">'
            "Our World in Data</a>). Anomalía respecto a la media del mismo mes en 1991-2020, en °C; "
            f"datos hasta {ultimo_mes:%m/%Y}. Licencia "
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.'
        ),
        datos=ARCHIVO_DATOS,
        codigo="horizon_temperatura.py",
    )
    logger.success("Guardado docs/horizon.html")
