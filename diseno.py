"""Presentación y análisis RTEM. Los gráficos cuentan registros, no órdenes únicas."""
from io import BytesIO
from pathlib import Path
from html import escape
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image as PDFImage
from PIL import Image, ImageOps, UnidentifiedImageError

AZUL = '#142D4E'
TURQUESA = '#087F8C'


def aplicar_diseno(st):
    st.markdown('''<style>
    .stApp {background:var(--background-color);}
    .block-container {max-width:1480px;padding-top:2rem;padding-bottom:3rem;}
    h1,h2,h3 {letter-spacing:-.035em;}
    [data-testid="stMetric"] {border:1px solid #9aaabc55;border-radius:14px;padding:18px;}
    [data-testid="stMetricLabel"] {font-size:13px;}
    [data-testid="stMetricValue"] {font-weight:700;}
    [data-testid="stSidebar"] {border-right:1px solid #9aaabc44;}
    .rtem-hero {background:linear-gradient(110deg,#142d4e,#17536b);padding:28px 32px;border-radius:18px;color:white;margin-bottom:24px;}
    .rtem-hero p {color:#d7e7ed;margin:0;}
    .rtem-hero h1 {color:white;font-size:32px;margin:4px 0 10px;}
    .rtem-tag {text-transform:uppercase;letter-spacing:3px;font-size:11px;color:#9de5df;}
    </style><div class="rtem-hero"><span class="rtem-tag">Operaciones · Control RTEM</span>
    <h1>Reparaciones e inspecciones</h1><p>Visibilidad del estado de las reparaciones y fichas técnicas para terreno.</p></div>''', unsafe_allow_html=True)


def panel(st, px, pd, vista, claves, colores):
    st.subheader('Panorama operativo')
    st.caption('Todos los indicadores cuentan registros de la selección actual. Una orden puede aparecer más de una vez.')
    estado, area = claves['estado'], claves['area']
    if not estado:
        st.info('Se necesita una columna de estatus para mostrar el panorama operativo.')
        return
    conteos = vista[estado].value_counts()
    total = len(vista)
    metricas = [('Definitivas', 'RTEM DEFINITIVA'), ('No ejecutadas', 'RTEM NO EJECUTADA'),
                ('Ejecución parcial', 'RTEM EJECUTADA PARCIAL'), ('Pendientes de revisión', 'RTEM PENDIENTE REVISION')]
    for contenedor, (titulo, valor) in zip(st.columns(4), metricas):
        n = int(conteos.get(valor, 0))
        contenedor.metric(titulo, n, help=f'{n / total:.1%} de los registros filtrados. Coincidencia exacta con {valor}.')
    conocidos = set(colores)
    otros = int(conteos[~conteos.index.isin(conocidos)].sum())
    st.caption(f'Ejecutadas: {int(conteos.get("RTEM EJECUTADA", 0))} · Otros estatus o sin información: {otros}. Todos se incluyen en los gráficos.')

    def mostrar(fig, key, alto=390):
        fig.update_layout(template='plotly_white', height=alto, font=dict(family='Arial', size=12, color=AZUL),
                          margin=dict(l=20, r=25, t=25, b=35), paper_bgcolor='rgba(0,0,0,0)',
                          legend_title_text='', hoverlabel=dict(bgcolor='white'))
        st.plotly_chart(fig, use_container_width=True, key=key,
                        config={'displaylogo': False, 'toImageButtonOptions': {'format': 'png', 'scale': 2}})

    izquierda, derecha = st.columns([1, 1.4])
    resumen = conteos.rename_axis('Estatus').reset_index(name='Registros')
    mapa = {v: colores.get(v, '#8695A6') for v in resumen.Estatus}
    with izquierda:
        with st.container(border=True):
            st.markdown('#### Composición por estatus')
            fig = px.pie(resumen, names='Estatus', values='Registros', color='Estatus', color_discrete_map=mapa, hole=.72)
            fig.update_traces(textinfo='percent', textposition='inside', hovertemplate='%{label}<br>%{value} registros · %{percent}<extra></extra>')
            fig.add_annotation(text=f'<b>{total}</b><br>registros', x=.5, y=.5, showarrow=False, font_size=23)
            fig.update_layout(showlegend=True, legend=dict(orientation='h', y=-.15, x=0))
            mostrar(fig, 'composicion', 470)
    with derecha:
        with st.container(border=True):
            st.markdown('#### Volumen por estatus')
            fig = px.bar(resumen.sort_values('Registros'), x='Registros', y='Estatus', orientation='h', color='Estatus', color_discrete_map=mapa, text='Registros')
            fig.update_layout(showlegend=False, xaxis_title='Registros', yaxis_title='')
            fig.update_traces(textposition='outside', cliponaxis=False)
            mostrar(fig, 'volumen', 470)
    limite = st.select_slider('Máximo de áreas y emplazamientos visibles', options=[5, 10, 15, 20], value=10)
    if area:
        areas = vista[area].value_counts().head(limite).index
        subset = vista[vista[area].isin(areas)]
        cruce = pd.crosstab(subset[area], subset[estado]).reindex(areas)
        cruce.index.name, cruce.columns.name = 'Área', 'Estatus'
        largo = cruce.reset_index().melt(id_vars='Área', var_name='Estatus', value_name='Registros')
        with st.container(border=True):
            st.markdown('#### Comparación entre áreas')
            porcentaje = st.toggle('Comparar composición porcentual', value=False)
            fig = px.bar(largo, x='Registros', y='Área', color='Estatus', orientation='h', color_discrete_map=mapa,
                         category_orders={'Área': list(areas)})
            fig.update_layout(barmode='stack', barnorm='percent' if porcentaje else '', xaxis_title='Porcentaje de registros' if porcentaje else 'Registros', yaxis_title='', legend=dict(orientation='h', y=-.2))
            mostrar(fig, 'areas', max(430, len(areas)*42+160))
            st.caption(f'Se muestran {len(areas)} de {vista[area].nunique()} áreas, ordenadas por volumen. Cada barra porcentual suma 100%.')
        with st.expander('Ver concentración por área y estatus', expanded=True):
            fig = px.imshow(cruce, text_auto=True, aspect='auto', color_continuous_scale=['#F1F6FA', '#087F8C', '#142D4E'], labels={'color':'Registros'})
            mostrar(fig, 'matriz', max(330, len(areas)*36+130))
    emplazamiento = claves['emplazamiento']
    if emplazamiento:
        with st.container(border=True):
            st.markdown('#### Emplazamientos con mayor volumen')
            ranking = vista[emplazamiento].value_counts().head(limite).rename_axis('Emplazamiento').reset_index(name='Registros')
            fig = px.bar(ranking.sort_values('Registros'), x='Registros', y='Emplazamiento', orientation='h', text='Registros', color_discrete_sequence=[TURQUESA])
            mostrar(fig, 'emplazamientos', max(350, len(ranking)*35+90))
            st.caption('El volumen indica concentración de registros; no representa gravedad ni prioridad.')
    with st.expander('Datos de respaldo del panel'):
        resumen['Porcentaje'] = (resumen.Registros / total * 100).round(1)
        st.dataframe(resumen, hide_index=True, use_container_width=True)
        st.download_button('Descargar resumen CSV', resumen.to_csv(index=False).encode('utf-8-sig'), 'resumen_rtem.csv', 'text/csv')


