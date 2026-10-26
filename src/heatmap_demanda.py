import json

import altair as alt
import pandas as pd
from loguru import logger

import comun

ARCHIVO_DATOS = "demanda_diaria_2025.csv"
DIAS = ["L", "M", "X", "J", "V", "S", "D"]
NOMBRES_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# fiestas nacionales comunes a todas las CC. AA. en 2025 (BOE-A-2024-21316);
# el 12 de octubre cae en domingo y no aparece en la lista
FESTIVOS = pd.to_datetime(
    [
        "2025-01-01", "2025-01-06", "2025-04-18", "2025-05-01", "2025-08-15",
        "2025-11-01", "2025-12-06", "2025-12-08", "2025-12-25",
    ]
)
LADO_CELDA = 16
LADO_CELDA_MES = 22
COLOR_FESTIVO = "#222222"
# el apagón peninsular: su demanda es tan baja que acapara el extremo claro de la escala
FECHA_APAGON = pd.Timestamp("2025-04-28")
COLOR_EXCLUIDO = "#d9d9d9"
# un solo botón que cambia el parámetro sin_apagon en todas las vistas de la página
BOTON_APAGON = """
<p><button type="button" class="boton" id="boton-apagon" aria-pressed="false">Quitar efecto apagón (28/04)</button></p>
<script>
document.getElementById("boton-apagon").addEventListener("click", (evento) => {
  const activo = evento.target.getAttribute("aria-pressed") !== "true";
  evento.target.setAttribute("aria-pressed", activo);
  evento.target.textContent = activo ? "Mostrar efecto apagón (28/04)" : "Quitar efecto apagón (28/04)";
  window.vistas.forEach((vista) => vista.signal("sin_apagon", activo).run());
});
</script>
"""


def calcular_semana(fechas: pd.Series) -> pd.Series:
    # semana propia y no ISO: la ISO manda el 29-31/12 a la semana 1
    desfase = fechas.iloc[0].weekday()
    return (fechas.dt.dayofyear - 1 + desfase) // 7


def cargar_demanda() -> pd.DataFrame:
    demanda = pd.read_csv(comun.PROCESSED / ARCHIVO_DATOS, parse_dates=["fecha"])
    demanda["semana"] = calcular_semana(demanda["fecha"])
    demanda["dia_semana"] = demanda["fecha"].dt.weekday.map(dict(enumerate(DIAS)))
    demanda["festivo"] = demanda["fecha"].isin(FESTIVOS)
    demanda["nombre_dia"] = demanda["fecha"].dt.weekday.map(dict(enumerate(NOMBRES_DIAS)))
    demanda.loc[demanda["festivo"], "nombre_dia"] += " (festivo nacional)"
    demanda["apagon"] = demanda["fecha"] == FECHA_APAGON
    demanda.loc[demanda["apagon"], "nombre_dia"] += " (apagón)"
    demanda["dia_mes"] = demanda["fecha"].dt.day
    demanda["mes"] = demanda["fecha"].dt.month.map(dict(enumerate(MESES, start=1)))
    logger.info(f"{len(demanda)} días, semanas de {demanda['semana'].min()} a {demanda['semana'].max()}")
    return demanda


def calcular_insight(demanda: pd.DataFrame) -> dict:
    dia = demanda["fecha"].dt.weekday
    laborable = demanda.loc[(dia < 5) & ~demanda["festivo"], "demanda_gwh"].mean()
    domingo = demanda.loc[dia == 6, "demanda_gwh"].mean()
    caida_domingo = (1 - domingo / laborable) * 100
    logger.info(
        f"Media laborable {laborable:.1f} GWh, domingo {domingo:.1f} GWh: "
        f"un {caida_domingo:.1f} % menos"
    )
    columnas = ["fecha", "nombre_dia", "demanda_gwh"]
    logger.info("3 días de mínima demanda:\n" + demanda.nsmallest(3, "demanda_gwh")[columnas].to_string(index=False))
    logger.info("3 días de máxima demanda:\n" + demanda.nlargest(3, "demanda_gwh")[columnas].to_string(index=False))
    mensual = demanda.groupby(demanda["fecha"].dt.month)["demanda_gwh"].mean().round(1)
    logger.info(f"Media mensual (GWh): {mensual.set_axis(MESES).to_dict()}")
    return {
        "caida_domingo": caida_domingo,
        "minimo": demanda.loc[demanda["demanda_gwh"].idxmin()],
        "maximo": demanda.loc[demanda["demanda_gwh"].idxmax()],
    }


def crear_celdas(demanda: pd.DataFrame, x: alt.X, y: alt.Y) -> alt.LayerChart:
    """Celdas coloreadas por demanda y puntos de festivos; comunes a las dos versiones."""
    # mismo dominio en las dos versiones para que los colores sean comparables;
    # sin el apagón, la escala empieza en el mínimo del resto de días
    minimo = demanda["demanda_gwh"].min()
    minimo_sin_apagon = demanda.loc[~demanda["apagon"], "demanda_gwh"].min()
    sin_apagon = alt.param(name="sin_apagon", value=False)
    color = alt.Color(
        "demanda_gwh:Q",
        scale=alt.Scale(
            scheme="yellowgreenblue",
            domainMin=alt.ExprRef(f"sin_apagon ? {minimo_sin_apagon} : {minimo}"),
            domainMax=demanda["demanda_gwh"].max(),
            clamp=True,
        ),
        legend=alt.Legend(title="Demanda (GWh/día)", orient="bottom", gradientLength=240, format=",.0f"),
    )

    celdas = alt.Chart(demanda).mark_rect(stroke="white", strokeWidth=1.5).add_params(sin_apagon).encode(
        x=x,
        y=y,
        color=alt.condition("sin_apagon && datum.apagon", alt.value(COLOR_EXCLUIDO), color),
        tooltip=[
            alt.Tooltip("fecha:T", title="Fecha", format="%d/%m/%Y"),
            alt.Tooltip("nombre_dia:N", title="Día"),
            alt.Tooltip("demanda_gwh:Q", title="Demanda (GWh)", format=",.1f"),
        ],
    )
    # punto con borde blanco y no contorno: un contorno oscuro no se ve en los días más oscuros
    festivos = (
        alt.Chart(demanda[demanda["festivo"]])
        .mark_circle(size=22, color=COLOR_FESTIVO, opacity=1, stroke="white", strokeWidth=1)
        .encode(x=x, y=y, tooltip=celdas.encoding.tooltip)
    )
    return celdas + festivos


