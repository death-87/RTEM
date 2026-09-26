"""Consulta RTEM. Ejecutar con: streamlit run app.py."""
from datetime import datetime
from hashlib import sha256
from html import escape
from io import StringIO
from pathlib import Path
import logging
import os
import re
import unicodedata
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

BASE = Path(__file__).resolve().parent
VACIO = "Sin información"
SHEET_ID = os.getenv("RTEM_SHEET_ID", "1PjTQCns0CYSzo2l1U9GXnSPS7qBAcVts-G0BwRxjSlQ")
HOJA = os.getenv("RTEM_HOJA", "Reparaciones activas")
DRIVE = os.getenv("RTEM_DRIVE_URL", "https://drive.google.com/drive/folders/1zGSlDQu5o9waFqm211P344MAqxCC8AAK")
COLORES = {"RTEM DEFINITIVA": "#28a745", "RTEM NO EJECUTADA": "#dc3545",
           "RTEM EJECUTADA PARCIAL": "#d35400", "RTEM EJECUTADA": "#ff8c00",
           "RTEM PENDIENTE REVISION": "#f1c40f"}
LOG = logging.getLogger(__name__)


def normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).lower().split())


def columna(df, *nombres):
    """Prioriza coincidencias exactas; nunca confunde LAT con otra palabra."""
    for nombre in nombres:
        for c in df.columns:
            if normalizar(c) == normalizar(nombre):
                return c
    return None


def coordenadas(valor):
    """Acepta grados decimales: lat, lon; lat; lon; o dos números con espacios."""
    texto = str(valor).strip().strip("()[]").strip()
    decimal = r"[+-]?\d+(?:\.\d+)?"
    coma_decimal = r"[+-]?\d+(?:[.,]\d+)?"
    patron = (rf"({coma_decimal})\s*;\s*({coma_decimal})" if ";" in texto
              else rf"({decimal})(?:\s*,\s*|\s+)({decimal})")
    match = re.fullmatch(patron, texto)
    if not match:
        return None
    lat, lon = (float(n.replace(",", ".")) for n in match.groups())
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def preparar_csv(texto):
    if texto.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise ValueError("Google devolvió una página HTML en lugar de un CSV.")
    df = pd.read_csv(StringIO(texto), dtype=str, keep_default_na=False)
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    if df.columns.duplicated().any():
        raise ValueError("Hay encabezados duplicados después de normalizar espacios.")
    df = df.loc[:, [c for c in df.columns if not normalizar(c).startswith("unnamed")]]
    for c in df.columns:
        df[c] = df[c].str.strip().replace("", VACIO)
        if normalizar(c) in {"orden", "aviso", "numero de orden", "numero de aviso"}:
            df[c] = df[c].str.replace(r"^(\d+)\.0$", r"\1", regex=True)
    if not any(columna(df, n) for n in ("orden", "aviso", "estatus", "status", "área")):
        raise ValueError("El CSV no contiene columnas RTEM reconocibles. Revisa los encabezados.")
    return df


@st.cache_data(ttl=300, max_entries=4, show_spinner=False)
def cargar(sheet_id, hoja):
    url = f"https://docs.google.com/spreadsheets/d/{quote(sheet_id, safe='')}/gviz/tq?" + urlencode({"tqx": "out:csv", "sheet": hoja})
    with urlopen(Request(url, headers={"User-Agent": "RTEM/2.0"}), timeout=25) as respuesta:
        texto = respuesta.read().decode("utf-8-sig")
    return preparar_csv(texto), datetime.now().astimezone().isoformat(timespec="seconds")


def recurso(*nombres):
    return next((BASE / n for n in nombres if (BASE / n).is_file()), None)


def texto_pdf(valor):
    # Helvetica admite español en Latin-1. Otros caracteres se sustituyen.
    return str(valor).encode("latin-1", "replace").decode("latin-1")


class FichaPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, f"RTEM | Página {self.page_no()}", align="C")
        logo = recurso("logojn.png", "logo.png", "logojn.npg")
        if logo:
            try:
                self.image(str(logo), x=175, y=self.h - 18, w=20, h=12, keep_aspect_ratio=True)
            except (OSError, ValueError):
                LOG.warning("No se pudo incorporar el logo al PDF", exc_info=True)