def preparar_mapa(contenido):
    """Valida y normaliza la captura en memoria, manteniendo la imagen completa."""
    if len(contenido) > 10 * 1024 * 1024:
        raise ValueError('La captura debe pesar como máximo 10 MB.')
    try:
        with Image.open(BytesIO(contenido)) as original:
            if original.format not in {'PNG', 'JPEG'}:
                raise ValueError('Sube una imagen PNG o JPG.')
            if original.width * original.height > 20_000_000:
                raise ValueError('La captura debe tener como máximo 20 megapíxeles.')
            imagen = ImageOps.exif_transpose(original).convert('RGBA')
            fondo = Image.new('RGB', imagen.size, 'white')
            fondo.paste(imagen, mask=imagen.getchannel('A'))
            fondo.thumbnail((2400, 2400))
            salida = BytesIO()
            fondo.save(salida, format='PNG')
            return salida.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('No se pudo leer la captura. Prueba con otro archivo PNG o JPG.') from exc


def generar_pdf(registro, claves, actualizado, colores, normalizar, base, mapa=None):
    """Ficha imprimible A4, con cabecera repetida y detalle que puede continuar en otra página."""
    salida = BytesIO()
    orden = str(registro.get(claves['orden'], 'Sin información'))
    aviso = str(registro.get(claves['aviso'], 'Sin información'))
    estado = str(registro.get(claves['estado'], 'Sin información'))
    area = str(registro.get(claves['area'], 'Sin información'))
    color = colors.HexColor(colores.get(normalizar(estado).upper(), '#087F8C'))
    estilos = {
        'titulo': ParagraphStyle('titulo', fontName='Helvetica-Bold', fontSize=23, leading=28, textColor=colors.HexColor(AZUL), spaceAfter=8),
        'seccion': ParagraphStyle('seccion', fontName='Helvetica-Bold', fontSize=11, leading=15, textColor=colors.HexColor(AZUL), spaceBefore=16, spaceAfter=10, keepWithNext=True),
        'texto': ParagraphStyle('texto', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#30445A'), spaceAfter=7),
        'etiqueta': ParagraphStyle('etiqueta', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.HexColor('#617389'), spaceAfter=4, keepWithNext=True),
    }
    def p(valor, estilo='texto'):
        return Paragraph(escape(str(valor)).replace('\n', '<br/>'), estilos[estilo])
    doc = SimpleDocTemplate(salida, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=91, bottomMargin=51,
                            title=f'Ficha técnica RTEM - Orden {orden}', author='Control RTEM')
    story = [p('Ficha técnica de reparación', 'titulo'), p(f'Área / {area}'), Spacer(1, 8)]
    tarjetas = Table([[p('ORDEN', 'etiqueta'), p('AVISO', 'etiqueta')], [p(orden), p(aviso)]], colWidths=[255, 256])
    tarjetas.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F0F5F9')), ('BOX',(0,0),(-1,-1),.5,colors.HexColor('#DCE5EE')), ('LEFTPADDING',(0,0),(-1,-1),13), ('TOPPADDING',(0,0),(-1,0),11), ('BOTTOMPADDING',(0,1),(-1,1),10), ('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [tarjetas, Spacer(1, 12)]
    estado_tabla = Table([[p('ESTATUS ACTUAL', 'etiqueta'), p(estado)]], colWidths=[130, 381])
    estado_tabla.setStyle(TableStyle([('LINEBEFORE',(0,0),(0,-1),4,color), ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F7F9FB')), ('VALIGN',(0,0),(-1,-1),'TOP'), ('TOPPADDING',(0,0),(-1,-1),10), ('LEFTPADDING',(0,0),(-1,-1),12)]))
    story += [estado_tabla, p('01 / Detalle técnico', 'seccion')]
    excluidos = {claves['orden'], claves['aviso'], claves['estado'], claves['area']}
    for campo, valor in registro.items():
        if campo in excluidos:
            continue
        story += [p(campo, 'etiqueta'), p(valor), Spacer(1, 5)]
    if mapa is not None:
        captura = PDFImage(BytesIO(preparar_mapa(mapa)))
        escala = min(doc.width / captura.imageWidth, 270 / captura.imageHeight)
        captura.drawWidth = captura.imageWidth * escala
        captura.drawHeight = captura.imageHeight * escala
        captura.hAlign = 'CENTER'
        story += [KeepTogether([
            p('02 / Ubicación de la reparación', 'seccion'),
            captura, Spacer(1, 8),
            p('Captura de mapa adjuntada manualmente para esta reparación.')
        ])]
    numero = 3 if mapa is not None else 2
    story += [p(f'{numero:02d} / Registro de inspección en terreno', 'seccion'), p('Completar manualmente durante la inspección. Estos campos no constituyen una aprobación.')]
    casillas = Table([[p('Fecha: __________________'), p('Inspector/a: __________________________')],
                      [p('Observaciones:'), ''], ['', ''], ['', ''],
                      [p('Firma: __________________'), p('Referencia de evidencia: _________________')]], colWidths=[255,256], rowHeights=[32,24,26,26,36])
    casillas.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LINEBELOW',(0,2),(-1,3),.5,colors.HexColor('#CED8E2')), ('BOX',(0,0),(-1,-1),.6,colors.HexColor('#CED8E2')), ('LEFTPADDING',(0,0),(-1,-1),10), ('TOPPADDING',(0,0),(-1,-1),8)]))
    story += [KeepTogether([casillas])]
    def pagina(canvas, documento):
        canvas.saveState()
        w,h = A4
        canvas.setFillColor(colors.HexColor(AZUL)); canvas.rect(0,h-63,w,63,fill=1,stroke=0)
        canvas.setFillColor(colors.white); canvas.setFont('Helvetica-Bold',18); canvas.drawString(42,h-34,'RTEM')
        canvas.setFont('Helvetica',8); canvas.drawString(42,h-49,'CONTROL DE REPARACIONES / FICHA PARA TERRENO')
        logo = next((Path(base)/n for n in ['logojn.png','logo.png'] if (Path(base)/n).exists()),None)
        if logo:
            canvas.drawImage(str(logo),w-117,h-53,width=75,height=40,preserveAspectRatio=True,anchor='c',mask='auto')
        canvas.setStrokeColor(colors.HexColor('#DCE5EE')); canvas.line(42,39,w-42,39)
        canvas.setFillColor(colors.HexColor('#617389')); canvas.setFont('Helvetica',7)
        canvas.drawString(42,27,'Consulta de datos: '+str(actualizado))
        canvas.drawRightString(w-42,27,f'Página {documento.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=pagina, onLaterPages=pagina)
    return salida.getvalue()
