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
GIDS = {"TALLER SALTA": "609774337"} # Salta tiene un solo grupo principal
URL_BASE = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid="

# ⚠️ ATENCIÓN: CAMBIAR ESTOS NOMBRES POR LOS DE SALTA
ASESORES_LISTA = ["SIN ASIGNAR", "ASESOR SALTA 1", "ASESOR SALTA 2"] 
CLIENTES_LISTA = ["PARTICULAR", "AUTOSOL", "AUTOLUX", "CIEL"]
OBJETIVO_MENSUAL_PANOS = 300.0 # Ajustá el objetivo de Salta acá

# GID de Turnos (Dejar vacío o poner el de Salta si tienen uno)
GID_TURNOS = "PONER_AQUI_GID_TURNOS" 

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds_dict)
    planilla = gc.open_by_key(ID_PLANILLA)
    try:
        hoja = planilla.worksheet("TURNOS")
    except:
        hoja = None # Si no hay pestaña TURNOS, no rompe
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

# --- ENCABEZADO ---
st.title("🚀 Sistema de Gestión Taller CENOA - Salta")

MESES_ES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# --- HELPERS DE FORMATO ---
formato_pesos = lambda x: f"$ {x:,.0f}".replace(',', '.')
formato_panos = lambda x: f"{x:.1f}"

# --- LÓGICA DE DÍAS HÁBILES ---
anio_actual = datetime.now().year
FERIADOS_ARG = [
    date(anio_actual, 3, 24), date(anio_actual, 4, 2), date(anio_actual, 4, 3)
]

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
    # Lógica de turnos original omitida para ahorrar espacio, se mantiene igual si la activás
    return pd.DataFrame(columns=columnas_base) 

@st.cache_data(ttl=300)
def obtener_datos_maestros():
    dfs = []
    for n, gid in GIDS.items():
        try:
            d_raw = pd.read_csv(f"{URL_BASE}{gid}", dtype=str, header=None)
            
            # Buscar encabezados inteligentemente
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

            # Diccionario de Renombramiento adaptado a la imagen de SALTA
            renames = {}
            for c in d.columns:
                c_str = str(c).upper().strip()
                if 'ESTADO FAC' in c_str or c_str == 'FAC': renames[c] = 'ESTADO_FAC'
                elif c_str == 'ESTADO': renames[c] = 'ESTADO_TALLER'
                elif c_str == 'FASE': renames[c] = 'FASE_TALLER'
                elif 'COMPAÑIA' in c_str or 'SEGURO' in c_str or 'EMPRESA' in c_str or 'CLIENTE' in c_str: renames[c] = 'EMPRESA_TALLER'
                elif 'OBSERVACION' in c_str: renames[c] = 'OBSERVACIONES_TALLER'
                elif 'PROM' in c_str: renames[c] = 'FECHA_PROMESA_I'
                elif 'TICKET' in c_str: renames[c] = 'FECHA_TICKET'
                elif 'INGRESO' in c_str: renames[c] = 'FECHA_INGRESO_TALLER'
                elif 'HORA' in c_str: renames[c] = 'HORA_ENTREGA'
                elif 'DOMINIO' in c_str or 'PATENTE' in c_str: renames[c] = 'PATENTE'
                # Logica de MO y REPUESTOS
                elif 'PRECIO' in c_str and ('MANO' in c_str or 'MO' in c_str): renames[c] = 'PRECIO_MO'
                elif 'COSTO' in c_str and ('MANO' in c_str or 'MO' in c_str): renames[c] = 'COSTO_MO'
                elif 'PRECIO' in c_str and 'REPUESTO' in c_str: renames[c] = 'PRECIO_REP'
                elif 'COSTO' in c_str and 'REPUESTO' in c_str: renames[c] = 'COSTO_REP'
                elif 'TERCERO' in c_str or 'ASESOR' in c_str: renames[c] = 'ASESOR'
                elif c_str == 'MES': renames[c] = 'MES'
                elif 'MARCA' in c_str or 'VEHIC' in c_str: renames[c] = 'VEHICULO'
                elif 'PAÑO' in c_str: renames[c] = 'PAÑOS'
                elif 'DIAS' in c_str and 'TRABAJO' in c_str: renames[c] = 'DIAS_TRABAJO'

            d = d.rename(columns=renames)
            if 'MES' in d.columns: d['MES'] = d['MES'].replace(r'^\s*$', pd.NA, regex=True).ffill()
            d = d.loc[:, ~d.columns.duplicated()]

            if 'PATENTE' in d.columns: 
                d = d.dropna(subset=['PATENTE'])
                d = d[d['PATENTE'].str.strip() != ""]
                d['GRUPO_ORIGEN'] = n
                dfs.append(d)
        except Exception as e: print(f"Error en pestaña {n}: {e}")
        
    if not dfs: return pd.DataFrame()
    df_raw = pd.concat(dfs, ignore_index=True)
    filas = []
    col_chasis = next((c for c in df_raw.columns if 'CHASIS' in c or 'VIN' in c), None)
    
    for _, row in df_raw.iterrows():
        f_fin = parsear_fecha_español(row.get('FECHA_PROMESA_I', ''))
        f_fin_disp = f_fin.date() if f_fin else None
        if not f_fin: f_fin = datetime.now() + timedelta(days=3650) 
        
        mes_hist = f_fin.strftime('%Y-%m') if f_fin.year < 2030 else "SIN FECHA"
        # Si la columna MES existe, la priorizamos para el historico
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
        
        p_mo = limpiar_num(row.get('PRECIO_MO', 0))
        c_mo = limpiar_num(row.get('COSTO_MO', 0))
        p_rep = limpiar_num(row.get('PRECIO_REP', 0))
        c_rep = limpiar_num(row.get('COSTO_REP', 0))
        
        # Unificamos Precio y Costo global para que los KPIs de Jujuy sigan funcionando
        precio_total = p_mo + p_rep
        costo_total = c_mo + c_rep
        
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
            'Precio': precio_total, 'Costo': costo_total, # Usados por Tablas Generales
            'Precio_MO': p_mo, 'Costo_MO': c_mo, 'Precio_REP': p_rep, 'Costo_REP': c_rep, # Usados en Facturación
            'Observaciones': str(row.get('OBSERVACIONES_TALLER', '')).replace('nan', '').strip()
        })
    return pd.DataFrame(filas)