def generar_pdf(registro, claves, actualizado):
    pdf = FichaPDF()
    pdf.set_auto_page_break(True, margin=23)
    pdf.add_page()
    estado = registro.get(claves["estado"], VACIO)
    color = COLORES.get(normalizar(estado).upper(), "#005ce6")
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))

    def escribir(texto, tam=10, negrita=False):
        pdf.set_font("Helvetica", "B" if negrita else "", tam)
        pdf.multi_cell(0, 6, texto_pdf(texto), new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(*rgb)
    escribir(f"RTEM · {registro.get(claves['area'], VACIO)}", 16, True)
    escribir(f"Estatus: {estado}", 11, True)
    pdf.set_text_color(0, 0, 0)
    escribir(f"Orden: {registro.get(claves['orden'], VACIO)} | Aviso: {registro.get(claves['aviso'], VACIO)}", 11, True)
    escribir(f"Datos consultados: {actualizado}", 8)
    pdf.ln(4)
    # Una columna permite que valores extensos continúen en páginas siguientes.
    for campo, valor in registro.items():
        if campo == claves["estado"]:
            continue
        if pdf.get_y() + 18 > pdf.h - pdf.b_margin:
            pdf.add_page()
        escribir(campo, 9, True)
        escribir(valor)
        pdf.ln(2)
    return bytes(pdf.output())


def main():
    st.set_page_config(page_title="Control y Consulta RTEM", page_icon="🔎", layout="wide")
    franja = recurso("franja.jpg")
    if franja:
        st.image(str(franja), use_container_width=True)
    st.title("🔎 Consulta e inspecciones RTEM")
    st.caption("Consulta reparaciones, revisa evidencias y descarga fichas para terreno.")
    if st.sidebar.button("Actualizar datos", use_container_width=True):
        cargar.clear()
    try:
        with st.spinner("Cargando reparaciones…"):
            df, actualizado = cargar(SHEET_ID, HOJA)
    except Exception:
        LOG.exception("Error al cargar Google Sheets")
        st.error("No se pudieron cargar los datos. Revisa la conexión, el nombre de la hoja y sus permisos de acceso CSV.")
        st.stop()
    claves = {"estado": columna(df, "estatus", "status", "estado"),
              "area": columna(df, "área", "area responsable"),
              "orden": columna(df, "orden", "numero de orden", "n° orden"),
              "aviso": columna(df, "aviso", "numero de aviso"),
              "emplazamiento": columna(df, "emplazamiento"),
              "geo": columna(df, "georreferencia", "georreferenciación", "coordenadas"),
              "lat": columna(df, "lat", "latitud"), "lon": columna(df, "lon", "lng", "longitud")}
    faltantes = [k for k in ("estado", "orden", "aviso", "area") if claves[k] is None]
    if faltantes:
        st.warning("Columnas no reconocidas: " + ", ".join(faltantes) + ". Algunas funciones no estarán disponibles.")
    if claves["estado"]:
        c = claves["estado"]
        df[c] = df[c].map(lambda v: normalizar(v).upper() if v != VACIO else v)
    st.sidebar.header("Filtros")
    if st.sidebar.button("Limpiar filtros"):
        for key in list(st.session_state):
            if key.startswith("filtro_"):
                del st.session_state[key]
        st.rerun()
    consulta = st.sidebar.text_input("Buscar en todos los campos", key="filtro_busqueda")
    vista = df.copy()
    if consulta.strip():
        termino = normalizar(consulta)
        mascara = df.apply(lambda s: s.map(normalizar).str.contains(termino, regex=False)).any(axis=1)
        vista = vista[mascara]
    for nombre, etiqueta in (("estado", "Estatus"), ("area", "Área"), ("emplazamiento", "Emplazamiento"), ("orden", "Orden"), ("aviso", "Aviso")):
        c = claves[nombre]
        if c:
            opciones = sorted(df[c].unique(), key=normalizar)
            key = f"filtro_{nombre}"
            if key in st.session_state:
                st.session_state[key] = [v for v in st.session_state[key] if v in opciones]
            seleccion = st.sidebar.multiselect(etiqueta, opciones, key=key)
            if seleccion:
                vista = vista[vista[c].isin(seleccion)]
    st.sidebar.caption(f"Consulta: {actualizado}. Caché de hasta 5 minutos.")
    logo = recurso("logojn.png", "logo.png")
    if logo:
        st.sidebar.image(str(logo), use_container_width=True)
    a, b, c = st.columns(3)
    a.metric("Registros encontrados", len(vista))
    b.metric("Total de registros", len(df))
    c.metric("Áreas en resultados", vista[claves["area"]].replace(VACIO, pd.NA).nunique() if claves["area"] else "—")
    if vista.empty:
        st.info("No hay resultados. Modifica o limpia los filtros.")
        return
    tabla, estadisticas = st.tabs(["📋 Reparaciones", "📊 Estadísticas"])
    registro = None
    with tabla:
        st.caption("Selecciona una fila para abrir su ficha técnica.")
        # Cambia la identidad del widget cuando cambia el contenido o su orden.
        huella = sha256(vista.to_json(orient="split").encode()).hexdigest()[:16]
        evento = st.dataframe(vista, hide_index=True, use_container_width=True,
                              selection_mode="single-row", on_select="rerun", key=f"tabla_{huella}")
        filas = evento.selection.rows
        if filas and 0 <= filas[0] < len(vista):
            registro = vista.iloc[filas[0]]
        elif len(vista) == 1:
            registro = vista.iloc[0]
    with estadisticas:
        st.caption("Los gráficos utilizan los filtros actuales y los datos de la última consulta.")
        for contenedor, nombre, titulo in zip(st.columns(2), ("estado", "area"), ("Reparaciones por estatus", "Distribución por área")):
            with contenedor:
                campo = claves[nombre]
                if campo:
                    resumen = vista[campo].value_counts().rename_axis("Categoría").reset_index(name="Cantidad")
                    fig = px.bar(resumen, x="Cantidad", y="Categoría", orientation="h", color="Categoría", text="Cantidad", title=titulo, color_discrete_map=COLORES)
                    fig.update_layout(showlegend=False, yaxis_title="", height=max(350, len(resumen) * 32))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"Falta la columna: {nombre}.")
    if registro is None:
        return
    st.divider()
    detalles, acciones = st.columns([2, 1])
    orden = registro.get(claves["orden"], VACIO)
    aviso = registro.get(claves["aviso"], VACIO)
    with detalles:
        st.subheader(f"Ficha técnica · Orden {orden}")
        st.table(pd.DataFrame({"Campo": registro.index, "Valor": registro.values}))
    with acciones:
        estado = registro.get(claves["estado"], VACIO)
        color = COLORES.get(normalizar(estado).upper(), "#005ce6")
        st.markdown(f'<div style="border:2px solid {color};padding:16px;border-radius:10px"><b>Estatus</b><br>{escape(estado)}</div>', unsafe_allow_html=True)
        st.write("")
        st.link_button("Abrir carpeta de evidencias", DRIVE, use_container_width=True)
        termino = orden if orden != VACIO else aviso
        if termino != VACIO:
            st.link_button(f"Buscar {termino} en Drive", "https://drive.google.com/drive/u/0/search?" + urlencode({"q": termino}), use_container_width=True)
            st.caption("La búsqueda abarca todo tu Drive; el botón anterior abre la carpeta configurada.")
        try:
            contenido = generar_pdf(registro, claves, actualizado)
        except Exception:
            LOG.exception("Error al generar PDF")
            st.error("No se pudo generar el PDF. El resto de la ficha sigue disponible.")
        else:
            nombre = re.sub(r"[^\w-]+", "_", str(orden))[:80]
            st.download_button("📄 Descargar ficha PDF", contenido, file_name=f"Ficha_OT_{nombre}.pdf", mime="application/pdf", use_container_width=True)
        identidad = sha256((str(registro.name) + registro.to_json()).encode()).hexdigest()[:16]
        foto = st.file_uploader("Vista previa de evidencia", type=["png", "jpg", "jpeg"], key=f"foto_{identidad}")
        st.caption("La imagen es temporal: no se guarda en Drive ni se incluye en el PDF.")
        if foto:
            st.image(foto, caption=f"Evidencia · {termino}", use_container_width=True)
        ubicacion = None
        if claves["lat"] and claves["lon"]:
            ubicacion = coordenadas(f"{registro[claves['lat']]};{registro[claves['lon']]}")
        if ubicacion is None and claves["geo"]:
            ubicacion = coordenadas(registro[claves["geo"]])
        if ubicacion is not None:
            lat, lon = ubicacion
            st.link_button("🗺️ Abrir en Google Maps", "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{lat},{lon}"}), use_container_width=True)
            st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=15)
        elif claves["geo"] or (claves["lat"] and claves["lon"]):
            st.caption("Este registro no tiene coordenadas decimales válidas.")


if __name__ == "__main__":
    main()
