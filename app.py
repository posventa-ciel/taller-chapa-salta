import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import calendar
import re
import time
import json
import gspread

# --- VARIABLES SALTA CON GIDS REALES ---
ID_PLANILLA = "1yVeTn7UJV5izBURIXFjROwnH1xD8L3vDpesPVZzy45c"

# GIDS agrupa las pestañas de Mano de Obra Directa (Taller)
GIDS = {
    "GRUPO": "609774337",
    "PULIDOS": "527300176" 
} 

GID_TURNOS = "109364752" 
GID_REPUESTOS = "1212138688"
GID_TERCEROS = "431495457"   

URL_BASE = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid="

OBJETIVO_MENSUAL_PANOS = 360.0 

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds_dict)
    planilla = gc.open_by_key(ID_PLANILLA)
    try:
        hoja = planilla.worksheet("TURNOS")
    except:
        hoja = None 
except Exception as e:
    st.error(f"Error de conexión a Google Sheets: {e}")
    hoja = None

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Taller CENOA - Salta", layout="wide", initial_sidebar_state="expanded")

# --- ESTILOS CSS INYECTADOS ---
st.markdown("""<style>
    [data-testid="stSidebar"] { min-width: 240px !important; max-width: 240px !important; }
    .metric-card { background-color: white; border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 110px; margin-bottom: 15px;}
    .metric-title { color: #666; font-size: 0.85rem; font-weight: 600; margin-bottom: 5px; text-transform: uppercase; }
    .metric-value-money { color: #00235d; font-size: 1.8rem; font-weight: bold; margin: 0; }
    .metric-value-number { color: #00235d; font-size: 1.5rem; font-weight: bold; margin: 0; }
    .metric-subtitle-red { color: #dc3545; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .metric-subtitle-green { color: #28a745; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .kanban-col { background-color: #f8f9fa; border-radius: 8px; padding: 10px; border: 1px solid #e9ecef; }
</style>""", unsafe_allow_html=True)

st.title("🚀 Sistema de Gestión Taller CENOA - Salta")

MESES_ES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

formato_pesos = lambda x: f"$ {x:,.0f}".replace(',', '.')

# --- LÓGICA DE FECHAS ---
anio_actual = datetime.now().year
FERIADOS_ARG = [date(anio_actual, 3, 24), date(anio_actual, 4, 2), date(anio_actual, 4, 3)]

def dias_habiles_del_mes(anio, mes):
    _, ult_dia = calendar.monthrange(anio, mes)
    dias = sum(1 for d in range(1, ult_dia + 1) if date(anio, mes, d).weekday() < 5 and date(anio, mes, d) not in FERIADOS_ARG)
    return max(1, dias)

def parsear_fecha_español(texto):
    if pd.isna(texto) or str(texto).strip() == "": return None 
    texto = str(texto).lower().strip()
    match_dm = re.match(r'^(\d{1,2})[-/](\d{1,2})$', texto)
    if match_dm: return datetime(datetime.now().year, int(match_dm.groups()[1]), int(match_dm.groups()[0]))
    try:
        res = pd.to_datetime(texto, dayfirst=True)
        if pd.notna(res): return res.to_pydatetime()
    except: pass
    return None

def limpiar_num(val):
    v = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
    try: return float(re.findall(r"[-+]?\d*\.\d+|\d+", v)[0]) if re.findall(r"[-+]?\d*\.\d+|\d+", v) else 0.0
    except: return 0.0

