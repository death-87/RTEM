import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gestión Adicional RTEM", layout="wide")

st.title("📝 Módulo de Gestión y Notas de Terreno")
st.markdown("---")

EXCEL_PATH = "../Base_RTEM.xlsx"  # Subimos un nivel para buscar el archivo principal

if not os.path.exists(EXCEL_PATH):
    # Si se ejecuta desde la raíz o dentro de pages, ajustamos la ruta por seguridad
    EXCEL_PATH = "Base_RTEM.xlsx"

if os.path.exists(EXCEL_PATH):
    df = pd.read_excel(EXCEL_PATH, sheet_name="Reparaciones activas")
    st.success(f"✅ Base de datos cargada exitosamente. Total de registros: {len(df)}")
    
    # Ejemplo de componente interactivo para tu nueva página
    st.subheader("Filtro rápido de órdenes para notas de campo")
    
    if "ORDEN" in df.columns:
        ordenes_disponibles = df["ORDEN"].dropna().unique()
        orden_elegida = st.selectbox("Selecciona una Orden de Trabajo:", ordenes_disponibles)
        
        # Filtrar el registro seleccionado
        registro_actual = df[df["ORDEN"] == orden_elegida]
        
        if not registro_actual.empty:
            st.write("Detalles rápidos del registro seleccionado:")
            st.dataframe(registro_actual, use_container_width=True)
            
            # Área de texto para notas o comentarios de terreno
            st.text_area("✍️ Agregar observaciones o bitácora para esta orden:", placeholder="Escribe tus notas aquí...")
            if st.button("Guardar Observación"):
                st.info("¡Observación registrada temporalmente en la sesión!")
        else:
            st.warning("No se encontró información para esta orden.")
else:
    st.error(f"❌ No se encontró el archivo '{EXCEL_PATH}'. Asegúrate de que esté en la carpeta principal.")