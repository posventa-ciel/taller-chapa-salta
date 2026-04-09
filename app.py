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

# --- VARIABLES SALTA ---
ID_PLANILLA = "1yVeTn7UJV5izBURIXFjROwnH1xD8L3vDpesPVZzy45c"
GIDS = {"TALLER SALTA": "609774337"} 
GID_TURNOS = "PONER_AQUI_GID_TURNOS" # <--- ¡PEGÁ EL NÚMERO DE LA PESTAÑA TURNOS ACÁ!
URL_BASE = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid="

OBJETIVO_MENSUAL_PANOS = 360.0 # Objetivo de Salta

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
    .metric-subtitle-blue { color: #17a2b8; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .metric-subtitle-gray { color: #888; font-size: 0.8rem; margin-top: 5px; }
    .kanban-col { background-color: #f8f9fa; border-radius: 8px; padding: 10px; border: 1px solid #e9ecef; }
</style>""", unsafe_allow_html=True)

st.title("🚀 Sistema de Gestión Taller CENOA - Salta")

MESES_ES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

formato_pesos = lambda x: f"$ {x:,.0f}".replace(',', '.')
formato_panos = lambda x: f"{x:.1f}"

# --- LÓGICA DE DÍAS HÁBILES ---
anio_actual = datetime.now().year
FERIADOS_ARG = [date(anio_actual, 3, 24), date(anio_actual, 4, 2), date(anio_actual, 4, 3)]

def dias_habiles_del_mes(anio, mes):
    _, ult_dia = calendar.monthrange(anio, mes)
    dias = sum(1 for d in range(1, ult_dia + 1) if date(anio, mes, d).weekday() < 5 and date(anio, mes, d) not in FERIADOS_ARG)
    return max(1, dias)

def dias_habiles_restantes_mes(anio, mes):
    hoy_f = datetime.today().date()
    if anio == hoy_f.year and mes == hoy_f.month: dia_inicio = hoy_f.day
    elif date(anio, mes, 1) < hoy_f: return 0
    else: dia_inicio = 1
    _, ult_dia = calendar.monthrange(anio, mes)
    return sum(1 for d in range(dia_inicio, ult_dia + 1) if date(anio, mes, d).weekday() < 5 and date(anio, mes, d) not in FERIADOS_ARG)

def parsear_fecha_español(texto):
    if pd.isna(texto) or str(texto).strip() == "": return None 
    texto = str(texto).lower().strip()
    meses_abrev = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12}
    
    match_abrev = re.search(r'(\d{1,2})[-/]([a-z]{3})', texto)
    if match_abrev and meses_abrev.get(match_abrev.groups()[1]): return datetime(datetime.now().year, meses_abrev.get(match_abrev.groups()[1]), int(match_abrev.groups()[0]))
    match_dm = re.match(r'^(\d{1,2})[-/](\d{1,2})$', texto)
    if match_dm: return datetime(datetime.now().year, int(match_dm.groups()[1]), int(match_dm.groups()[0]))
    try:
        res = pd.to_datetime(texto, dayfirst=True)
        if pd.notna(res): return res.to_pydatetime()
    except: pass
    match_largo = re.search(r'(\d+)\s+de\s+([a-z]+)\s+de\s+(\d+)', texto)
    if match_largo: return datetime(int(match_largo.groups()[2]), MESES_ES.get(match_largo.groups()[1], 1), int(match_largo.groups()[0]))
    return None

def clasificar_abc(panos):
    if panos <= 3: return 'A (1-3 paños)'
    elif panos <= 7: return 'B (4-7 paños)'
    else: return 'C (8+ paños)'

def obtener_proxima_fecha_libre(dias_carga):
    fecha = datetime.today()
    dias_agregados = 0
    while dias_agregados < int(dias_carga):
        fecha += timedelta(days=1)
        if fecha.weekday() < 5 and fecha.date() not in FERIADOS_ARG: dias_agregados += 1
    return f"{DIAS_SEMANA[fecha.weekday()]} {fecha.strftime('%d/%m')}"

@st.cache_data(ttl=300)
def obtener_turnos():
    columnas_base = ['Tipo', 'Fecha', 'Hora', 'Vehiculo', 'Patente', 'Asesor', 'Precio', 'Paños', 'Observaciones', 'Tiempo_Entrega', 'Cliente', 'Seguro', 'Ticket', 'Recibido', 'Fotos', 'Referencia', 'Cancelado', 'Motivo_Cancelacion', 'Eliminar']
    if GID_TURNOS == "PONER_AQUI_GID_TURNOS": return pd.DataFrame(columns=columnas_base)
    try:
        d = pd.read_csv(f"{URL_BASE}{GID_TURNOS}", dtype=str)
        d.columns = d.columns.str.strip().str.upper()
        if 'PATENTE' in d.columns: d = d.dropna(subset=['PATENTE']); d = d[d['PATENTE'].str.strip() != ""]
        filas = []
        
        col_recibido = next((c for c in d.columns if 'RECIBID' in c), None)
        col_fotos = next((c for c in d.columns if 'FOTO' in c), None)
        col_turno = next((c for c in d.columns if 'TURNO' in c), 'TURNO')
        col_motivo = next((c for c in d.columns if 'MOTIVO' in c or 'CANCELACION' in c), None)
        if not col_motivo and len(d.columns) >= 17: col_motivo = d.columns[16]
            
        for _, row in d.iterrows():
            col_fecha = next((c for c in d.columns if 'FECH' in c), None)
            fecha_turno = parsear_fecha_español(row.get(col_fecha, '')) or datetime.now()
            asesor_raw = str(row.get('ASESOR', 'SIN ASIGNAR')).strip().upper()
            if not asesor_raw or asesor_raw == 'NAN': asesor_raw = "SIN ASIGNAR"
            col_tiempo = next((c for c in d.columns if 'TIEMPO' in c), None)
            
            val_recibido = str(row.get(col_recibido, '')).strip().upper() if col_recibido else ""
            bool_recibido = val_recibido in ['SI', 'SÍ', 'TRUE', '1', 'X']
            val_fotos = str(row.get(col_fotos, '')).strip().upper() if col_fotos else ""
            bool_fotos = val_fotos in ['SI', 'SÍ', 'TRUE', '1', 'X']
            
            val_ticket = str(row.get('N° TICKET', '')).strip(); val_ticket = "" if val_ticket == 'nan' else val_ticket
            val_referencia = str(row.get('N° REFERENCIA', '')).strip(); val_referencia = "" if val_referencia == 'nan' else val_referencia
            val_motivo_str = str(row.get(col_motivo, '')).replace('nan', '').strip() if col_motivo else ""
            val_turno_str = str(row.get(col_turno, '')).strip().upper()
            
            es_cancelado = val_turno_str in ["CANCELADO", "C"]
            tipo_turno = '🚶‍♂️ SIN TURNO' if val_turno_str in ["N", "NO"] else '📅 PROGRAMADO'
            
            filas.append({
                'Tipo': tipo_turno, 'Fecha': fecha_turno.date(), 'Hora': str(row.get('HORA TURNO', row.get('HORAS', ''))).strip(),
                'Vehiculo': str(row.get('VEHICULO', '')).upper(), 'Patente': str(row.get('PATENTE', '')).upper(),
                'Asesor': asesor_raw, 'Precio': str(row.get('PRECIO', '')).strip(), 'Paños': str(row.get('PAÑOS', '')).strip(),
                'Observaciones': str(row.get('OBSERVACION', str(row.get('OBSERVACIONES', '')))).strip(), 
                'Tiempo_Entrega': str(row.get(col_tiempo, '')) if col_tiempo else "",
                'Cliente': str(row.get('CLIENTE', '')).upper(), 'Seguro': str(row.get('SEGURO', '')).upper(),
                'Ticket': val_ticket, 'Referencia': val_referencia, 'Recibido': bool_recibido, 'Fotos': bool_fotos, 
                'Cancelado': es_cancelado, 'Motivo_Cancelacion': val_motivo_str, 'Eliminar': False
            })
        return pd.DataFrame(filas)
    except: return pd.DataFrame(columns=columnas_base)

@st.cache_data(ttl=300)
def obtener_datos_maestros():
    dfs = []
    for n, gid in GIDS.items():
        try:
            d_raw = pd.read_csv(f"{URL_BASE}{gid}", dtype=str, header=None)
            
            idx_header = 0
            for i in range(min(15, len(d_raw))):
                fila_str = " ".join(d_raw.iloc[i].fillna("").astype(str).str.upper())
                if 'DOMINIO' in fila_str or 'PATENTE' in fila_str:
                    idx_header = i
                    break
                    
            cols = []
            for j, val in enumerate(d_raw.iloc[idx_header]):
                val_str = str(val).strip().upper()
                if val_str == 'NAN' or val_str == 'NONE' or not val_str: cols.append(f"VACIA_{j}")
                else: cols.append(val_str)
                    
            d_raw.columns = cols
            d = d_raw.iloc[idx_header + 1:].reset_index(drop=True)

            renames = {}
            for c in d.columns:
                c_str = str(c).upper().strip()
                if 'ESTADO FAC' in c_str or c_str == 'FAC': renames[c] = 'ESTADO_FAC'
                elif c_str == 'ESTADO': renames[c] = 'ESTADO_TALLER'
                elif 'FASE' in c_str: renames[c] = 'FASE_TALLER'
                elif 'EMPRESA' in c_str or 'COMPAÑIA' in c_str or 'CLIENTE' in c_str:
                    if 'EMPRESA_TALLER' not in renames.values(): renames[c] = 'EMPRESA_TALLER'
                elif 'OBSERVACION' in c_str: renames[c] = 'OBSERVACIONES_TALLER'
                elif 'F. PROM' in c_str or 'PROMESA' in c_str: renames[c] = 'FECHA_PROMESA_I'
                elif 'INGR' in c_str or 'INGRESO' in c_str: renames[c] = 'FECHA_INGRESO_TALLER'
                elif 'HS PROM' in c_str or 'HORA' in c_str: renames[c] = 'HORA_ENTREGA'
                elif c_str == 'PATENTE' or c_str == 'DOMINIO': renames[c] = 'PATENTE'
                elif c_str == 'PRECIO': renames[c] = 'PRECIO'
                elif c_str == 'COSTO': renames[c] = 'COSTO'
                elif c_str == 'ASESOR': renames[c] = 'ASESOR'
                elif c_str == 'VEHICULO' or 'MARCA' in c_str: renames[c] = 'VEHICULO'
                elif c_str == 'PAÑOS' or 'PAÑO' in c_str: renames[c] = 'PAÑOS'
                elif 'DIAS' in c_str and 'TRABAJO' in c_str: renames[c] = 'DIAS_TRABAJO'
                elif c_str == 'MES': renames[c] = 'MES'

            d = d.rename(columns=renames)
            if 'MES' in d.columns: d['MES'] = d['MES'].replace(r'^\s*$', pd.NA, regex=True).ffill()
            d = d.loc[:, ~d.columns.duplicated()]

            if 'PATENTE' in d.columns: 
                d = d.dropna(subset=['PATENTE'])
                d = d[d['PATENTE'].str.strip() != ""]
                d['GRUPO_ORIGEN'] = n
                dfs.append(d)
        except Exception as e: print(f"Error cargando pestaña {n}: {e}")
        
    if not dfs: return pd.DataFrame()
    df_raw = pd.concat(dfs, ignore_index=True)
    filas = []
    col_chasis = next((c for c in df_raw.columns if 'CHASIS' in c or 'VIN' in c), None)
    
    for _, row in df_raw.iterrows():
        f_fin = parsear_fecha_español(row.get('FECHA_PROMESA_I', ''))
        f_fin_disp = f_fin.date() if f_fin else None
        if not f_fin: f_fin = datetime.now() + timedelta(days=3650) 
        
        mes_hist = f_fin.strftime('%Y-%m') if f_fin.year < 2030 else "SIN FECHA"
        if 'MES' in row and pd.notna(row['MES']):
            mes_str = str(row['MES']).strip().lower()
            for m_name, m_num in MESES_ES.items():
                if m_name in mes_str:
                    mes_hist = f"{datetime.now().year}-{m_num:02d}"
                    break

        f_ingreso = parsear_fecha_español(row.get('FECHA_INGRESO_TALLER', ''))
        f_ticket = parsear_fecha_español(row.get('FECHA_TICKET', ''))
        
        def limpiar_num(val):
            v = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
            try: return float(re.findall(r"[-+]?\d*\.\d+|\d+", v)[0]) if re.findall(r"[-+]?\d*\.\d+|\d+", v) else 0.0
            except: return 0.0

        panos = limpiar_num(row.get('PAÑOS', 0))
        dias_rep = limpiar_num(row.get('DIAS_TRABAJO', 0))
        precio_val = limpiar_num(row.get('PRECIO', 0))
        costo_val = limpiar_num(row.get('COSTO', 0))
        
        estado_fac = str(row.get('ESTADO_FAC', '')).replace('.', '').strip().upper()
        estado = str(row.get('ESTADO_TALLER', '')).replace('nan', '').strip().upper() or "SIN ESTADO"
        cliente = str(row.get('EMPRESA_TALLER', 'PARTICULAR')).replace('nan', '').strip().upper() or "PARTICULAR"
        asesor = str(row.get('ASESOR', '')).strip().upper()
        if asesor == 'NAN' or not asesor: asesor = "SIN ASIGNAR"
        fase = str(row.get('FASE_TALLER', '')).replace('nan', '').strip().upper()
        if not fase: fase = "SIN FASE ASIGNADA"

        filas.append({
            'Grupo': row.get('GRUPO_ORIGEN'), 'Asesor': asesor, 'Cliente': cliente,
            'Patente': str(row.get('PATENTE', '')), 'Vehiculo': str(row.get('VEHICULO', '')), 
            'Chasis': str(row.get(col_chasis, '')).upper() if col_chasis else "",
            'Inicio': f_fin - timedelta(days=max(1, int(panos))), 'Fin': f_fin, 'Fecha_Promesa_Disp': f_fin_disp, 
            'Fecha_Ingreso': f_ingreso.date() if f_ingreso else None, 'Fecha_Ticket': f_ticket.date() if f_ticket else None,
            'Hora_Entrega': str(row.get('HORA_ENTREGA', '')).replace('nan', '').strip(),
            'Mes_Hist': mes_hist, 'Paños': panos, 'Dias_Reparacion': dias_rep, 'Tipo_ABC': clasificar_abc(panos),
            'Estado_Fac': estado_fac, 'Estado_Taller': estado, 'Fase_Taller': fase, 
            'Precio': precio_val, 'Costo': costo_val,
            'Observaciones': str(row.get('OBSERVACIONES_TALLER', '')).replace('nan', '').strip()
        })
    return pd.DataFrame(filas)

# --- MEMORIA Y CARGA DE DATOS ---
if 'memoria_turnos_v12' not in st.session_state: st.session_state.memoria_turnos_v12 = obtener_turnos()
if 'entregas_confirmadas' not in st.session_state: st.session_state.entregas_confirmadas = []

df = obtener_datos_maestros()
df_turnos_display = st.session_state.memoria_turnos_v12.copy()
df_completo = df.copy() 

# ---------------------------------------------------------
# LECTURA DINÁMICA DE ASESORES Y CLIENTES
# ---------------------------------------------------------
if not df.empty:
    asesores_unicos = [str(a).strip().upper() for a in df['Asesor'].unique() if pd.notna(a) and str(a).strip().upper() != "SIN ASIGNAR"]
    ASESORES_LISTA = ["SIN ASIGNAR"] + sorted(list(set(asesores_unicos)))
    
    clientes_unicos = [str(c).strip().upper() for c in df['Cliente'].unique() if pd.notna(c)]
    CLIENTES_LISTA = sorted(list(set(clientes_unicos)))
    if "PARTICULAR" not in CLIENTES_LISTA: CLIENTES_LISTA.append("PARTICULAR")
else:
    ASESORES_LISTA = ["SIN ASIGNAR"]
    CLIENTES_LISTA = ["PARTICULAR"]

hoy = datetime.today()
hoy_ym = hoy.strftime('%Y-%m')

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.markdown("### 🔍 Buscador Rápido")
    busqueda_global = st.text_input("Dominio o Chasis", placeholder="Ej: AB123CD")
    st.caption("Filtra tablas y muestra un resumen.")
    contenedor_resultados_busqueda = st.container()
    st.divider()

    st.markdown("### 📅 Filtro Mensual")
    meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    m1 = df[df['Mes_Hist'] != 'SIN FECHA']['Mes_Hist'].dropna().unique().tolist()
    m2 = df_turnos_display['Fecha'].dropna().apply(lambda x: x.strftime('%Y-%m') if pd.notna(x) else None).dropna().unique().tolist()
    todos_meses_disp = sorted(list(set(m1 + m2)), reverse=True)
    
    opciones_meses = ["🗓️ MES ACTUAL", "♾️ TODOS"]
    mapa_meses = {}
    for m in todos_meses_disp:
        try:
            y, mo = m.split('-')
            nombre = f"{meses_nombres[int(mo)-1]} {y}"
            opciones_meses.append(nombre)
            mapa_meses[nombre] = m
        except: pass
        
    mes_seleccionado_label = st.selectbox("Período de Análisis", opciones_meses)
    mes_filtro = hoy_ym if mes_seleccionado_label == "🗓️ MES ACTUAL" else "TODOS" if mes_seleccionado_label == "♾️ TODOS" else mapa_meses.get(mes_seleccionado_label, "TODOS")
    st.caption("Aplica a Turnos, Taller y Facturación. El Histórico se mantiene global.")
    st.divider()
    
    st.markdown("### ⚙️ Sistema")
    if st.button("🔄 Forzar Actualización", use_container_width=True):
        st.cache_data.clear()
        if 'memoria_turnos_v12' in st.session_state: del st.session_state['memoria_turnos_v12']
        st.success("¡Datos actualizados!"); time.sleep(0.5); st.rerun()

# --- APLICAR FILTROS ---
if mes_filtro != "TODOS":
    df = df[(df['Mes_Hist'] == mes_filtro) | (df['Mes_Hist'] == 'SIN FECHA')]
    año_filtro, mes_num_filtro = map(int, mes_filtro.split('-'))
else:
    año_filtro, mes_num_filtro = hoy.year, hoy.month

DIAS_HABILES_MES = dias_habiles_del_mes(año_filtro, mes_num_filtro)
CAPACIDAD_DIARIA_TALLER = OBJETIVO_MENSUAL_PANOS / DIAS_HABILES_MES
CAPACIDAD_DIARIA_GRUPO = CAPACIDAD_DIARIA_TALLER 
dias_restantes_calc = dias_habiles_restantes_mes(año_filtro, mes_num_filtro)

if busqueda_global:
    termino = busqueda_global.upper().strip()
    if not df.empty:
        if 'Chasis' not in df.columns: df['Chasis'] = ""
        df = df[(df['Patente'].str.contains(termino, na=False)) | (df['Chasis'].str.contains(termino, na=False))]
                
    if not df_turnos_display.empty:
        if 'Chasis' not in df_turnos_display.columns: df_turnos_display['Chasis'] = ""
        df_turnos_display = df_turnos_display[(df_turnos_display['Patente'].str.contains(termino, na=False)) | (df_turnos_display['Chasis'].str.contains(termino, na=False))]
    
    with contenedor_resultados_busqueda:
        st.markdown("### 📋 Resumen")
        if not df.empty:
            for _, row in df.head(5).iterrows():
                f_prom = row.get('Fecha_Promesa_Disp')
                fecha_str = f_prom.strftime('%d/%m/%Y') if pd.notna(f_prom) else "Sin Fecha"
                estado_taller = str(row.get('Estado_Taller', ''))
                color_borde = "#28a745" if "ENTREGADO" in estado_taller else "#ffc107" if "PROCESO" in estado_taller else "#dc3545" if "DETENIDO" in estado_taller else "#17a2b8" if "TERM" in estado_taller else "#6c757d"
                st.markdown(f"<div style='background-color: white; border: 1px solid #dee2e6; padding: 10px; border-radius: 8px; border-left: 6px solid {color_borde}; margin-bottom: 10px; font-size: 0.85em;'><div style='font-size: 1.1em; font-weight: bold; color: #00235d;'>🚗 {row['Patente']} - {str(row['Vehiculo'])[:12]}</div><strong>🏷️ Estado:</strong> {estado_taller}<br><strong>👔 Asesor:</strong> {row['Asesor']}<br><strong>📅 Entrega:</strong> <span style='color: #d32f2f; font-weight: bold;'>{fecha_str}</span></div>", unsafe_allow_html=True)
        else: st.warning("No encontrado.")

recomendaciones_grupos = {}
if not df.empty:
    df_en_proceso_global = df[df['Estado_Taller'].str.contains("PROCESO", na=False)]
    if not df_en_proceso_global.empty:
        resumen = df_en_proceso_global.groupby('Grupo')['Paños'].sum().reset_index()
        for _, row in resumen.iterrows():
            recomendaciones_grupos[row['Grupo']] = obtener_proxima_fecha_libre(row['Paños'] / CAPACIDAD_DIARIA_GRUPO)

tab_turnos, tab_prog, tab_portal, tab_fac, tab_kpi, tab_hist = st.tabs(["📋 Turnero y Entregas", "🛠️ Programación del Taller", "🏢 Seguimiento Empresas", "💰 Facturación", "📊 KPIs", "📅 Históricos"])

# ==========================================
# PESTAÑA 1: TURNERO Y ENTREGAS
# ==========================================
with tab_turnos:
    if recomendaciones_grupos and not busqueda_global:
        st.info("**📅 Asistente de Turnos:**\n" + " | ".join([f"**{g}**: libre desde el {f}" for g, f in recomendaciones_grupos.items()]))
    
    st.markdown("<h4 style='color: #00235d; margin-top: 10px;'>🔍 Filtros de Visualización</h4>", unsafe_allow_html=True)
    col_fecha, col_asesor, col_add = st.columns([1, 1, 2])
    
    with col_fecha:
        if mes_filtro != "TODOS":
            primer_dia = date(año_filtro, mes_num_filtro, 1)
            _, ult_dia_int = calendar.monthrange(año_filtro, mes_num_filtro)
            ultimo_dia = date(año_filtro, mes_num_filtro, ult_dia_int)
            rango_default = (hoy.date(), hoy.date()) if mes_seleccionado_label == "🗓️ MES ACTUAL" else (primer_dia, ultimo_dia)
        else: rango_default = (hoy.date(), hoy.date())
            
        fechas_seleccionadas = st.date_input("📅 Rango de Fechas", value=rango_default, format="DD/MM/YYYY")
        f_inicio = fechas_seleccionadas[0] if isinstance(fechas_seleccionadas, tuple) and len(fechas_seleccionadas) > 0 else fechas_seleccionadas
        f_fin = fechas_seleccionadas[1] if isinstance(fechas_seleccionadas, tuple) and len(fechas_seleccionadas) == 2 else f_inicio
        
    with col_asesor: asesor_filtro = st.selectbox("👔 Filtrar por Asesor", ["TODOS"] + ASESORES_LISTA)
        
    with col_add:
        with st.expander("➕ Ingresar vehículo SIN TURNO (Walk-in)"):
            if "procesando_envio" not in st.session_state: st.session_state.procesando_envio = False
            with st.form("form_sin_turno", clear_on_submit=True):
                c_pat, c_veh, c_cli = st.columns(3)
                nueva_patente = c_pat.text_input("Patente *")
                nuevo_vehiculo = c_veh.text_input("Vehículo *")
                nuevo_cliente = c_cli.selectbox("Cliente", CLIENTES_LISTA)
                
                c_seg, c_pre, c_pan = st.columns(3)
                nuevo_seguro = c_seg.text_input("Seguro")
                nuevo_precio = c_pre.text_input("Precio ($)")
                nuevo_panos = c_pan.text_input("Paños (Ej: 1.5)")
                
                c_ase, c_tic, c_tie = st.columns(3)
                nuevo_asesor = c_ase.selectbox("Asesor", ASESORES_LISTA, index=0)
                nuevo_ticket = c_tic.text_input("N° Ticket")
                nuevo_tiempo = c_tie.text_input("Tiempo Entrega (Días)")
                
                nueva_obs = st.text_input("Observaciones (Opcional)")
                st.write("---")
                c_chk1, c_chk2, c_ref = st.columns([1, 1, 2])
                val_recibido_bool = c_chk1.checkbox("✅ ¿Vehículo Recibido?")
                val_foto_bool = c_chk2.checkbox("📸 ¿Fotos tomadas?")
                nueva_referencia = c_ref.text_input("N° Referencia / OR")

                enviado = st.form_submit_button("Agregar al Turnero y Guardar")
                if enviado:
                    if not st.session_state.procesando_envio:
                        if nueva_patente and nuevo_vehiculo:
                            st.session_state.procesando_envio = True
                            if hoja is not None:
                                try:
                                    # Mapeo a las 17 columnas de Salta
                                    nueva_fila = [
                                        "N", str(f_inicio.strftime('%d/%m/%Y')), "-", str(nuevo_vehiculo).upper(), str(nueva_patente).upper(), str(nuevo_asesor), str(nuevo_precio), str(nuevo_panos), str(nueva_obs), str(nuevo_tiempo), str(nuevo_cliente).upper(), str(nuevo_seguro).upper(), str(nuevo_ticket), "SI" if val_recibido_bool else "", "SI" if val_foto_bool else "", str(nueva_referencia), ""
                                    ]
                                    hoja.append_row(nueva_fila)
                                    st.cache_data.clear()
                                    if 'memoria_turnos_v12' in st.session_state: del st.session_state['memoria_turnos_v12']
                                    st.success(f"¡Vehículo {nueva_patente.upper()} guardado exitosamente!"); time.sleep(1); st.session_state.procesando_envio = False; st.rerun()
                                except Exception as e:
                                    st.session_state.procesando_envio = False
                                    st.error(f"Error al guardar: {e}")
                            else: st.error("No se detecta la pestaña TURNOS en el Sheets.")
                        else: st.warning("Por favor completá Patente y Vehículo.")
                    else: st.error("Procesando...")

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("<h2 style='color: #00235d; margin-top: 0;'>📥 1. INGRESOS: Recepción de Vehículos</h2>", unsafe_allow_html=True)
        mask = (df_turnos_display['Fecha'] >= f_inicio) & (df_turnos_display['Fecha'] <= f_fin)
        df_rango = df_turnos_display[mask].copy()
        if asesor_filtro != "TODOS": df_rango = df_rango[df_rango['Asesor'] == asesor_filtro]

        if df_rango.empty: st.info("No hay turnos para los filtros seleccionados.")
        else:
            df_activos = df_rango[df_rango['Cancelado'] == False]
            mascara_recibidos = ((df_activos['Ticket'].str.strip() != "") | (df_activos['Referencia'].str.strip() != "")) & (df_activos['Recibido'] == True) & (df_activos['Fotos'] == True)
            df_pendientes = df_activos[~mascara_recibidos].sort_values(['Fecha', 'Hora', 'Asesor'])
            df_recibidos = df_activos[mascara_recibidos].sort_values(['Fecha', 'Hora', 'Asesor'])

            st.write("#### ⏱️ Turnos Pendientes")
            if not df_pendientes.empty:
                df_prog = df_pendientes[df_pendientes['Tipo'] == '📅 PROGRAMADO']
                df_sin = df_pendientes[df_pendientes['Tipo'] == '🚶‍♂️ SIN TURNO']
                edited_prog, edited_sin = pd.DataFrame(), pd.DataFrame()
                
                conf_columnas = {
                    "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"), 
                    "Asesor": st.column_config.SelectboxColumn("Asesor", options=ASESORES_LISTA), 
                    "Ticket": st.column_config.TextColumn("🎫 Ticket", max_chars=15), 
                    "Observaciones": st.column_config.TextColumn("💬 Observaciones"), 
                    "Recibido": st.column_config.CheckboxColumn("✅ Recibido", default=False), 
                    "Fotos": st.column_config.CheckboxColumn("📸 Fotos", default=False), 
                    "Referencia": st.column_config.TextColumn("🏷️ Ref.", max_chars=15), 
                    "Cancelado": st.column_config.CheckboxColumn("❌ Cancelar", default=False),
                    "Motivo_Cancelacion": st.column_config.TextColumn("📝 Motivo (Col Q)")
                }
                orden_columnas = ['Fecha', 'Hora', 'Patente', 'Vehiculo', 'Cliente', 'Asesor', 'Ticket', 'Observaciones', 'Recibido', 'Fotos', 'Referencia', 'Cancelado', 'Motivo_Cancelacion']
                
                if not df_prog.empty: edited_prog = st.data_editor(df_prog[orden_columnas], column_config=conf_columnas, hide_index=True, use_container_width=True, key="editor_prog")
                if not df_sin.empty: edited_sin = st.data_editor(df_sin[orden_columnas + ['Eliminar']], column_config=conf_columnas, hide_index=True, use_container_width=True, key="editor_sin")

                if st.button("💾 Guardar Cambios Pendientes"):
                    with st.spinner("Sincronizando..."):
                        patentes_sheet_raw = hoja.col_values(5) if hoja else []
                        patentes_limpias = ["".join(str(p).split()).upper() for p in patentes_sheet_raw]
                        
                        def procesar_guardado_fila(row, row_orig):
                            if (row['Fecha'] != row_orig['Fecha'] or row['Recibido'] != row_orig['Recibido'] or row['Fotos'] != row_orig['Fotos'] or str(row['Ticket']).strip() != str(row_orig['Ticket']).strip() or str(row['Referencia']).strip() != str(row_orig['Referencia']).strip() or row['Asesor'] != row_orig['Asesor'] or row['Cancelado'] != row_orig['Cancelado'] or str(row.get('Motivo_Cancelacion','')) != str(row_orig.get('Motivo_Cancelacion','')) or str(row.get('Observaciones','')) != str(row_orig.get('Observaciones',''))):
                                patente_buscada = "".join(str(row['Patente']).split()).upper()
                                if hoja and patente_buscada in patentes_limpias:
                                    fila_sheet = len(patentes_limpias) - patentes_limpias[::-1].index(patente_buscada)
                                    try:
                                        hoja.update_acell(f'B{fila_sheet}', row['Fecha'].strftime('%d/%m/%Y'))
                                        hoja.update_acell(f'F{fila_sheet}', row['Asesor'])
                                        hoja.update_acell(f'I{fila_sheet}', str(row['Observaciones']) if pd.notna(row['Observaciones']) else "")
                                        hoja.update_acell(f'M{fila_sheet}', str(row['Ticket']) if pd.notna(row['Ticket']) else "")
                                        hoja.update_acell(f'N{fila_sheet}', "SI" if row['Recibido'] else "")
                                        hoja.update_acell(f'O{fila_sheet}', "SI" if row['Fotos'] else "")
                                        hoja.update_acell(f'P{fila_sheet}', str(row['Referencia']) if pd.notna(row['Referencia']) else "")
                                        if row['Cancelado']:
                                            hoja.update_acell(f'A{fila_sheet}', "C")
                                            hoja.update_acell(f'Q{fila_sheet}', str(row['Motivo_Cancelacion']) if pd.notna(row['Motivo_Cancelacion']) else "")
                                        elif row_orig['Cancelado'] and not row['Cancelado']:
                                            hoja.update_acell(f'A{fila_sheet}', "N" if row_orig['Tipo'] == '🚶‍♂️ SIN TURNO' else "SI") 
                                            hoja.update_acell(f'Q{fila_sheet}', "")
                                    except Exception as e: st.error(f"Error {row['Patente']}: {e}")

                        if not edited_prog.empty:
                            for idx, row in edited_prog.iterrows(): procesar_guardado_fila(row, df_prog.loc[idx])
                        if not edited_sin.empty:
                            for idx, row in edited_sin.iterrows():
                                if row.get('Eliminar', False): 
                                    p_b = "".join(str(row['Patente']).split()).upper()
                                    if hoja and p_b in patentes_limpias:
                                        try: hoja.delete_rows(len(patentes_limpias) - patentes_limpias[::-1].index(p_b))
                                        except: pass
                                else: procesar_guardado_fila(row, df_sin.loc[idx])
                                        
                        st.cache_data.clear()
                        for k in [k for k in st.session_state.keys() if k.startswith('memoria')]: del st.session_state[k]
                        st.success("¡Sincronización completa!"); time.sleep(1); st.rerun()

            st.write("#### 🏁 Turnos Completados (Ya Recibidos)")
            if not df_recibidos.empty:
                edited_recibidos = st.data_editor(df_recibidos[['Tipo', 'Fecha', 'Patente', 'Vehiculo', 'Cliente', 'Asesor', 'Recibido', 'Fotos', 'Ticket', 'Referencia']], hide_index=True, use_container_width=True, disabled=['Tipo', 'Fecha', 'Patente', 'Vehiculo', 'Cliente', 'Asesor'], key="editor_recibidos")
                if st.button("💾 Guardar Correcciones"):
                    with st.spinner("Actualizando..."):
                        patentes_limpias = ["".join(str(p).split()).upper() for p in (hoja.col_values(5) if hoja else [])]
                        for idx, row in edited_recibidos.iterrows():
                            row_orig = df_recibidos.loc[idx]
                            if row['Recibido'] != row_orig['Recibido'] or row['Fotos'] != row_orig['Fotos'] or str(row['Ticket']).strip() != str(row_orig['Ticket']).strip() or str(row['Referencia']).strip() != str(row_orig['Referencia']).strip():
                                patente_buscada = "".join(str(row['Patente']).split()).upper()
                                if hoja and patente_buscada in patentes_limpias:
                                    fila_sheet = len(patentes_limpias) - patentes_limpias[::-1].index(patente_buscada)
                                    try:
                                        hoja.update_acell(f'N{fila_sheet}', "SI" if row['Recibido'] else "")
                                        hoja.update_acell(f'O{fila_sheet}', "SI" if row['Fotos'] else "")
                                        hoja.update_acell(f'M{fila_sheet}', str(row['Ticket']) if pd.notna(row['Ticket']) else "")
                                        hoja.update_acell(f'P{fila_sheet}', str(row['Referencia']) if pd.notna(row['Referencia']) else "")
                                    except: pass
                        st.cache_data.clear(); st.success("¡Guardado!"); time.sleep(1); st.rerun()

    with st.container(border=True):
        st.markdown("<h2 style='color: #1e7e34; margin-top: 0;'>📤 2. SALIDAS: Agenda de Entregas</h2>", unsafe_allow_html=True)
        if not df.empty:
            df_no_entregados = df[~df['Estado_Taller'].str.contains("ENTREGADO", na=False)].copy()
            df_no_entregados = df_no_entregados[~df_no_entregados['Patente'].isin(st.session_state.entregas_confirmadas)]
            df_no_entregados['Entregado_OK'] = False
            
            entregas_rango = df_no_entregados[(df_no_entregados['Fecha_Promesa_Disp'] >= f_inicio) & (df_no_entregados['Fecha_Promesa_Disp'] <= f_fin)].copy()
            entregas_atrasadas = df_no_entregados[(df_no_entregados['Fecha_Promesa_Disp'].notna()) & (df_no_entregados['Fecha_Promesa_Disp'] < hoy.date())].copy()
            
            if asesor_filtro != "TODOS":
                entregas_rango = entregas_rango[entregas_rango['Asesor'] == asesor_filtro]
                entregas_atrasadas = entregas_atrasadas[entregas_atrasadas['Asesor'] == asesor_filtro]
            
            edit_rango_df, edit_atra = pd.DataFrame(), pd.DataFrame()
            
            st.markdown("#### 🔴 Entregas Atrasadas (Vencidas)")
            if not entregas_atrasadas.empty:
                entregas_atrasadas = entregas_atrasadas.sort_values(by='Fecha_Promesa_Disp', ascending=True)
                entregas_atrasadas['Fecha Prom.'] = entregas_atrasadas['Fecha_Promesa_Disp'].apply(lambda x: x.strftime('%d/%m/%Y'))
                entregas_atrasadas['Demora (Días)'] = entregas_atrasadas['Fecha_Promesa_Disp'].apply(lambda x: (hoy.date() - x).days if pd.notna(x) else 0)
                edit_atra = st.data_editor(entregas_atrasadas[['Entregado_OK', 'Demora (Días)', 'Fecha Prom.', 'Patente', 'Vehiculo', 'Asesor', 'Estado_Taller', 'Precio', 'Observaciones']], hide_index=True, use_container_width=True, column_config={"Entregado_OK": st.column_config.CheckboxColumn("✅ Listo", default=False), "Demora (Días)": st.column_config.NumberColumn("⚠️ Demora", format="%d días"), "Fecha Prom.": st.column_config.TextColumn("📅 Venció", disabled=True), "Patente": st.column_config.TextColumn("Patente", disabled=True), "Vehiculo": st.column_config.TextColumn("Vehículo", disabled=True), "Asesor": st.column_config.TextColumn("Asesor", disabled=True), "Estado_Taller": st.column_config.TextColumn("Estado", disabled=True), "Precio": st.column_config.NumberColumn("Monto ($)", format="$ %d", disabled=True), "Observaciones": st.column_config.TextColumn("Observaciones", disabled=True)}, key="editor_entregas_atra")
            else: st.success("No hay vehículos atrasados.")
                
            st.divider()
            
            titulo_rango = f"HOY ({f_inicio.strftime('%d/%m')})" if f_inicio == hoy.date() and f_inicio == f_fin else f"del {f_inicio.strftime('%d/%m')} al {f_fin.strftime('%d/%m')}"
            st.markdown(f"#### 🟢 Entregas Programadas {titulo_rango}")
            if not entregas_rango.empty:
                entregas_rango['Fecha Prom.'] = entregas_rango['Fecha_Promesa_Disp'].apply(lambda x: x.strftime('%d/%m') if pd.notna(x) else "")
                df_g_rango = entregas_rango.sort_values(by=['Fecha_Promesa_Disp', 'Hora_Entrega'])
                edit_rango_df = st.data_editor(df_g_rango[['Entregado_OK', 'Fecha Prom.', 'Hora_Entrega', 'Patente', 'Vehiculo', 'Asesor', 'Precio', 'Observaciones']], hide_index=True, use_container_width=True, column_config={"Entregado_OK": st.column_config.CheckboxColumn("✅ Listo", default=False), "Fecha Prom.": st.column_config.TextColumn("📅 Día", disabled=True), "Hora_Entrega": st.column_config.TextColumn("⌚ Hora", disabled=True), "Patente": st.column_config.TextColumn("Patente", disabled=True), "Vehiculo": st.column_config.TextColumn("Vehículo", disabled=True), "Asesor": st.column_config.TextColumn("Asesor", disabled=True), "Precio": st.column_config.NumberColumn("Monto ($)", format="$ %d", disabled=True), "Observaciones": st.column_config.TextColumn("Observaciones", disabled=True)}, key="editor_entregas_rango_unica")
            else: st.info("No hay entregas pendientes para el rango seleccionado.")
                    
            if not edit_rango_df.empty or not edit_atra.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Confirmar Salida de Vehículos Seleccionados", use_container_width=True):
                    nuevas_confirmadas = []
                    if not edit_rango_df.empty: nuevas_confirmadas.extend(edit_rango_df[edit_rango_df['Entregado_OK'] == True]['Patente'].tolist())
                    if not edit_atra.empty: nuevas_confirmadas.extend(edit_atra[edit_atra['Entregado_OK'] == True]['Patente'].tolist())
                    if nuevas_confirmadas:
                        st.session_state.entregas_confirmadas.extend(nuevas_confirmadas)
                        st.success(f"Se registraron {len(nuevas_confirmadas)} entregas localmente."); time.sleep(1); st.rerun()
                    else: st.warning("No marcaste ningún vehículo.")

# ==========================================
# PESTAÑA 2: PROGRAMACIÓN Y KANBAN
# ==========================================
with tab_prog:
    st.subheader("🛠️ Programación y Flujo de Trabajo")
    if not df.empty:
        col_filtro, _ = st.columns([1, 2])
        with col_filtro: asesor_filtro_prog = st.selectbox("👔 Filtrar por Asesor", ["TODOS"] + ASESORES_LISTA, key="filtro_asesor_prog")
            
        df_prog_filtrado = df.copy()
        if asesor_filtro_prog != "TODOS":
            nombre_corto = asesor_filtro_prog.split()[0].upper()
            df_prog_filtrado = df_prog_filtrado[df_prog_filtrado['Asesor'].str.contains(nombre_corto, case=False, na=False)]

        df_en_proceso = df_prog_filtrado[df_prog_filtrado['Estado_Taller'].str.contains("PROCESO", na=False)]
        
        st.markdown(f"### 🚥 Termómetro de Capacidad (Mes de {DIAS_HABILES_MES} días hábiles)")
        if not df_en_proceso.empty:
            resumen_capacidad = df_en_proceso.groupby('Grupo').agg(Autos=('Patente', 'count'), Panos_Activos=('Paños', 'sum')).reset_index()
            resumen_capacidad['Dias_Carga_Real'] = resumen_capacidad['Panos_Activos'] / CAPACIDAD_DIARIA_GRUPO
            
            cols_cap = st.columns(len(resumen_capacidad))
            for i, row in resumen_capacidad.reset_index(drop=True).iterrows():
                with cols_cap[i]:
                    dias_reales = row['Dias_Carga_Real']
                    fecha_libre = obtener_proxima_fecha_libre(dias_reales)
                    color_dias = "#28a745" if dias_reales < 4 else "#ffc107" if dias_reales < 7 else "#dc3545"
                    st.markdown(f"""
                    <div style='background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                        <h4 style='color: #00235d; margin-top: 0;'>{row['Grupo']}</h4>
                        <h1 style='color: {color_dias}; margin: 10px 0;'>{dias_reales:.1f} Días</h1>
                        <p style='color: #17a2b8; font-weight: bold; font-size: 1.1em; margin-bottom: 0;'>📅 Libre aprox: {fecha_libre}</p>
                        <hr style='margin: 10px 0;'><div style='display: flex; justify-content: space-around;'><span>🚗 {row['Autos']} autos</span><span>📦 {row['Panos_Activos']:.1f} paños</span></div>
                    </div>
                    """, unsafe_allow_html=True)
        else: st.info("No hay vehículos en proceso.")

        st.divider()

        st.markdown("## 📑 Listado de Vehículos en Taller por Estado")
        estados_map = [
            ("⏳ EN PROCESO", "PROCESO"), 
            ("⛔ DETENIDOS", "DETENIDO"), 
            ("⚠️ TERMINADOS (Pendiente Facturar)", "TERM PEND FACT"),
            ("⏳ TERMINADOS (Pendiente Entregar)", "TERM PEND ENTREG"),
            ("🚚 ENTREGADOS (Pendiente Facturar)", "ENTREGADO PEND FACT"),
            ("🏁 ENTREGADOS (Listos y Facturados)", "ENTREGADO_FINAL")
        ]
        
        for titulo, match_key in estados_map:
            if "DETENIDO" in match_key: st.error(f"#### {titulo}")
            else: st.markdown(f"#### {titulo}")
            
            d_g = df_prog_filtrado.copy()
            if match_key == "ENTREGADO_FINAL":
                d_e = d_g[(d_g['Estado_Taller'].str.contains("ENTREGADO", na=False)) & (~d_g['Estado_Taller'].str.contains("PEND", na=False))].copy()
            else:
                d_e = d_g[d_g['Estado_Taller'].str.contains(match_key, na=False)].copy()
                
            if not d_e.empty:
                d_e = d_e.sort_values(by='Fin', ascending=True, na_position='last')
                d_e['F. Ingreso'] = d_e['Fecha_Ingreso'].apply(lambda x: x.strftime('%d/%m') if pd.notna(x) else "")
                d_e['1ra Promesa'] = d_e['Fecha_Ticket'].apply(lambda x: x.strftime('%d/%m') if pd.notna(x) else "")
                d_e['F. Entrega'] = d_e['Fecha_Promesa_Disp'].apply(lambda x: x.strftime('%d/%m') if pd.notna(x) else "")
                
                if "TERM" in match_key or "ENTREGADO" in match_key:
                    cols_to_show = ['F. Ingreso', '1ra Promesa', 'F. Entrega', 'Hora_Entrega', 'Patente', 'Vehiculo', 'Asesor', 'Paños', 'Precio', 'Observaciones']
                else:
                    cols_to_show = ['F. Ingreso', '1ra Promesa', 'F. Entrega', 'Hora_Entrega', 'Patente', 'Vehiculo', 'Asesor', 'Paños', 'Observaciones']
                    
                st.dataframe(d_e[cols_to_show], hide_index=True, use_container_width=True, column_config={"Hora_Entrega": st.column_config.TextColumn("Hs"), "Precio": st.column_config.NumberColumn("Monto ($)", format="$ %d"), "Observaciones": st.column_config.TextColumn("Observaciones", width="medium")})
            else: st.caption("Sin vehículos en este estado.")
            st.markdown("<br>", unsafe_allow_html=True)

        st.divider()

        st.markdown("### 📋 Tablero Kanban - Taller Salta")
        df_kanban = df_prog_filtrado[df_prog_filtrado['Estado_Taller'].str.contains("PROCESO|DETENIDO", na=False)].copy()
        df_kanban.loc[df_kanban['Estado_Taller'].str.contains("DETENIDO", na=False), 'Fase_Taller'] = "⛔ DETENIDOS"
        
        orden_ideal = ["SIN FASE ASIGNADA", "CHAPA", "PREPARACION", "PINTURA", "ARMADO", "PULIDO", "⛔ DETENIDOS"]
        
        cols_kanban = st.columns(len(orden_ideal))
        for idx, fase in enumerate(orden_ideal):
            with cols_kanban[idx]:
                st.markdown(f"<div class='kanban-col'><h5 style='text-align:center; color:#00235d; margin: 0; font-size: 0.85rem;'>{fase}</h5></div>", unsafe_allow_html=True)
                
                if fase == "SIN FASE ASIGNADA": df_fase = df_kanban[(df_kanban['Fase_Taller'] == "") | (df_kanban['Fase_Taller'].isna()) | (df_kanban['Fase_Taller'] == "SIN FASE ASIGNADA")]
                else: df_fase = df_kanban[df_kanban['Fase_Taller'].str.contains(fase[:4], na=False, case=False)]
                
                if not df_fase.empty:
                    for _, row in df_fase.iterrows():
                        f_prom = row.get('Fecha_Promesa_Disp')
                        if fase == "⛔ DETENIDOS": color_borde, circulo, texto_fecha = "#6c757d", "⚪", "Detenido"
                        else:
                            if pd.isna(f_prom) or not f_prom: color_borde, circulo, texto_fecha = "#17a2b8", "🔵", "Sin fecha"
                            elif f_prom < hoy.date(): color_borde, circulo, texto_fecha = "#dc3545", "🔴", f_prom.strftime('%d/%m')
                            elif f_prom == hoy.date(): color_borde, circulo, texto_fecha = "#ffc107", "🟡", f_prom.strftime('%d/%m')
                            else: color_borde, circulo, texto_fecha = "#28a745", "🟢", f_prom.strftime('%d/%m')
                            
                        novedad_html = f"<div style='margin-top: 5px; font-size: 0.85em; color: #721c24; background-color: #f8d7da; padding: 4px; border-radius: 4px;'><strong>Novedad:</strong> {str(row['Observaciones'])}</div>" if fase == "⛔ DETENIDOS" and str(row.get('Observaciones', '')).strip() != "" and str(row.get('Observaciones', '')).lower() != "nan" else ""
                        
                        st.markdown(f"""
                        <div style='background: white; padding: 8px; margin-top: 8px; border-radius: 5px; border-left: 5px solid {color_borde}; box-shadow: 1px 1px 3px rgba(0,0,0,0.1); font-size: 0.9em;'>
                            <div style='display: flex; justify-content: space-between;'><strong>{row['Patente']}</strong><span>{circulo} {texto_fecha}</span></div>
                            <span style='font-size: 0.85em;'>{row['Vehiculo'][:15]}</span><br>
                            <span style='font-size: 0.8em; color: gray;'>📦 {row['Paños']} p. | {row['Asesor'].split()[0] if row['Asesor'] else 'N/A'}</span>
                            {novedad_html}
                        </div>
                        """, unsafe_allow_html=True)

# ==========================================
# PESTAÑA 3: PORTAL EMPRESAS 
# ==========================================
with tab_portal:
    if not df.empty:
        st.subheader("🏢 Seguimiento de Unidades: Empresas del Grupo")
        df_grupo = df[df['Cliente'].str.contains('SOL|LUX|CIEL', case=False, na=False)].copy()
        if not df_grupo.empty:
            c_filtro, _ = st.columns([1, 2])
            with c_filtro: empresa_filtro = st.selectbox("Seleccionar Empresa", ["TODAS", "AUTOSOL", "AUTOLUX", "CIEL / AUTOCIEL"])
            df_vista_emp = df_grupo.copy()
            if empresa_filtro == "AUTOSOL": df_vista_emp = df_vista_emp[df_vista_emp['Cliente'].str.contains('SOL', case=False, na=False)]
            elif empresa_filtro == "AUTOLUX": df_vista_emp = df_vista_emp[df_vista_emp['Cliente'].str.contains('LUX', case=False, na=False)]
            elif empresa_filtro == "CIEL / AUTOCIEL": df_vista_emp = df_vista_emp[df_vista_emp['Cliente'].str.contains('CIEL', case=False, na=False)]
            
            df_vista_emp = df_vista_emp.sort_values(by='Fecha_Promesa_Disp', ascending=True, na_position='last')
            en_proceso = len(df_vista_emp[df_vista_emp['Estado_Taller'].str.contains("PROCESO", na=False)])
            detenidos = len(df_vista_emp[df_vista_emp['Estado_Taller'].str.contains("DETENIDO", na=False)])
            terminados = len(df_vista_emp[df_vista_emp['Estado_Taller'].str.contains("TERM", na=False)])
            
            ce1, ce2, ce3 = st.columns(3)
            ce1.markdown(f'<div class="metric-card"><div class="metric-title">En Proceso</div><div class="metric-value-number">{en_proceso}</div></div>', unsafe_allow_html=True)
            ce2.markdown(f'<div class="metric-card"><div class="metric-title">Detenidos</div><div class="metric-value-number" style="color:#dc3545;">{detenidos}</div></div>', unsafe_allow_html=True)
            ce3.markdown(f'<div class="metric-card"><div class="metric-title">Terminados (Pte. Entregar)</div><div class="metric-value-number" style="color:#28a745;">{terminados}</div></div>', unsafe_allow_html=True)
            
            st.dataframe(df_vista_emp[['Cliente', 'Patente', 'Vehiculo', 'Estado_Taller', 'Fecha_Promesa_Disp', 'Observaciones']], hide_index=True, use_container_width=True)
        else: st.info("No hay vehículos registrados para las empresas del grupo.")

# ==========================================
# PESTAÑA 4: FACTURACIÓN
# ==========================================
with tab_fac:
    if not df.empty:
        st.subheader("💰 Análisis de Facturación y Objetivos")
        
        df_analisis = df.copy()
        def clasificar_estado(row):
            est_taller = str(row['Estado_Taller']).upper()
            est_fac = str(row['Estado_Fac']).upper()
            if 'DETENIDO' in est_taller: return 'En Taller (Otros)' 
            if est_fac == 'FAC': return 'Facturado (FAC)'
            if est_fac == 'SI': return 'Aprobado (SI)'
            return 'En Taller (Otros)'
            
        df_analisis['Estado_Resumen'] = df_analisis.apply(clasificar_estado, axis=1)

        df_fac = df_analisis[df_analisis['Estado_Resumen'] == 'Facturado (FAC)']
        df_si = df_analisis[df_analisis['Estado_Resumen'] == 'Aprobado (SI)']
        
        pesos_fac, panos_fac = df_fac['Precio'].sum(), df_fac['Paños'].sum()
        pesos_si, panos_si = df_si['Precio'].sum(), df_si['Paños'].sum()
        pesos_est, panos_est = pesos_fac + pesos_si, panos_fac + panos_si
        
        porcentaje_logro = min((panos_est / OBJETIVO_MENSUAL_PANOS) * 100 if OBJETIVO_MENSUAL_PANOS > 0 else 0, 100)
        
        dias_restantes = dias_restantes_calc
        panos_faltantes = max(0, OBJETIVO_MENSUAL_PANOS - panos_est)
        ritmo_diario_necesario = panos_faltantes / dias_restantes if dias_restantes > 0 else 0
        
        st.markdown("### 🎯 Control de Objetivo Mensual y Ritmo")
        c_obj1, c_obj2 = st.columns([3, 1])
        with c_obj1:
            st.progress(int(porcentaje_logro))
            st.caption(f"**Progreso del Mes:** {panos_est:.1f} paños asegurados de un objetivo de {OBJETIVO_MENSUAL_PANOS} paños.")
        with c_obj2:
            st.markdown(f"<h3 style='text-align: right; color: {'#28a745' if porcentaje_logro >= 95 else '#ffc107' if porcentaje_logro >= 75 else '#dc3545'}; margin-top: 0;'>{porcentaje_logro:.1f}%</h3>", unsafe_allow_html=True)
            
        st.info(f"⏱️ **Termómetro de Ritmo:** Faltan **{panos_faltantes:.1f} paños** y quedan **{dias_restantes} días hábiles**. Para llegar a la meta, el taller debe sacar a la calle **{ritmo_diario_necesario:.1f} paños por día**.")
            
        st.write("### 💰 Rendimiento y Proyección al Cierre")
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.markdown(f'<div class="metric-card"><div class="metric-title">Facturado Actual (FAC)</div><div class="metric-value-money">{formato_pesos(pesos_fac)}</div><div class="metric-subtitle-gray" style="font-size: 1.1rem; margin-top: 8px;">📦 {panos_fac:.1f} paños</div></div>', unsafe_allow_html=True)
        c_r2.markdown(f'<div class="metric-card"><div class="metric-title">Aprobado (SI)</div><div class="metric-value-money" style="color:#28a745;">{formato_pesos(pesos_si)}</div><div class="metric-subtitle-green" style="font-size: 1.1rem; margin-top: 8px;">📦 {panos_si:.1f} paños</div></div>', unsafe_allow_html=True)
        c_r3.markdown(f'<div class="metric-card" style="border: 2px solid #00235d; background-color: #f8f9fa;"><div class="metric-title" style="color:#00235d;">Estimado a Cierre de Mes</div><div class="metric-value-money" style="color:#00235d;">{formato_pesos(pesos_est)}</div><div class="metric-subtitle-gray" style="font-size: 1.1rem; color:#00235d; font-weight: bold; margin-top: 8px;">📦 {panos_est:.1f} paños totales</div></div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        df_tpf = df[df['Estado_Taller'].str.contains("TERM PEND FACT", na=False)]
        df_tpe = df[df['Estado_Taller'].str.contains("TERM PEND ENTREG", na=False)]
        df_epf = df[df['Estado_Taller'].str.contains("ENTREGADO PEND FACT", na=False)]

        st.write("### 🚨 Detalle de Estados Pendientes (Plata Inmovilizada)")
        c_e1, c_e2, c_e3 = st.columns(3)
        c_e1.markdown(f'<div class="metric-card"><div class="metric-title">Terminado Pend. Facturar</div><div class="metric-value-money">{formato_pesos(df_tpf["Precio"].sum())}</div><div class="metric-subtitle-red">⚠️ {df_tpf["Paños"].sum():.1f} paños físicos</div></div>', unsafe_allow_html=True)
        c_e2.markdown(f'<div class="metric-card"><div class="metric-title">Terminado Pend. Entregar</div><div class="metric-value-money">{formato_pesos(df_tpe["Precio"].sum())}</div><div class="metric-subtitle-blue">⏳ {df_tpe["Paños"].sum():.1f} paños físicos</div></div>', unsafe_allow_html=True)
        c_e3.markdown(f'<div class="metric-card"><div class="metric-title">Entregados (Pendiente Facturar)</div><div class="metric-value-money">{formato_pesos(df_epf["Precio"].sum())}</div><div class="metric-subtitle-green">🚚 {df_epf["Paños"].sum():.1f} paños físicos</div></div>', unsafe_allow_html=True)
        
        st.write("### 🔭 Radar del Mes Siguiente (Estado 'NO')")
        df_no = df_completo[df_completo['Estado_Fac'] == 'NO'].copy()
        if not df_no.empty:
            c_n1, c_n2, c_n3 = st.columns(3)
            c_n1.markdown(f'<div class="metric-card"><div class="metric-title">Autos para Próx. Mes</div><div class="metric-value-number" style="color:#6f42c1;">{df_no["Patente"].count()}</div></div>', unsafe_allow_html=True)
            c_n2.markdown(f'<div class="metric-card"><div class="metric-title">Paños Asegurados</div><div class="metric-value-number" style="color:#6f42c1;">{df_no["Paños"].sum():.1f}</div></div>', unsafe_allow_html=True)
            c_n3.markdown(f'<div class="metric-card"><div class="metric-title">Plata Proyectada</div><div class="metric-value-money" style="color:#6f42c1;">{formato_pesos(df_no["Precio"].sum())}</div></div>', unsafe_allow_html=True)
        else: st.info("No hay vehículos marcados con 'NO'.")

        if mes_filtro != "TODOS":
            st.divider()
            st.markdown("### 📈 Curva de Producción y Facturación del Mes")
            primer_dia = date(año_filtro, mes_num_filtro, 1)
            _, ult_dia = calendar.monthrange(año_filtro, mes_num_filtro)
            fechas_mes = [date(año_filtro, mes_num_filtro, d) for d in range(1, ult_dia + 1)]

            df_dias = pd.DataFrame({'Fecha': fechas_mes})
            df_dias['Es_Habil'] = df_dias['Fecha'].apply(lambda x: x.weekday() < 5 and x not in FERIADOS_ARG)
            df_habiles = df_dias[df_dias['Es_Habil']].copy()
            df_habiles['Dia_Habil_Num'] = range(1, len(df_habiles) + 1)
            df_habiles['Meta Lineal (Paños)'] = df_habiles['Dia_Habil_Num'] * CAPACIDAD_DIARIA_TALLER

            df_proyeccion = df_analisis[df_analisis['Estado_Resumen'].isin(['Facturado (FAC)', 'Aprobado (SI)'])].copy()
            
            def asignar_fecha_curva(row):
                f = row['Fecha_Promesa_Disp']
                if pd.isna(f) or f.month != mes_num_filtro or f.year != año_filtro:
                    return hoy.date() if hoy.month == mes_num_filtro else primer_dia
                return f

            df_proyeccion['Fecha_Curva'] = df_proyeccion.apply(asignar_fecha_curva, axis=1)
            df_proyeccion['Es_Hecho'] = df_proyeccion['Estado_Taller'].str.contains('ENTREGADO|TERM', na=False) | (df_proyeccion['Estado_Resumen'] == 'Facturado (FAC)')

            agrupado = df_proyeccion.groupby('Fecha_Curva').agg(Paños_Esperados=('Paños', 'sum')).reset_index()
            agrupado_hecho = df_proyeccion[df_proyeccion['Es_Hecho']].groupby('Fecha_Curva').agg(Paños_Hechos=('Paños', 'sum')).reset_index()

            df_habiles = df_habiles.merge(agrupado, left_on='Fecha', right_on='Fecha_Curva', how='left').fillna(0)
            df_habiles = df_habiles.merge(agrupado_hecho, left_on='Fecha', right_on='Fecha_Curva', how='left').fillna(0)

            df_habiles['1. Proyección Esperada (SI+FAC)'] = df_habiles['Paños_Esperados'].cumsum()
            df_habiles['2. Avance Real Hecho'] = df_habiles['Paños_Hechos'].cumsum()
            df_habiles.loc[df_habiles['Fecha'] > hoy.date(), '2. Avance Real Hecho'] = None

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_habiles['Fecha'], y=df_habiles['Meta Lineal (Paños)'], name='Meta Exigida (Lineal)', mode='lines', line=dict(color='gray', dash='dash', width=2)))
            fig.add_trace(go.Scatter(x=df_habiles['Fecha'], y=df_habiles['1. Proyección Esperada (SI+FAC)'], name='Proyección según Fechas (Ideal)', mode='lines+markers', line=dict(color='#00A8E8', width=2), marker=dict(size=6, color='#00A8E8')))
            fig.add_trace(go.Scatter(x=df_habiles['Fecha'], y=df_habiles['2. Avance Real Hecho'], name='Avance Real al Día de Hoy', mode='lines+markers', line=dict(color='#28a745', width=4), marker=dict(size=8, color='#1e7e34')))
            fig.update_layout(title="Curva de Acumulación de Trabajo (Mes)", xaxis_title="Días Hábiles", yaxis_title="Cantidad de Paños Acumulados", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)

# ==========================================
# PESTAÑA 5: KPIs
# ==========================================
with tab_kpi:
    if not df.empty:
        st.subheader("📊 Panel de Control y KPIs del Taller")
        
        with st.container(border=True):
            st.markdown("#### 🏷️ Parámetros de Referencia")
            c_ref1, c_ref2, c_ref3 = st.columns([1, 1, 2])
            with c_ref1: precio_base_iva = st.number_input("Precio Paño Seguro (Con IVA)", value=192000.0, step=1000.0)
            with c_ref2:
                valor_ref_neto = precio_base_iva / 1.21
                st.markdown(f'<div class="metric-card" style="min-height: 80px; padding: 10px; margin-bottom: 0;"><div class="metric-title">Valor Neto Objetivo (Sin IVA)</div><div class="metric-value-money" style="font-size: 1.4rem; color: #6f42c1;">{formato_pesos(valor_ref_neto)}</div></div>', unsafe_allow_html=True)
            with c_ref3: st.caption("Todo lo que se venda por debajo de este promedio indica pérdida de rentabilidad. Lo que esté por encima es ganancia extra.")

        df_kpi = df[(df['Precio'] > 0) & (df['Paños'] > 0)].copy()
        
        if not df_kpi.empty:
            st.markdown("### 📈 Indicadores Globales del Período")
            ticket_promedio_global = df_kpi['Precio'].sum() / len(df_kpi)
            intensidad_global = df_kpi['Paños'].sum() / len(df_kpi)
            precio_prom_pano_global = df_kpi['Precio'].sum() / df_kpi['Paños'].sum()
            brecha_global = precio_prom_pano_global - valor_ref_neto

            c_g1, c_g2, c_g3, c_g4 = st.columns(4)
            color_brecha, signo_brecha = ("#28a745", "+") if brecha_global >= 0 else ("#dc3545", "")
            c_g1.markdown(f'<div class="metric-card"><div class="metric-title">Precio Prom. Real x Paño</div><div class="metric-value-money">{formato_pesos(precio_prom_pano_global)}</div><div style="color:{color_brecha}; font-weight:bold; font-size:0.9rem; margin-top:5px;">{signo_brecha}{formato_pesos(brecha_global)} vs Seguro</div></div>', unsafe_allow_html=True)
            c_g2.markdown(f'<div class="metric-card"><div class="metric-title">Ticket Promedio ($/Auto)</div><div class="metric-value-money" style="color:#00235d;">{formato_pesos(ticket_promedio_global)}</div></div>', unsafe_allow_html=True)
            c_g3.markdown(f'<div class="metric-card"><div class="metric-title">Intensidad (Paños/Auto)</div><div class="metric-value-number" style="color:#17a2b8;">{intensidad_global:.2f}</div></div>', unsafe_allow_html=True)
            c_g4.markdown(f'<div class="metric-card"><div class="metric-title">Volumen (Autos Computados)</div><div class="metric-value-number" style="color:#6c757d;">{len(df_kpi)}</div></div>', unsafe_allow_html=True)
            
            st.divider()
            
            def formato_alerta(val): return f"🔴 -$ {abs(val):,.0f}".replace(',', '.') if val < 0 else f"🟢 +$ {abs(val):,.0f}".replace(',', '.')
            kpi_asesor = df_kpi.groupby('Asesor').agg(Autos=('Patente', 'count'), Paños_Totales=('Paños', 'sum'), Facturación_Total=('Precio', 'sum')).reset_index()
            kpi_asesor['Precio_Promedio_Paño'] = kpi_asesor['Facturación_Total'] / kpi_asesor['Paños_Totales']
            kpi_asesor['Brecha'] = (kpi_asesor['Precio_Promedio_Paño'] - valor_ref_neto).apply(formato_alerta)
            
            col_kpi1, col_kpi2 = st.columns(2)
            with col_kpi1:
                with st.container(border=True):
                    st.markdown("#### 👔 Rendimiento por Asesor")
                    st.dataframe(kpi_asesor[['Asesor', 'Precio_Promedio_Paño', 'Brecha', 'Autos']].sort_values('Precio_Promedio_Paño', ascending=False), hide_index=True, use_container_width=True, column_config={"Precio_Promedio_Paño": st.column_config.NumberColumn("Precio Prom. x Paño", format="$ %.0f"), "Brecha": st.column_config.TextColumn("Brecha vs. Seguro"), "Autos": st.column_config.NumberColumn("Autos")})
            with col_kpi2:
                with st.container(border=True):
                    kpi_asesor['Ticket_Promedio'] = kpi_asesor['Facturación_Total'] / kpi_asesor['Autos']
                    fig_ticket = px.bar(kpi_asesor, x='Asesor', y='Ticket_Promedio', text_auto='$.3s', title='💰 Ticket Promedio de Venta ($ por Auto)', color_discrete_sequence=['#28a745'])
                    st.plotly_chart(fig_ticket, use_container_width=True)
        else: st.warning("No hay suficientes datos válidos con Precio y Paños > 0.")

# ==========================================
# PESTAÑA 6: HISTÓRICOS
# ==========================================
with tab_hist:
    if not df_completo.empty: 
        st.subheader("📅 Histórico Mensual")
        df_hist = df_completo[df_completo['Mes_Hist'] != 'SIN FECHA'].sort_values('Mes_Hist')
        if not df_hist.empty:
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                pivot_panos = pd.pivot_table(df_hist, values='Paños', index='Mes_Hist', columns='Cliente', aggfunc='sum', fill_value=0)
                st.dataframe(pivot_panos.style.format("{:.1f}"), use_container_width=True)
            with c_h2:
                pivot_pesos = pd.pivot_table(df_hist, values='Precio', index='Mes_Hist', columns='Cliente', aggfunc='sum', fill_value=0)
                st.dataframe(pivot_pesos.style.format(lambda x: f"$ {x:,.0f}".replace(',', '.')), use_container_width=True)
            st.plotly_chart(px.bar(df_hist, x="Mes_Hist", y="Paños", color="Cliente", barmode="group", title="Paños por Mes"), use_container_width=True)
        else: st.info("No hay datos con fechas válidas.")