@st.cache_data(ttl=300)
def obtener_turnos():
    columnas_base = ['Tipo', 'Fecha', 'Hora', 'Vehiculo', 'Patente', 'Asesor', 'Precio', 'Paños', 'Observaciones', 'Cliente', 'Ticket', 'Recibido', 'Fotos', 'Referencia', 'Cancelado', 'Eliminar']
    try:
        d = pd.read_csv(f"{URL_BASE}{GID_TURNOS}", dtype=str)
        d.columns = d.columns.str.strip().str.upper()
        if 'PATENTE' in d.columns: d = d.dropna(subset=['PATENTE']); d = d[d['PATENTE'].str.strip() != ""]
        filas = []
        for _, row in d.iterrows():
            col_fecha = next((c for c in d.columns if 'FECH' in c), None)
            fecha_turno = parsear_fecha_español(row.get(col_fecha, '')) or datetime.now()
            val_turno = str(row.get('TURNO', '')).strip().upper()
            es_cancelado = val_turno in ["CANCELADO", "C"]
            tipo_turno = '🚶‍♂️ SIN TURNO' if val_turno in ["N", "NO"] else '📅 PROGRAMADO'
            
            filas.append({
                'Tipo': tipo_turno, 'Fecha': fecha_turno.date(), 'Hora': str(row.get('HORA', '')).strip(),
                'Vehiculo': str(row.get('VEHICULO', '')).upper(), 'Patente': str(row.get('PATENTE', '')).upper(),
                'Asesor': str(row.get('ASESOR', 'SIN ASIGNAR')).strip().upper(),
                'Ticket': str(row.get('N° TICKET', '')).strip(), 'Recibido': str(row.get('RECIBIDO', '')).strip().upper() == 'SI',
                'Fotos': str(row.get('FOTOS', '')).strip().upper() == 'SI', 'Referencia': str(row.get('N° REFERENCIA', '')).strip(),
                'Cancelado': es_cancelado, 'Eliminar': False
            })
        return pd.DataFrame(filas)
    except: return pd.DataFrame(columns=columnas_base)

@st.cache_data(ttl=300)
def obtener_datos_taller(gid_str, nombre_grupo):
    if not gid_str or gid_str == "": return pd.DataFrame()
    try:
        d_raw = pd.read_csv(f"{URL_BASE}{gid_str}", dtype=str, header=None)
        idx_header = 0
        for i in range(min(15, len(d_raw))):
            if 'DOMINIO' in " ".join(d_raw.iloc[i].fillna("").astype(str).str.upper()) or 'PATENTE' in " ".join(d_raw.iloc[i].fillna("").astype(str).str.upper()):
                idx_header = i; break
                
        cols = [str(c).strip().upper() if pd.notna(c) else f"V_{j}" for j, c in enumerate(d_raw.iloc[idx_header])]
        d_raw.columns = cols
        d = d_raw.iloc[idx_header + 1:].reset_index(drop=True)
        
        renames = {}
        for c in d.columns:
            if 'ESTADO FAC' in c or c == 'FAC': renames[c] = 'ESTADO_FAC'
            elif c == 'ESTADO': renames[c] = 'ESTADO_TALLER'
            elif 'FASE' in c: renames[c] = 'FASE_TALLER'
            elif 'EMPRESA' in c or 'COMPAÑIA' in c or 'CLIENTE' in c: renames[c] = 'CLIENTE'
            elif 'F. PROM' in c or 'PROMESA' in c: renames[c] = 'FECHA_PROMESA_I'
            elif 'INGR' in c or 'INGRESO' in c: renames[c] = 'FECHA_INGRESO_TALLER'
            elif c == 'PATENTE' or c == 'DOMINIO': renames[c] = 'PATENTE'
            elif c == 'PRECIO': renames[c] = 'PRECIO'
            elif c == 'ASESOR': renames[c] = 'ASESOR'
            elif c == 'VEHICULO' or 'MARCA' in c: renames[c] = 'VEHICULO'
            elif c == 'PAÑOS' or 'PAÑO' in c: renames[c] = 'PAÑOS'

        d = d.rename(columns=renames)
        if 'PATENTE' in d.columns: 
            d = d.dropna(subset=['PATENTE'])
            d = d[d['PATENTE'].str.strip() != ""]
            filas = []
            for _, row in d.iterrows():
                f_fin = parsear_fecha_español(row.get('FECHA_PROMESA_I', ''))
                f_ing = parsear_fecha_español(row.get('FECHA_INGRESO_TALLER', ''))
                mes_hist = f_fin.strftime('%Y-%m') if f_fin else "SIN FECHA"
                panos = limpiar_num(row.get('PAÑOS', 0))
                
                filas.append({
                    'Grupo': nombre_grupo, 'Patente': str(row.get('PATENTE', '')), 'Vehiculo': str(row.get('VEHICULO', '')),
                    'Asesor': str(row.get('ASESOR', 'SIN ASIGNAR')).strip().upper() or "SIN ASIGNAR",
                    'Cliente': str(row.get('CLIENTE', 'PARTICULAR')).strip().upper() or "PARTICULAR",
                    'Fecha_Ingreso': f_ing.date() if f_ing else None, 'Fecha_Promesa_Disp': f_fin.date() if f_fin else None,
                    'Mes_Hist': mes_hist, 'Paños': panos, 'Precio': limpiar_num(row.get('PRECIO', 0)),
                    'Estado_Fac': str(row.get('ESTADO_FAC', '')).replace('.', '').strip().upper(),
                    'Estado_Taller': str(row.get('ESTADO_TALLER', '')).strip().upper() or "SIN ESTADO",
                    'Fase_Taller': str(row.get('FASE_TALLER', '')).strip().upper() or "SIN FASE ASIGNADA"
                })
            return pd.DataFrame(filas)
    except: return pd.DataFrame()