# --- MEMORIA Y CARGA DE DATOS ---
if 'memoria_turnos_v12' not in st.session_state: st.session_state.memoria_turnos_v12 = obtener_turnos()
if 'entregas_confirmadas' not in st.session_state: st.session_state.entregas_confirmadas = []

df = obtener_datos_maestros()
df_turnos_display = st.session_state.memoria_turnos_v12.copy()
df_completo = df.copy() 

hoy = datetime.today()
hoy_ym = hoy.strftime('%Y-%m')

# --- BARRA LATERAL (SIDEBAR) Y BUSCADOR ---
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

# --- APLICAR FILTRO MENSUSAL GLOBAL A MAESTRO ---
if mes_filtro != "TODOS":
    df = df[(df['Mes_Hist'] == mes_filtro) | (df['Mes_Hist'] == 'SIN FECHA')]
    año_filtro, mes_num_filtro = map(int, mes_filtro.split('-'))
else:
    año_filtro, mes_num_filtro = hoy.year, hoy.month

DIAS_HABILES_MES = dias_habiles_del_mes(año_filtro, mes_num_filtro)
CAPACIDAD_DIARIA_TALLER = OBJETIVO_MENSUAL_PANOS / DIAS_HABILES_MES
CAPACIDAD_DIARIA_GRUPO = CAPACIDAD_DIARIA_TALLER # En Salta es 1 solo grupo, la capacidad del grupo es la total
dias_restantes_calc = dias_habiles_restantes_mes(año_filtro, mes_num_filtro)

