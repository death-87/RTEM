import os
import re
import unicodedata
import urllib.parse
import pandas as pd
import streamlit as st
import plotly.express as px
from fpdf import FPDF

st.set_page_config(page_title="Control y Consulta RTEM", layout="wide")

# -----------------------------------------------------------------------------
# CABECERA VISUAL: FRANJA Y TÍTULO
# -----------------------------------------------------------------------------
if os.path.exists("franja.jpg"):
    st.image("franja.jpg", use_container_width=True)

st.title("🔎 Sistema de Consulta e Inspecciones RTEM")
st.markdown("---")

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE GOOGLE SHEETS Y GOOGLE DRIVE
# -----------------------------------------------------------------------------
SHEET_ID = "1PjTQCns0CYSzo2l1U9GXnSPS7qBAcVts-G0BwRxjSlQ"
NOMBRE_HOJA = "Reparaciones activas"

GDRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1zGSlDQu5o9waFqm211P344MAqxCC8AAK"

# Paleta de colores oficial para los estatus
MAPA_COLORES_ESTATUS = {
    "RTEM DEFINITIVA": "#28a745",          # Verde
    "RTEM NO EJECUTADA": "#dc3545",        # Rojo
    "RTEM EJECUTADA PARCIAL": "#d35400",   # Naranjo oscuro
    "RTEM EJECUTADA": "#ff8c00",           # Naranjo
    "RTEM PENDIENTE REVISION": "#f1c40f"   # Amarillo
}

def normalizar_texto(texto):
    """Elimina tildes y pasa a minúsculas para comparaciones exactas"""
    if not isinstance(texto, str):
        texto = str(texto)
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().strip()

def hex_to_rgb(hex_code):
    """Convierte un color HEX a una tupla RGB para FPDF"""
    hex_code = hex_code.lstrip('#')
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def generar_link_gdrive(termino_busqueda):
    """Genera un enlace de búsqueda directa dentro de la carpeta de Google Drive"""
    busqueda_encoded = urllib.parse.quote(str(termino_busqueda))
    return f"https://drive.google.com/drive/u/0/search?q={busqueda_encoded}"

def extraer_coordenadas(coordenadas):
    if pd.isna(coordenadas) or str(coordenadas).strip() in ['Sin información', 'nan']:
        return None, None
    numeros = re.findall(r'-?\d+[\.,]\d+', str(coordenadas))
    if len(numeros) >= 2:
        lat = numeros[0].replace(',', '.')
        lon = numeros[1].replace(',', '.')
        return lat, lon
    return None, None