# --- CARGA DE DATOS ---
if 'memoria_turnos' not in st.session_state: st.session_state.memoria_turnos = obtener_turnos()
if 'entregas_confirmadas' not in st.session_state: st.session_state.entregas_confirmadas = []

df_taller = pd.DataFrame()
for nombre, gid in GIDS.items():
    df_temp = obtener_datos_taller(gid, nombre)
    if not df_temp.empty: df_taller = pd.concat([df_taller, df_temp], ignore_index=True)

df_repuestos = obtener_datos_taller(GID_REPUESTOS, "REPUESTOS")
df_terceros = obtener_datos_taller(GID_TERCEROS, "TERCEROS")

hoy = datetime.today()
hoy_ym = hoy.strftime('%Y-%m')

# ---------------------------------------------------------
# LECTURA DINÁMICA ASESORES
# ---------------------------------------------------------
if not df_taller.empty:
    asesores_unicos = [str(a).strip().upper() for a in df_taller['Asesor'].unique() if pd.notna(a) and str(a).strip().upper() != "SIN ASIGNAR"]
    ASESORES_LISTA = ["SIN ASIGNAR"] + sorted(list(set(asesores_unicos)))
else: ASESORES_LISTA = ["SIN ASIGNAR"]

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("### 📅 Filtro Mensual")
    meses_disp = sorted(list(set(df_taller['Mes_Hist'].dropna().unique().tolist() if not df_taller.empty else [])), reverse=True)
    opciones_meses = ["🗓️ MES ACTUAL", "♾️ TODOS"] + meses_disp
    mes_seleccionado = st.selectbox("Período de Análisis", opciones_meses)
    mes_filtro = hoy_ym if mes_seleccionado == "🗓️ MES ACTUAL" else "TODOS" if mes_seleccionado == "♾️ TODOS" else mes_seleccionado
    st.divider()
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# --- APLICAR FILTROS ---
def filtrar_por_mes(dataframe):
    if dataframe.empty or mes_filtro == "TODOS": return dataframe
    return dataframe[(dataframe['Mes_Hist'] == mes_filtro) | (dataframe['Mes_Hist'] == 'SIN FECHA')]

df_taller_f = filtrar_por_mes(df_taller)
df_rep_f = filtrar_por_mes(df_repuestos)
df_ter_f = filtrar_por_mes(df_terceros)

# --- TABS ---
tab_turnos, tab_prog, tab_fac, tab_terceros, tab_audit = st.tabs(["📋 Turnero y Balance", "🛠️ Taller y Kanban", "💰 Facturación y Repuestos", "🤝 Terceros", "🔎 Auditoría"])

