from datetime import date
from pathlib import Path
from string import Template

import altair as alt

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
DOCS = RAIZ / "docs"
PLANTILLA = RAIZ / "src" / "plantilla.html"

REPOSITORIO = "https://github.com/pablodieaco/uoc-viz-pec2"

FUENTE = "Lato, system-ui, sans-serif"
COLOR_TEXTO = "#222222"
COLOR_SECUNDARIO = "#595959"
COLOR_EJES = "#bdbdbd"

# versiones fijadas: las que usa Altair 5.5
SCRIPTS_VEGA = """
<script src="https://cdn.jsdelivr.net/npm/vega@5.30.0"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5.20.1"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6.26.0"></script>
"""


@alt.theme.register("pec2", enable=True)
def tema_pec2() -> alt.theme.ThemeConfig:
    """Tema común de Altair: misma tipografía y grises que el CSS."""
    return {
        "config": {
            "font": FUENTE,
            "background": "white",
            "view": {"stroke": None},
            "axis": {
                "labelColor": COLOR_SECUNDARIO,
                "titleColor": COLOR_SECUNDARIO,
                "domainColor": COLOR_EJES,
                "tickColor": COLOR_EJES,
                "grid": False,
                "labelFontSize": 11,
                "titleFontWeight": "normal",
            },
            "legend": {
                "labelColor": COLOR_SECUNDARIO,
                "titleColor": COLOR_SECUNDARIO,
                "titleFontWeight": "normal",
            },
        }
    }


def numero(valor: float, decimales: int = 1) -> str:
    """Formato español: coma decimal y punto de miles (1.234,5)."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def fecha_descarga() -> str:
    descarga = date.fromisoformat((RAW / "fecha_descarga.txt").read_text().strip())
    return f"{descarga:%d/%m/%Y}"


def html_altair(grafico: alt.TopLevelMixin, id_div: str = "grafico") -> str:
    # formatLocale: coma decimal y punto de miles también en tooltips y ejes;
    # timeFormatLocale: meses en español en los ejes de fecha sin formato fijo
    opciones = (
        '{actions: false, formatLocale: {decimal: ",", thousands: ".", '
        'grouping: [3], currency: ["", " €"]}, timeFormatLocale: {dateTime: "%A, %e de %B de %Y, %X", '
        'date: "%d/%m/%Y", time: "%H:%M:%S", periods: ["AM", "PM"], '
        'days: ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"], '
        'shortDays: ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"], '
        'months: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", '
        '"septiembre", "octubre", "noviembre", "diciembre"], '
        'shortMonths: ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]}}'
    )
    # cada vista se guarda en window.vistas para poder cambiar sus parámetros desde la página
    return (
        f'<div id="{id_div}"></div>\n'
        f'<script>vegaEmbed("#{id_div}", {grafico.to_json()}, {opciones})'
        ".then((r) => (window.vistas = window.vistas || []).push(r.view));</script>"
    )


def guardar_pagina(archivo: str, scripts: str = "", **huecos: str) -> None:
    """Rellena la plantilla común y la guarda en docs/."""
    plantilla = Template(PLANTILLA.read_text(encoding="utf-8"))
    html = plantilla.substitute(
        scripts=scripts,
        fecha_descarga=fecha_descarga(),
        repositorio=REPOSITORIO,
        **huecos,
    )
    (DOCS / archivo).write_text(html, encoding="utf-8")
