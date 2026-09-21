import re
import unicodedata
import urllib.parse
import pandas as pd
import streamlit as st
import plotly.express as px
from fpdf import FPDF

st.set_page_config(page_title="Control y Consulta RTEM", layout="wide")
st.title("🔎 Sistema de Consulta e Inspecciones RTEM")

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE GOOGLE SHEETS Y SHAREPOINT
# -----------------------------------------------------------------------------
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1PjTQCns0CYSzo2l1U9GXnSPS7qBAcVts-G0BwRxjSlQ/edit?gid=0#gid=0"
NOMBRE_HOJA = "Reparaciones activas"

# Enlace de tu carpeta "RTEM OT" en Google Drive
GDRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1zGSlDQu5o9waFqm211P344MAqxCC8AAK"

def generar_link_gdrive(termino_busqueda):
    """Genera un enlace de búsqueda directa dentro de tu carpeta de Google Drive"""
    # Puedes abrir la carpeta general de Google Drive o filtrar por el término de búsqueda
    busqueda_encoded = urllib.parse.quote(str(termino_busqueda))
    return f"https://drive.google.com/drive/u/0/search?q={busqueda_encoded}"

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

def generar_link_sharepoint(termino_busqueda):
    id_encoded = urllib.parse.quote(RUTA_BASE_DOCUMENTOS, safe="")
    busqueda_encoded = urllib.parse.quote(str(termino_busqueda))
    return f"{SHAREPOINT_DOMAIN}?id={id_encoded}&viewid={VIEW_ID}&q={busqueda_encoded}"

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
    """Genera el PDF real con el título personalizado y los bloques de datos sin enlaces externos"""
    pdf = FPDF()
    pdf.add_page()
    
    rgb = hex_to_rgb(color_hex)
    
    # 1. Título Principal con el área y el color del estatus
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(*rgb)
    pdf.cell(0, 10, titulo_rtem, ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    
    # 2. Orden y Aviso destacados abajo del título
    pdf.set_font("Arial", "B", 12)
    txt_orden_aviso = f"ORDEN: {val_orden}   |   AVISO: {val_aviso}"
    pdf.cell(0, 8, txt_orden_aviso, ln=True, align="C")
    pdf.ln(3)
    
    # Estatus Actual con su color respectivo
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*rgb)
    pdf.cell(0, 7, f"Estatus Actual: {valor_status}", ln=True)
    pdf.set_text_color(0, 0, 0)
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Detalle Tecnico de la Reparacion", ln=True)
    pdf.ln(2)
    
    # Recorremos los datos aplicando el color del estatus en los bordes de los recuadros
    for k, v in datos_mostrar.items():
        k_str = str(k)
        k_norm = normalizar_texto(k_str)
        
        palabras_excluidas = ["unnamed", "indicador abc", "estatus", "status", "cantidad", "perfil catalogo", "perfil"]
        if any(p in k_norm for p in palabras_excluidas):
            continue
            
        k_clean = k_str.encode('latin-1', 'replace').decode('latin-1')
        v_clean = str(v).encode('latin-1', 'replace').decode('latin-1')
        
        pdf.set_draw_color(*rgb)
        
        # Etiqueta del campo
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(190, 6, f"  {k_clean}", border="TRL", ln=True, fill=True)
        
        # Valor con ajuste automático multilínea
        pdf.set_font("Arial", "", 9)
        pdf.multi_cell(190, 6, f"  {v_clean}", border="BRL")
        pdf.ln(2)
        
    pdf.set_draw_color(0, 0, 0)
    return bytes(pdf.output())

# --- CARGA AUTOMÁTICA DESDE GOOGLE SHEETS ---
SHEET_ID = "1PjTQCns0CYSzo2l1U9GXnSPS7qBAcVts-G0BwRxjSlQ"
nombre_hoja_encoded = urllib.parse.quote(NOMBRE_HOJA)
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={nombre_hoja_encoded}"

try:
    # Leemos directamente con pandas usando la URL codificada
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


# --- VISTA PRINCIPAL ---
st.markdown(f"**Registros encontrados:** `{len(df_filtrado)}` de `{len(df)}` totales.")

# Pestañas Principales en la UI
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
                
                fig_status = px.bar(
                    df_status_counts, 
                    x='Estatus', 
                    y='Cantidad',
                    color='Estatus',
                    color_discrete_map=MAPA_COLORES_ESTATUS,
                    text='Cantidad'
                )
                fig_status.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total")
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("No se encontró la columna de Estatus para graficar.")
                
        with col_g2:
            st.markdown("##### 📊 Distribución por Área")
            if col_area:
                df_area_counts = df_filtrado[col_area].value_counts().reset_index()
                df_area_counts.columns = ['Área', 'Cantidad']
                
                fig_area = px.bar(
                    df_area_counts,
                    x='Área',
                    y='Cantidad',
                    text='Cantidad'
                )
                fig_area.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total")
                st.plotly_chart(fig_area, use_container_width=True)
            else:
                st.info("No se encontró la columna de Área para graficar.")

# Si hay un registro seleccionado o el filtro deja exactamente 1 fila
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
        # BLOQUE DE ESTATUS CON COLORES SINCRONIZADOS
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
            url_sharepoint = generar_link_sharepoint(termino_busqueda)
            st.link_button(
                label=f"📂 Abrir Carpeta OT '{termino_busqueda}' en SharePoint", 
                url=url_sharepoint, 
                use_container_width=True
            )
            st.write("") 
        
        # Procesar coordenadas y URL de mapas para la app web
        lat, lon = None, None
        url_maps = ""
        if col_geo and registro[col_geo] != 'Sin información':
            lat, lon = extraer_coordenadas(registro[col_geo])
            if lat and lon:
                url_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

        # Obtener el valor del área para el título del PDF (ej. "RTEM AFR")
        nombre_area = ""
        if col_area and registro[col_area] != 'Sin información':
            nombre_area = str(registro[col_area]).strip()
        titulo_rtem = f"RTEM {nombre_area}" if nombre_area else "RTEM"

        # --- BOTÓN DE DESCARGA DIRECTA DE PDF ---
        pdf_bytes = generar_pdf_orden(val_orden, val_aviso, valor_status, datos_mostrar, color_principal, titulo_rtem)
        st.download_button(
            label="📄 Descargar Ficha en PDF para Terreno",
            data=pdf_bytes,
            file_name=f"Ficha_OT_{val_orden}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        st.write("")

        st.markdown("🖼️ **Vista previa de Inspección (Ej: 'app')**")
        foto_subida = st.file_uploader("Sube o arrastra la imagen de esta orden:", type=["png", "jpg", "jpeg"], key="visor_foto")
        
        if foto_subida is not None:
            st.image(foto_subida, caption=f"Evidencia - OT {termino_busqueda}", use_container_width=True)

        st.markdown("---")

        # MAPA DE GOOGLE MAPS EN LA APLICACIÓN CON ZOOM EQUILIBRADO (z=16)
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