# ==========================================
# PESTAÑA 1: TURNERO Y BALANCE DE CARGA
# ==========================================
with tab_turnos:
    st.subheader("📋 Ingresos, Entregas y Balance de Carga")
    
    st.markdown("### ⚖️ Balance de Carga Operativa (Cuellos de Botella)")
    st.caption("Visualización de ingresos y entregas para evitar la saturación de principio/fin de semana y los cuellos de botella a fin de mes.")
    if not df_taller_f.empty:
        c_bal1, c_bal2 = st.columns(2)
        
        with c_bal1:
            # Saturación por día de la semana
            df_ingresos = df_taller_f[df_taller_f['Fecha_Ingreso'].notna()].copy()
            df_entregas = df_taller_f[df_taller_f['Fecha_Promesa_Disp'].notna()].copy()
            
            df_ingresos['Dia_Semana'] = df_ingresos['Fecha_Ingreso'].apply(lambda x: x.weekday())
            df_entregas['Dia_Semana'] = df_entregas['Fecha_Promesa_Disp'].apply(lambda x: x.weekday())
            
            conteo_ingresos = df_ingresos['Dia_Semana'].value_counts().reindex(range(7), fill_value=0)
            conteo_entregas = df_entregas['Dia_Semana'].value_counts().reindex(range(7), fill_value=0)
            
            df_dias = pd.DataFrame({'Día': DIAS_SEMANA, 'Recepciones': conteo_ingresos.values, 'Entregas': conteo_entregas.values})
            fig_dias = go.Figure(data=[
                go.Bar(name='📥 Recepciones', x=df_dias['Día'], y=df_dias['Recepciones'], marker_color='#00235d'),
                go.Bar(name='📤 Entregas', x=df_dias['Día'], y=df_dias['Entregas'], marker_color='#28a745')
            ])
            fig_dias.update_layout(title="Saturación por Día de la Semana", barmode='group')
            st.plotly_chart(fig_dias, use_container_width=True)
            
        with c_bal2:
            # Calendario de picos
            conteo_fechas = df_entregas['Fecha_Promesa_Disp'].value_counts().reset_index()
            conteo_fechas.columns = ['Fecha', 'Cantidad']
            conteo_fechas = conteo_fechas.sort_values('Fecha')
            promedio_ideal = len(df_entregas) / dias_habiles_del_mes(datetime.now().year, datetime.now().month) if not df_entregas.empty else 0
            
            fig_cal = px.bar(conteo_fechas, x='Fecha', y='Cantidad', title="Calendario de Entregas (Picos)", text='Cantidad')
            fig_cal.update_traces(marker_color='#28a745')
            fig_cal.add_hline(y=promedio_ideal, line_dash="dash", line_color="red", annotation_text=f"Promedio Ideal: {promedio_ideal:.1f}/día")
            st.plotly_chart(fig_cal, use_container_width=True)

# ==========================================
# PESTAÑA 2: KANBAN Y PROGRAMACIÓN
# ==========================================
with tab_prog:
    st.subheader("🛠️ Programación y Kanban")
    if not df_taller_f.empty:
        asesor_filtro_prog = st.selectbox("👔 Filtrar por Asesor", ["TODOS"] + ASESORES_LISTA)
        df_prog = df_taller_f.copy()
        if asesor_filtro_prog != "TODOS": df_prog = df_prog[df_prog['Asesor'].str.contains(asesor_filtro_prog.split()[0], case=False, na=False)]

        df_kanban = df_prog[df_prog['Estado_Taller'].str.contains("PROCESO|DETENIDO", na=False)].copy()
        df_kanban.loc[df_kanban['Estado_Taller'].str.contains("DETENIDO", na=False), 'Fase_Taller'] = "⛔ DETENIDOS"
        
        orden_ideal = ["SIN FASE ASIGNADA", "CHAPA", "PREPARACION", "PINTURA", "ARMADO", "PULIDO", "⛔ DETENIDOS"]
        
        cols_kanban = st.columns(len(orden_ideal))
        for idx, fase in enumerate(orden_ideal):
            with cols_kanban[idx]:
                st.markdown(f"<div class='kanban-col'><h5 style='text-align:center; color:#00235d; margin: 0; font-size: 0.8rem;'>{fase}</h5></div>", unsafe_allow_html=True)
                if fase == "SIN FASE ASIGNADA": df_fase = df_kanban[(df_kanban['Fase_Taller'] == "") | (df_kanban['Fase_Taller'].isna()) | (df_kanban['Fase_Taller'] == "SIN FASE ASIGNADA")]
                else: df_fase = df_kanban[df_kanban['Fase_Taller'].str.contains(fase[:4], na=False, case=False)]
                
                for _, row in df_fase.iterrows():
                    color = "#dc3545" if fase == "⛔ DETENIDOS" else "#17a2b8"
                    st.markdown(f"<div style='background: white; padding: 8px; margin-top: 8px; border-left: 5px solid {color}; box-shadow: 1px 1px 3px rgba(0,0,0,0.1); font-size: 0.85em;'><strong>{row['Patente']}</strong><br>{row['Vehiculo'][:15]}<br><span style='color: gray;'>📦 {row['Paños']} p. | {row['Asesor'].split()[0]}</span></div>", unsafe_allow_html=True)