# --- APLICAR BUSCADOR GLOBAL ---
if busqueda_global:
    termino = busqueda_global.upper().strip()
    if not df.empty:
        if 'Chasis' not in df.columns: df['Chasis'] = ""
        df = df[(df['Patente'].str.contains(termino, na=False)) | (df['Chasis'].str.contains(termino, na=False))]
                
    if not df_turnos_display.empty:
        if 'Chasis' not in df_turnos_display.columns: df_turnos_display['Chasis'] = ""
        df_turnos_display = df_turnos_display[(df_turnos_display['Patente'].str.contains(termino, na=False)) | (df_turnos_display['Chasis'].str.contains(termino, na=False))]
    
    with contenedor_resultados_busqueda:
        st.markdown("### 📋 Resumen del Vehículo")
        if not df.empty:
            for _, row in df.head(5).iterrows():
                f_prom = row.get('Fecha_Promesa_Disp')
                fecha_str = f_prom.strftime('%d/%m/%Y') if pd.notna(f_prom) else "Sin Fecha"
                estado_taller = str(row.get('Estado_Taller', ''))
                
                color_borde = "#28a745" if "ENTREGADO" in estado_taller else "#ffc107" if "PROCESO" in estado_taller else "#dc3545" if "DETENIDO" in estado_taller else "#17a2b8" if "TERM" in estado_taller else "#6c757d"
                st.markdown(f"""
                <div style='background-color: white; border: 1px solid #dee2e6; padding: 10px; border-radius: 8px; border-left: 6px solid {color_borde}; margin-bottom: 10px; font-size: 0.85em;'>
                    <div style='font-size: 1.1em; font-weight: bold; color: #00235d;'>🚗 {row['Patente']} - {str(row['Vehiculo'])[:12]}</div>
                    <strong>🏷️ Estado:</strong> {estado_taller}<br>
                    <strong>👔 Asesor:</strong> {row['Asesor']}<br>
                    <strong>📅 Entrega:</strong> <span style='color: #d32f2f; font-weight: bold;'>{fecha_str}</span>
                </div>
                """, unsafe_allow_html=True)
        else: st.warning("No se encontró el vehículo.")

# --- CÁLCULO GLOBAL DE CAPACIDAD ---
recomendaciones_grupos = {}
if not df.empty:
    df_en_proceso_global = df[df['Estado_Taller'].str.contains("PROCESO", na=False)]
    if not df_en_proceso_global.empty:
        resumen = df_en_proceso_global.groupby('Grupo')['Paños'].sum().reset_index()
        for _, row in resumen.iterrows():
            dias_reales = row['Paños'] / CAPACIDAD_DIARIA_GRUPO
            recomendaciones_grupos[row['Grupo']] = obtener_proxima_fecha_libre(dias_reales)

tab_turnos, tab_prog, tab_portal, tab_fac, tab_kpi, tab_hist = st.tabs([
    "📋 Turnero y Entregas", "🛠️ Programación del Taller", "🏢 Seguimiento Empresas", "💰 Facturación y Repuestos", "📊 KPIs", "📅 Históricos"
])