def generar_pdf_orden(val_orden, val_aviso, valor_status, datos_mostrar, color_hex, titulo_rtem):
    """Genera el PDF con celdas de altura dinámica en 2 columnas para que el texto baje correctamente"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    rgb = hex_to_rgb(color_hex)
    
    # 1. Título Principal con el área
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(*rgb)
    pdf.cell(0, 7, titulo_rtem, ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)
    
    # 2. Orden y Aviso destacados
    pdf.set_font("Arial", "B", 10)
    txt_orden_aviso = f"ORDEN: {val_orden}   |   AVISO: {val_aviso}"
    pdf.cell(0, 5, txt_orden_aviso, ln=True, align="C")
    pdf.ln(1)
    
    # Estatus Actual
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(*rgb)
    pdf.cell(0, 5, f"Estatus Actual: {valor_status}", ln=True)
    pdf.set_text_color(0, 0, 0)
    
    pdf.ln(2)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "Detalle Tecnico de la Reparacion", ln=True)
    pdf.ln(1)
    
    # Filtrar datos excluidos
    items_filtrados = []
    for k, v in datos_mostrar.items():
        k_str = str(k)
        k_norm = normalizar_texto(k_str)
        palabras_excluidas = ["unnamed", "indicador abc", "estatus", "status", "cantidad", "perfil catalogo", "perfil"]
        if any(p in k_norm for p in palabras_excluidas):
            continue
        items_filtrados.append((k_str, str(v)))
    
    ancho_columna = 93  # Ancho de cada columna
    pdf.set_draw_color(*rgb)
    
    for i in range(0, len(items_filtrados), 2):
        # Par de elementos (Izquierda y Derecha)
        k1, v1 = items_filtrados[i]
        k1_c = k1.encode('latin-1', 'replace').decode('latin-1')
        v1_c = v1.encode('latin-1', 'replace').decode('latin-1')
        
        if i + 1 < len(items_filtrados):
            k2, v2 = items_filtrados[i+1]
            k2_c = k2.encode('latin-1', 'replace').decode('latin-1')
            v2_c = v2.encode('latin-1', 'replace').decode('latin-1')
        else:
            k2_c, v2_c = "", ""
            
        # Calcular dinámicamente cuántas líneas ocupa cada bloque de texto usando string length aproximado
        # Cada 55 caracteres aprox equivale a una línea con fuente tamaño 8 en 93mm de ancho
        lineas_v1 = max(1, int(len(v1_c) / 52) + 1)
        lineas_v2 = max(1, int(len(v2_c) / 52) + 1) if k2_c else 1
        max_lineas = max(lineas_v1, lineas_v2)
        
        # Altura total de la caja de valor para esta fila
        altura_valor = max_lineas * 4.5 + 2
        
        # Verificar si hay espacio suficiente en la página actual antes de imprimir la fila
        if pdf.get_y() + altura_valor + 10 > 280:
            pdf.add_page()
            
        x_inicio = pdf.get_x()
        y_inicio = pdf.get_y()
        
        # --- COLUMNA IZQUIERDA ---
        # Título de Columna 1
        pdf.set_font("Arial", "B", 7.5)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(ancho_columna, 4.5, f"  {k1_c}", border="TRL", fill=True)
        
        # Espacio entre columnas
        pdf.cell(4, altura_valor + 4.5, "", border=0)
        
        # --- COLUMNA DERECHA ---
        if k2_c:
            pdf.set_font("Arial", "B", 7.5)
            pdf.set_fill_color(245, 245, 245)
            pdf.cell(ancho_columna, 4.5, f"  {k2_c}", border="TRL", fill=True, ln=True)
        else:
            pdf.cell(ancho_columna, 4.5, "", border=0, ln=True)
            
        # Posicionar el cursor para imprimir los valores debajo de los títulos
        y_despues_titulos = pdf.get_y()
        
        # Imprimir Valor Izquierdo con salto automático (multi_cell)
        pdf.set_xy(x_inicio, y_despues_titulos)
        pdf.set_font("Arial", "", 8)
        pdf.multi_cell(ancho_columna, 4.5, f"  {v1_c}", border="BRL")
        
        y_fin_izq = pdf.get_y()
        
        # Imprimir Valor Derecho si existe
        if k2_c:
            pdf.set_xy(x_inicio + ancho_columna + 4, y_despues_titulos)
            pdf.set_font("Arial", "", 8)
            pdf.multi_cell(ancho_columna, 4.5, f"  {v2_c}", border="BRL")
            y_fin_der = pdf.get_y()
            max_y = max(y_fin_izq, y_fin_der)
        else:
            max_y = y_fin_izq
            
        # Mover el cursor a la siguiente posición unificada abajo de la fila más alta
        pdf.set_xy(x_inicio, max_y + 1)
        
    pdf.set_draw_color(0, 0, 0)
    return bytes(pdf.output())

# --- CARGA AUTOMÁTICA DESDE GOOGLE SHEETS (VÍA CSV SEGURO) ---
nombre_hoja_encoded = urllib.parse.quote(NOMBRE_HOJA)
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={nombre_hoja_encoded}"

try:
    df = pd.read_csv(SHEET_URL)
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    df = df.fillna("Sin información")
    df = df.astype(str)
    
    for col in df.columns:
        if 'ORDEN' in col.upper() or 'AVISO' in col.upper():
            df[col] = df[col].str.replace(r'\.0$', '', regex=True).str.strip()
            df[col] = df[col].replace('nan', 'Sin información')
            
except Exception as e:
    st.error(f"❌ Error al conectar con Google Sheets: {e}")
    st.stop()

# --- RECONOCIMIENTO DE COLUMNAS CLAVE ---
col_area = next((c for c in df.columns if 'ÁREA' in c.upper() or 'AREA' in c.upper()), None)
col_emplazamiento = next((c for c in df.columns if 'EMPLAZAMIENTO' in c.upper()), None)
col_orden = next((c for c in df.columns if 'ORDEN' in c.upper()), None)
col_aviso = next((c for c in df.columns if 'AVISO' in c.upper()), None)
col_geo = next((c for c in df.columns if 'GEORREFERENCIA' in c.upper() or 'LAT' in c.upper()), None)

if "ESTATUS" in df.columns:
    col_status = "ESTATUS"
elif "STATUS" in df.columns:
    col_status = "STATUS"
else:
    col_status = None

# --- BARRA LATERAL: FILTROS ---
st.sidebar.header("🎯 Búsqueda Rápida")
df_filtrado = df.copy()

if col_status:
    estados = ["Todos"] + sorted([x for x in df[col_status].unique() if x != "Sin información"])
    status_sel = st.sidebar.selectbox("⚡ Filtrar por Estatus:", estados)
    if status_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado[col_status] == status_sel]

if col_orden:
    ordenes = ["Todas"] + sorted([x for x in df_filtrado[col_orden].unique() if x != "Sin información"])
    orden_sel = st.sidebar.selectbox("1️⃣ Buscar por Orden:", ordenes)
    if orden_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado[col_orden] == orden_sel]

if col_aviso:
    avisos = ["Todos"] + sorted([x for x in df_filtrado[col_aviso].unique() if x != "Sin información"])
    aviso_sel = st.sidebar.selectbox("2️⃣ Buscar por Aviso:", avisos)
    if aviso_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado[col_aviso] == aviso_sel]

st.sidebar.markdown("---")
st.sidebar.markdown("**Filtros Generales**")

if col_area:
    areas = ["Todas"] + sorted([x for x in df[col_area].unique() if x != "Sin información"])
    area_sel = st.sidebar.selectbox("Filtrar por Área:", areas)
    if area_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado[col_area] == area_sel]

if col_emplazamiento:
    emplazamientos = ["Todos"] + sorted([x for x in df[col_emplazamiento].unique() if x != "Sin información"])
    emp_sel = st.sidebar.selectbox("Filtrar por Emplazamiento:", emplazamientos)
    if emp_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado[col_emplazamiento] == emp_sel]

# --- LOGO INSTITUCIONAL AL PIE DE LA BARRA LATERAL ---
st.sidebar.markdown("---")
if os.path.exists("logojn.png"):
    st.sidebar.image("logojn.png", use_container_width=True)
elif os.path.exists("logojn.npg"):
    st.sidebar.image("logojn.npg", use_container_width=True)
elif os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)


# --- VISTA PRINCIPAL ---
st.markdown(f"**Registros encontrados:** `{len(df_filtrado)}` de `{len(df)}` totales.")

pestana_tabla, pestana_stats = st.tabs(["📊 Vista General de Datos", "📈 Panel de Estadísticas y Gráficos"])

with pestana_tabla:
    st.caption("💡 Haz clic en cualquier fila de la tabla para abrir inmediatamente su Ficha Técnica detallada.")
    palabras_a_ocultar = ['emplazamiento', 'equipo', 'indicador abc', 'prioridad', 'fecha de entrada', 'ubicac.tecnica', 'ubicac tecnica', 'fe.fin extrema']
    
    columnas_visibles = []
    for c in df_filtrado.columns:
        c_norm = normalizar_texto(c)
        if not any(oculta in c_norm for oculta in palabras_a_ocultar):
            columnas_visibles.append(c)
            
    df_vista_tabla = df_filtrado[columnas_visibles]

    evento_tabla = st.dataframe(
        df_vista_tabla, 
        use_container_width=True, 
        selection_mode="single-row", 
        on_select="rerun"
    )

    registro_seleccionado = None
    if evento_tabla and "selection" in evento_tabla and "rows" in evento_tabla["selection"]:
        filas_seleccionadas = evento_tabla["selection"]["rows"]
        if len(filas_seleccionadas) > 0:
            indice_fila = filas_seleccionadas[0]
            registro_seleccionado = df_filtrado.iloc[indice_fila]

with pestana_stats:
    st.subheader("📊 Análisis Gráfico Dinámico")
    st.markdown("Estos gráficos reflejan la información en tiempo real según los filtros aplicados en el panel izquierdo.")
    
    if len(df_filtrado) == 0:
        st.warning("No hay datos para mostrar en las estadísticas con los filtros actuales.")
    else:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("##### 📉 Reparaciones por Estatus")
            if col_status:
                df_status_counts = df_filtrado[col_status].value_counts().reset_index()
                df_status_counts.columns = ['Estatus', 'Cantidad']
                fig_status = px.bar(df_status_counts, x='Estatus', y='Cantidad', color='Estatus', color_discrete_map=MAPA_COLORES_ESTATUS, text='Cantidad')
                fig_status.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total")
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("No se encontró la columna de Estatus para graficar.")
                
        with col_g2:
            st.markdown("##### 📊 Distribución por Área")
            if col_area:
                df_area_counts = df_filtrado[col_area].value_counts().reset_index()
                df_area_counts.columns = ['Área', 'Cantidad']
                fig_area = px.bar(df_area_counts, x='Área', y='Cantidad', text='Cantidad')
                fig_area.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total")
                st.plotly_chart(fig_area, use_container_width=True)
            else:
                st.info("No se encontró la columna de Área para graficar.")

if (registro_seleccionado is not None) or (len(df_filtrado) == 1):
    registro = registro_seleccionado if registro_seleccionado is not None else df_filtrado.iloc[0]
    
    st.markdown("---")
    st.markdown("---")
    
    col_detalles, col_enlaces = st.columns([2, 1])

    with col_detalles:
        titulo_ficha = f"Orden: {registro[col_orden]}" if col_orden and registro[col_orden] != 'Sin información' else "Detalle del Registro"
        st.subheader(f"📋 Ficha Técnica - {titulo_ficha}")
        datos_mostrar = {k: v for k, v in registro.items() if "Unnamed" not in str(k) and k != col_status}
        df_ficha = pd.DataFrame(list(datos_mostrar.items()), columns=['Campo', 'Valor'])
        st.table(df_ficha)

    with col_enlaces:
        color_principal = "#005ce6"
        valor_status = "SIN INFORMACIÓN"
        if col_status and registro[col_status] != 'Sin información':
            valor_status = registro[col_status].strip().upper()
            color_principal = MAPA_COLORES_ESTATUS.get(valor_status, "#005ce6")
            
        st.markdown(f"""
        <div style="background: transparent; padding: 12px; border-radius: 8px; text-align: center; border: 2px solid {color_principal}; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 12px; color: #666; font-weight: bold; text-transform: uppercase;">Estatus de la Reparación</p>
            <h3 style="margin: 4px 0 0 0; font-size: 22px; color: {color_principal}; line-height: 1.1;">{valor_status}</h3>
        </div>
        """, unsafe_allow_html=True)
            
        st.subheader("📁 Accesos Rápidos y Evidencia")
        
        termino_busqueda = ""
        val_orden = registro[col_orden] if col_orden else "Sin información"
        val_aviso = registro[col_aviso] if col_aviso else "Sin información"
        
        if col_orden and registro[col_orden] != 'Sin información':
            termino_busqueda = registro[col_orden]
        elif col_aviso and registro[col_aviso] != 'Sin información':
            termino_busqueda = registro[col_aviso]
            
        if termino_busqueda:
            url_gdrive = generar_link_gdrive(termino_busqueda)
            st.link_button(
                label=f"📂 Buscar OT '{termino_busqueda}' en Google Drive", 
                url=url_gdrive, 
                use_container_width=True
            )
            st.write("") 
        
        lat, lon = None, None
        url_maps = ""
        if col_geo and registro[col_geo] != 'Sin información':
            lat, lon = extraer_coordenadas(registro[col_geo])
            if lat and lon:
                url_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

        nombre_area = ""
        if col_area and registro[col_area] != 'Sin información':
            nombre_area = str(registro[col_area]).strip()
        titulo_rtem = f"RTEM {nombre_area}" if nombre_area else "RTEM"

        pdf_bytes = generar_pdf_orden(val_orden, val_aviso, valor_status, datos_mostrar, color_principal, titulo_rtem)
        st.download_button(
            label="📄 Descargar Ficha en PDF para Terreno",
            data=pdf_bytes,
            file_name=f"Ficha_OT_{val_orden}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        st.write("")

        st.markdown("🖼️ **Vista previa de Inspección**")
        foto_subida = st.file_uploader("Sube o arrastra la imagen de esta orden:", type=["png", "jpg", "jpeg"], key="visor_foto")
        
        if foto_subida is not None:
            st.image(foto_subida, caption=f"Evidencia - OT {termino_busqueda}", use_container_width=True)

        st.markdown("---")

        if lat and lon:
            st.link_button(
                label="🗺️ Abrir en Google Maps (Pantalla completa)", 
                url=url_maps, 
                use_container_width=True
            )
            mapa_html = f"""
            <iframe 
                width="100%" 
                height="350" 
                frameborder="0" 
                scrolling="no" 
                marginheight="0" 
                marginwidth="0" 
                src="https://maps.google.com/maps?q={lat},{lon}&hl=es&z=16&output=embed"
                style="border-radius: 8px; border: 1px solid #ddd; margin-top: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
            </iframe>
            """
            st.markdown(mapa_html, unsafe_allow_html=True)