# ==========================================
# PESTAÑA 3: FACTURACIÓN Y REPUESTOS
# ==========================================
with tab_fac:
    st.subheader("💰 Análisis de Facturación (Mano de Obra y Repuestos)")
    
    # Cálculos MO (del taller)
    df_mo_fac = df_taller_f[df_taller_f['Estado_Fac'] == 'FAC']
    df_mo_si = df_taller_f[df_taller_f['Estado_Fac'] == 'SI']
    df_mo_no = df_taller_f[df_taller_f['Estado_Fac'] == 'NO']
    
    mo_fac_plata, mo_fac_panos = df_mo_fac['Precio'].sum(), df_mo_fac['Paños'].sum()
    mo_si_plata, mo_si_panos = df_mo_si['Precio'].sum(), df_mo_si['Paños'].sum()
    mo_no_plata, mo_no_panos = df_mo_no['Precio'].sum(), df_mo_no['Paños'].sum()
    mo_est_plata = mo_fac_plata + mo_si_plata

    # Cálculos Repuestos
    df_rep_fac = df_rep_f[df_rep_f['Estado_Fac'] == 'FAC']
    df_rep_si = df_rep_f[df_rep_f['Estado_Fac'] == 'SI']
    df_rep_no = df_rep_f[df_rep_f['Estado_Fac'] == 'NO']
    
    rep_fac_plata = df_rep_fac['Precio'].sum()
    rep_si_plata = df_rep_si['Precio'].sum()
    rep_no_plata = df_rep_no['Precio'].sum()
    rep_est_plata = rep_fac_plata + rep_si_plata
    
    # Totales
    total_fac = mo_fac_plata + rep_fac_plata
    total_est = mo_est_plata + rep_est_plata

    st.markdown("### 💼 Rentabilidad Estimada al Cierre")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="metric-card"><div class="metric-title">Mano de Obra (Taller)</div><div class="metric-value-money">{formato_pesos(mo_est_plata)}</div><div class="metric-subtitle-gray">Facturado: {formato_pesos(mo_fac_plata)}</div><div class="metric-subtitle-green">Aprobado (SI): {formato_pesos(mo_si_plata)}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-title">Repuestos</div><div class="metric-value-money" style="color: #6f42c1;">{formato_pesos(rep_est_plata)}</div><div class="metric-subtitle-gray">Facturado: {formato_pesos(rep_fac_plata)}</div><div class="metric-subtitle-green">Aprobado (SI): {formato_pesos(rep_si_plata)}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card" style="border: 2px solid #00235d;"><div class="metric-title">Facturación Total (MO + Rep)</div><div class="metric-value-money">{formato_pesos(total_est)}</div><div class="metric-subtitle-gray">Total Facturado (FAC): {formato_pesos(total_fac)}</div></div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📊 Análisis de Producción Detallado")
    
    if not df_taller_f.empty:
        # Gráficos combinados de barras (como en la foto que pasaste)
        c_graf1, c_graf2 = st.columns(2)
        
        datos_barras = pd.DataFrame({
            'Estado': ['Facturado (FAC)', 'Aprobado (SI)', 'Proyección NO (Próx Mes)'],
            'Paños': [mo_fac_panos, mo_si_panos, mo_no_panos],
            'Plata (MO)': [mo_fac_plata, mo_si_plata, mo_no_plata]
        })
        
        with c_graf1:
            fig_panos = px.bar(datos_barras, x='Estado', y='Paños', title="Paños Físicos en Taller", text_auto='.1f', color='Estado', color_discrete_map={'Facturado (FAC)': '#28a745', 'Aprobado (SI)': '#adb5bd', 'Proyección NO (Próx Mes)': '#17a2b8'})
            st.plotly_chart(fig_panos, use_container_width=True)
        
        with c_graf2:
            fig_plata = px.bar(datos_barras, x='Estado', y='Plata (MO)', title="Montos en Pesos (Mano de Obra)", text_auto='$.3s', color='Estado', color_discrete_map={'Facturado (FAC)': '#28a745', 'Aprobado (SI)': '#adb5bd', 'Proyección NO (Próx Mes)': '#17a2b8'})
            st.plotly_chart(fig_plata, use_container_width=True)