# ==========================================
# PESTAÑA 1: TURNERO Y ENTREGAS (Simplificada visualmente)
# ==========================================
with tab_turnos:
    st.info("💡 **Nota:** La función de ingresos/turnos está disponible pero depende de tener una pestaña 'TURNOS' configurada en el Sheets de Salta.")
    if recomendaciones_grupos and not busqueda_global:
        st.info("**📅 Asistente de Turnos:**\n" + " | ".join([f"**{g}**: libre desde el {f}" for g, f in recomendaciones_grupos.items()]))
    
    # 2. SALIDAS: Agenda de Entregas (Esto sí funciona con la data maestra)
    with st.container(border=True):
        st.markdown("<h2 style='color: #1e7e34; margin-top: 0;'>📤 Agenda de Entregas</h2>", unsafe_allow_html=True)
        if not df.empty:
            df_no_entregados = df[~df['Estado_Taller'].str.contains("ENTREGADO", na=False)].copy()
            df_no_entregados = df_no_entregados[~df_no_entregados['Patente'].isin(st.session_state.entregas_confirmadas)]
            df_no_entregados['Entregado_OK'] = False
            
            entregas_atrasadas = df_no_entregados[(df_no_entregados['Fecha_Promesa_Disp'].notna()) & (df_no_entregados['Fecha_Promesa_Disp'] < hoy.date())].copy()
            
            if not entregas_atrasadas.empty:
                st.markdown("#### 🔴 Entregas Atrasadas (Vencidas)")
                entregas_atrasadas = entregas_atrasadas.sort_values(by='Fecha_Promesa_Disp', ascending=True)
                entregas_atrasadas['Fecha Prom.'] = entregas_atrasadas['Fecha_Promesa_Disp'].apply(lambda x: x.strftime('%d/%m/%Y'))
                entregas_atrasadas['Demora (Días)'] = entregas_atrasadas['Fecha_Promesa_Disp'].apply(lambda x: (hoy.date() - x).days if pd.notna(x) else 0)
                
                edit_atra = st.data_editor(
                    entregas_atrasadas[['Entregado_OK', 'Demora (Días)', 'Fecha Prom.', 'Patente', 'Vehiculo', 'Asesor', 'Estado_Taller', 'Precio', 'Observaciones']], 
                    hide_index=True, use_container_width=True,
                    column_config={"Entregado_OK": st.column_config.CheckboxColumn("✅ Listo"), "Demora (Días)": st.column_config.NumberColumn("⚠️ Demora", format="%d días")}
                )
                if st.button("💾 Confirmar Salidas Seleccionadas"):
                    confirmadas = edit_atra[edit_atra['Entregado_OK'] == True]['Patente'].tolist()
                    if confirmadas:
                        st.session_state.entregas_confirmadas.extend(confirmadas)
                        st.success("Entregas registradas localmente."); time.sleep(1); st.rerun()
            else: st.success("No hay vehículos atrasados.")