def crear_heatmap_semanas(demanda: pd.DataFrame) -> alt.LayerChart:
    x = alt.X("semana:O", axis=None)
    y = alt.Y("dia_semana:O", sort=DIAS, title=None, axis=alt.Axis(ticks=False, domain=False, labelPadding=6))

    primeros = demanda[demanda["fecha"].dt.day == 1].assign(mes=MESES)
    meses = alt.Chart(primeros).mark_text(
        align="left", baseline="bottom", dx=-LADO_CELDA / 2, dy=-4, fontSize=11, color=comun.COLOR_SECUNDARIO
    ).encode(x=x, y=alt.value(0), text="mes:N")

    return (crear_celdas(demanda, x, y) + meses).properties(
        width=alt.Step(LADO_CELDA), height=alt.Step(LADO_CELDA)
    )


def crear_heatmap_dias_mes(demanda: pd.DataFrame) -> alt.LayerChart:
    eje = alt.Axis(ticks=False, domain=False, labelPadding=6, labelAngle=0)
    x = alt.X("dia_mes:O", title=None, axis=alt.Axis(orient="top", ticks=False, domain=False, labelAngle=0))
    y = alt.Y("mes:O", sort=MESES, title=None, axis=eje)
    return crear_celdas(demanda, x, y).properties(
        width=alt.Step(LADO_CELDA_MES), height=alt.Step(LADO_CELDA_MES)
    )


if __name__ == "__main__":
    demanda = cargar_demanda()
    insight = calcular_insight(demanda)
    minimo, maximo = insight["minimo"], insight["maximo"]

    respuesta_ree = json.loads((comun.RAW / "demanda_ree_2025.json").read_text(encoding="utf-8"))
    actualizacion = pd.to_datetime(respuesta_ree["data"]["attributes"]["last-update"][:10])

    comun.guardar_pagina(
        "heatmap.html",
        scripts=comun.SCRIPTS_VEGA,
        tecnica="Heatmap de calendario",
        titulo="¿Cuándo consume más electricidad España?",
        subtitulo=(
            f"Los domingos se consume de media un {comun.numero(insight['caida_domingo'], 0)} % "
            f"menos que un día laborable. El día de menor demanda de 2025 fue el del apagón, "
            f"el {minimo['fecha']:%d/%m} ({comun.numero(minimo['demanda_gwh'], 0)} GWh), "
            f"y el de mayor, el {maximo['fecha']:%d/%m}, a principios de julio "
            f"({comun.numero(maximo['demanda_gwh'], 0)} GWh)."
        ),
        descripcion=(
            "Dos calendarios de 2025 con un cuadrado por día coloreado según la demanda eléctrica, "
            "uno por semanas y otro por día del mes: los fines de semana, los festivos y la "
            "primavera aparecen más claros."
        ),
        grafico=(
            BOTON_APAGON
            + "<h2>Por semanas</h2>\n"
            + comun.html_altair(crear_heatmap_semanas(demanda), "semanas")
            + "\n<h2>Por día del mes</h2>\n"
            + comun.html_altair(crear_heatmap_dias_mes(demanda), "dias-mes")
        ),
        como_se_lee=(
            "<p>Cada cuadrado es un día de 2025 y cuanto más oscuro es su color, más electricidad "
            "se consumió ese día en España. Los dos calendarios usan la misma escala de color.</p>"
            "<p><strong>Por semanas</strong>: cada columna es una semana, de enero a diciembre, "
            "y cada fila un día de la semana, de lunes a domingo. Así, los fines de semana forman "
            "dos franjas claras abajo. <strong>Por día del mes</strong>: cada fila es un mes y cada "
            "columna un día del 1 al 31; como cada mes empieza en un día de la semana distinto, "
            "los fines de semana aparecen como diagonales.</p>"
            "<p>El 28 de abril, día del apagón, la demanda cayó tanto que ocupa casi todo el "
            "extremo claro de la escala. El botón <em>Quitar efecto apagón</em> lo pinta en gris y "
            "hace que la escala empiece en el siguiente día más bajo, para ver mejor el resto.</p>"
            "<p>Los puntos negros marcan los festivos nacionales. "
            "Pasa el ratón (o el dedo) por encima de un día para ver su demanda exacta.</p>"
        ),
        fuente=(
            'Fuente: Red Eléctrica, <a href="https://www.ree.es/es/datos/apidatos">REData</a> '
            f"(apidatos.ree.es), demanda nacional diaria; datos actualizados el {actualizacion:%d/%m/%Y}. "
            'Uso según el <a href="https://www.ree.es/es/aviso-legal">aviso legal de REE</a>. '
            'Festivos: <a href="https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-21316">BOE-A-2024-21316</a>.'
        ),
        datos=ARCHIVO_DATOS,
        codigo="heatmap_demanda.py",
    )
    logger.success("Guardado docs/heatmap.html")