# ==========================================
# PESTAÑA 4: TERCEROS
# ==========================================
with tab_terceros:
    st.subheader("🤝 Gestión de Terceros")
    if not df_ter_f.empty:
        ter_fac = df_ter_f[df_ter_f['Estado_Fac'] == 'FAC']['Precio'].sum()
        ter_si = df_ter_f[df_ter_f['Estado_Fac'] == 'SI']['Precio'].sum()
        
        c_t1, c_t2 = st.columns(2)
        c_t1.markdown(f'<div class="metric-card"><div class="metric-title">Terceros Facturados</div><div class="metric-value-money" style="color:#28a745;">{formato_pesos(ter_fac)}</div></div>', unsafe_allow_html=True)
        c_t2.markdown(f'<div class="metric-card"><div class="metric-title">Terceros Pendientes (SI)</div><div class="metric-value-money" style="color:#ffc107;">{formato_pesos(ter_si)}</div></div>', unsafe_allow_html=True)
        
        st.dataframe(df_ter_f[['Patente', 'Vehiculo', 'Cliente', 'Asesor', 'Estado_Fac', 'Precio']], use_container_width=True)
    else: st.info("No hay datos cargados en la pestaña Terceros para este mes (o no configuraste el GID).")

# ==========================================
# PESTAÑA 5: AUDITORÍA DE CARGAS
# ==========================================
with tab_audit:
    st.subheader("🔎 Auditoría y Calidad de Datos")
    st.caption("Revisión automática de errores en el Excel de Salta.")
    
    if not df_taller.empty: # La auditoría se hace sobre TODOS los datos, no solo el mes filtrado
        errores = []
        
        # 1. Autos sin Asesor
        sin_asesor = df_taller[df_taller['Asesor'] == 'SIN ASIGNAR']
        if not sin_asesor.empty: errores.append(f"🔴 **{len(sin_asesor)} vehículos** no tienen Asesor asignado (Columna ASESOR vacía).")
            
        # 2. Autos en Taller sin Estado
        sin_estado = df_taller[df_taller['Estado_Taller'] == 'SIN ESTADO']
        if not sin_estado.empty: errores.append(f"🔴 **{len(sin_estado)} vehículos** no tienen Estado de Taller asignado.")
            
        # 3. Entregados sin facturar (Peligro de pérdida de plata)
        entregados_pendientes = df_taller[(df_taller['Estado_Taller'].str.contains('ENTREGADO', na=False)) & (~df_taller['Estado_Fac'].isin(['FAC', 'SI']))]
        if not entregados_pendientes.empty: errores.append(f"⚠️ **{len(entregados_pendientes)} vehículos** figuran como ENTREGADOS pero no tienen estado de facturación (FAC o SI).")
            
        # 4. Facturados con Precio Cero
        fac_cero = df_taller[(df_taller['Estado_Fac'] == 'FAC') & (df_taller['Precio'] == 0)]
        if not fac_cero.empty: errores.append(f"⚠️ **{len(fac_cero)} vehículos** están marcados como 'FAC' pero el Precio es $0.")

        if errores:
            for e in errores: st.markdown(e)
            if not entregados_pendientes.empty:
                st.write("#### Detalle: Entregados Pendientes de Acción Administrativa")
                st.dataframe(entregados_pendientes[['Patente', 'Vehiculo', 'Asesor', 'Estado_Taller', 'Estado_Fac']], hide_index=True)
        else: st.success("🎉 ¡Excelente! No se detectaron errores graves en la carga de datos del Excel.")