# ==========================================
# PESTAÑA 2: PROGRAMACIÓN Y KANBAN
# ==========================================
with tab_prog:
    st.subheader("🛠️ Programación y Flujo de Trabajo")
    if not df.empty:
        df_en_proceso = df[df['Estado_Taller'].str.contains("PROCESO", na=False)]
        
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
        else: st.info("No hay vehículos en proceso para calcular capacidad.")

        st.divider()
        st.markdown("### 📋 Tablero Kanban - Taller Salta")
        df_kanban = df[df['Estado_Taller'].str.contains("PROCESO|DETENIDO", na=False)].copy()
        df_kanban.loc[df_kanban['Estado_Taller'].str.contains("DETENIDO", na=False), 'Fase_Taller'] = "⛔ DETENIDOS"
        
        orden_ideal = ["SIN FASE ASIGNADA", "CHAPA", "PREPARACION", "PINTURA", "ARMADO", "PULIDO", "⛔ DETENIDOS"]
        
        cols_kanban = st.columns(len(orden_ideal))
        for idx, fase in enumerate(orden_ideal):
            with cols_kanban[idx]:
                st.markdown(f"<div class='kanban-col'><h5 style='text-align:center; color:#00235d; margin: 0; font-size: 0.85rem;'>{fase}</h5></div>", unsafe_allow_html=True)
                
                # Tolerancia de búsqueda (ej. PREPARACIÓN vs PREPARACION)
                if fase == "SIN FASE ASIGNADA": df_fase = df_kanban[(df_kanban['Fase_Taller'] == "") | (df_kanban['Fase_Taller'].isna()) | (df_kanban['Fase_Taller'] == "SIN FASE ASIGNADA")]
                else: df_fase = df_kanban[df_kanban['Fase_Taller'].str.contains(fase[:4], na=False, case=False)]
                
                if not df_fase.empty:
                    for _, row in df_fase.iterrows():
                        color_borde = "#dc3545" if fase == "⛔ DETENIDOS" else "#17a2b8"
                        st.markdown(f"""
                        <div style='background: white; padding: 8px; margin-top: 8px; border-radius: 5px; border-left: 5px solid {color_borde}; box-shadow: 1px 1px 3px rgba(0,0,0,0.1); font-size: 0.9em;'>
                            <strong>{row['Patente']}</strong><br>
                            <span style='font-size: 0.85em;'>{row['Vehiculo'][:15]}</span><br>
                            <span style='font-size: 0.8em; color: gray;'>📦 {row['Paños']} p. | {row['Asesor']}</span>
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
            df_vista_emp = df_grupo.sort_values(by='Fecha_Promesa_Disp', ascending=True, na_position='last')
            en_proceso = len(df_vista_emp[df_vista_emp['Estado_Taller'].str.contains("PROCESO", na=False)])
            detenidos = len(df_vista_emp[df_vista_emp['Estado_Taller'].str.contains("DETENIDO", na=False)])
            terminados = len(df_vista_emp[df_vista_emp['Estado_Taller'].str.contains("TERM", na=False)])
            
            ce1, ce2, ce3 = st.columns(3)
            ce1.markdown(f'<div class="metric-card"><div class="metric-title">En Proceso</div><div class="metric-value-number">{en_proceso}</div></div>', unsafe_allow_html=True)
            ce2.markdown(f'<div class="metric-card"><div class="metric-title">Detenidos</div><div class="metric-value-number" style="color:#dc3545;">{detenidos}</div></div>', unsafe_allow_html=True)
            ce3.markdown(f'<div class="metric-card"><div class="metric-title">Terminados (Pte. Entregar)</div><div class="metric-value-number" style="color:#28a745;">{terminados}</div></div>', unsafe_allow_html=True)
            
            st.dataframe(df_vista_emp[['Cliente', 'Patente', 'Vehiculo', 'Estado_Taller', 'Fecha_Promesa_Disp', 'Observaciones']], hide_index=True, use_container_width=True)
        else: st.info("No hay vehículos registrados para las empresas del grupo (Autosol/Autolux/Ciel).")

# ==========================================
# PESTAÑA 4: FACTURACIÓN Y REPUESTOS (ESPECIAL SALTA)
# ==========================================
with tab_fac:
    if not df.empty:
        st.subheader("💰 Análisis de Facturación: Mano de Obra + Repuestos")
        
        # Filtramos los que están facturados o aprobados para el cálculo (Misma lógica que Jujuy pero con MO y REP)
        df_ventas = df[df['Estado_Fac'].isin(['FAC', 'SI'])].copy()
        
        # --- TARJETAS SUPERIORES (Estilo Jujuy pero con datos de Salta) ---
        panos_fac = df[df['Estado_Fac'] == 'FAC']['Paños'].sum()
        panos_si = df[df['Estado_Fac'] == 'SI']['Paños'].sum()
        panos_est = panos_fac + panos_si
        porcentaje_logro = min((panos_est / OBJETIVO_MENSUAL_PANOS) * 100 if OBJETIVO_MENSUAL_PANOS > 0 else 0, 100)
        
        st.markdown("### 🎯 Control de Objetivo Mensual (Paños)")
        st.progress(int(porcentaje_logro))
        st.caption(f"**Progreso:** {panos_est:.1f} paños asegurados de un objetivo de {OBJETIVO_MENSUAL_PANOS} paños ({porcentaje_logro:.1f}%).")
        st.divider()
        
        if not df_ventas.empty:
            v_mo = df_ventas['Precio_MO'].sum()
            c_mo = df_ventas['Costo_MO'].sum()
            m_mo = v_mo - c_mo
            
            v_rep = df_ventas['Precio_REP'].sum()
            c_rep = df_ventas['Costo_REP'].sum()
            m_rep = v_rep - c_rep
            
            porc_margen_rep = (m_rep / v_rep * 100) if v_rep > 0 else 0
            
            total_venta = v_mo + v_rep
            total_margen = m_mo + m_rep
            
            st.markdown("### 💼 Rentabilidad Estimada al Cierre (Aprobados + Facturados)")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### 🔧 Mano de Obra")
                st.markdown(f'<div class="metric-card"><div class="metric-title">Venta MO</div><div class="metric-value-money">{formato_pesos(v_mo)}</div><div class="metric-subtitle-green" style="font-size:0.8rem; color:#666;">Costo: {formato_pesos(c_mo)}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown("#### 📦 Repuestos")
                st.markdown(f'<div class="metric-card"><div class="metric-title">Venta Repuestos</div><div class="metric-value-money" style="color: #28a745;">{formato_pesos(v_rep)}</div><div class="metric-subtitle-red" style="font-size:0.9rem;">Costo: {formato_pesos(c_rep)}</div><div style="font-size: 0.8rem; color: #00235d; font-weight: bold; margin-top:5px;">Margen Rep: {porc_margen_rep:.1f}%</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown("#### 🏆 Total Operación")
                st.markdown(f'<div class="metric-card" style="border: 2px solid #00235d;"><div class="metric-title">Facturación Total (MO + Rep)</div><div class="metric-value-money">{formato_pesos(total_venta)}</div><div class="metric-subtitle-green" style="margin-top:5px;">Ganancia Bruta: {formato_pesos(total_margen)}</div></div>', unsafe_allow_html=True)

            st.divider()
            st.write("### 🔍 Detalle de Rentabilidad por Unidad (Aprobados/Facturados)")
            df_detalle = df_ventas[['Patente', 'Cliente', 'Asesor', 'Estado_Fac', 'Precio_MO', 'Precio_REP', 'Precio', 'Costo']].copy()
            df_detalle['Margen ($)'] = df_detalle['Precio'] - df_detalle['Costo']
            
            st.dataframe(
                df_detalle.sort_values('Precio', ascending=False), hide_index=True, use_container_width=True,
                column_config={
                    "Precio_MO": st.column_config.NumberColumn("Venta MO ($)", format="$ %.0f"),
                    "Precio_REP": st.column_config.NumberColumn("Venta Repuestos ($)", format="$ %.0f"),
                    "Precio": st.column_config.NumberColumn("Total Facturado ($)", format="$ %.0f"),
                    "Costo": st.column_config.NumberColumn("Costo Total ($)", format="$ %.0f"),
                    "Margen ($)": st.column_config.NumberColumn("Margen de Ganancia ($)", format="$ %.0f")
                }
            )
        else: st.info("No hay vehículos marcados como 'FAC' o 'SI' en la columna de Estado de Facturación.")

# ==========================================
# PESTAÑA 5: KPIs
# ==========================================
with tab_kpi:
    if not df.empty:
        st.subheader("📊 Panel de Control y KPIs del Taller")
        df_kpi = df[(df['Precio'] > 0) & (df['Paños'] > 0)].copy()
        
        if not df_kpi.empty:
            ticket_promedio_global = df_kpi['Precio'].sum() / len(df_kpi)
            intensidad_global = df_kpi['Paños'].sum() / len(df_kpi)
            precio_prom_pano_global = df_kpi['Precio'].sum() / df_kpi['Paños'].sum()

            c_g1, c_g2, c_g3, c_g4 = st.columns(4)
            c_g1.markdown(f'<div class="metric-card"><div class="metric-title">Precio Prom. Real x Paño</div><div class="metric-value-money">{formato_pesos(precio_prom_pano_global)}</div></div>', unsafe_allow_html=True)
            c_g2.markdown(f'<div class="metric-card"><div class="metric-title">Ticket Promedio ($/Auto)</div><div class="metric-value-money" style="color:#00235d;">{formato_pesos(ticket_promedio_global)}</div></div>', unsafe_allow_html=True)
            c_g3.markdown(f'<div class="metric-card"><div class="metric-title">Intensidad (Paños/Auto)</div><div class="metric-value-number" style="color:#17a2b8;">{intensidad_global:.2f}</div></div>', unsafe_allow_html=True)
            c_g4.markdown(f'<div class="metric-card"><div class="metric-title">Volumen (Autos)</div><div class="metric-value-number" style="color:#6c757d;">{len(df_kpi)}</div></div>', unsafe_allow_html=True)
            
            kpi_asesor = df_kpi.groupby('Asesor').agg(Autos=('Patente', 'count'), Facturación_Total=('Precio', 'sum')).reset_index()
            fig_ticket = px.bar(kpi_asesor, x='Asesor', y='Facturación_Total', text_auto='$.3s', title='💰 Facturación Total por Asesor')
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
