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

# --- CONEXIÓN A GOOGLE SHEETS (GSPREAD) ---
try:
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds_dict)
    ID_PLANILLA = "1yVeTn7UJV5izBURIXFjROwnH1xD8L3vDpesPVZzy45c" # SALTA ID
    planilla = gc.open_by_key(ID_PLANILLA)
    
    # 1. Traemos la pestaña principal
    hoja = planilla.worksheet("TURNOS")
    
    # 2. Traemos la pestaña de Repuestos
    hoja_repuestos = planilla.worksheet("REPUESTOS")
    
    # 3. Traemos la pestaña de Terceros
    hoja_terceros = planilla.worksheet("TERCEROS")
        
except Exception as e:
    st.error(f"Error de conexión a Google Sheets: {e}")
    hoja = None
    hoja_repuestos = None
    hoja_terceros = None

# --- FUNCIONES DE LIMPIEZA GLOBAL (PARA TODA LA APP) ---

# Función para traducir fechas y blindar el año 2026
def limpiar_fecha_ar(fecha_str):
    if pd.isna(fecha_str) or str(fecha_str).strip() == '': return pd.NaT
    f = str(fecha_str).strip().lower()
    reemplazos = {'ene': 'jan', 'abr': 'apr', 'ago': 'aug', 'dic': 'dec'}
    for es, en in reemplazos.items():
        f = f.replace(es, en)
    try:
        dt = pd.to_datetime(f, dayfirst=True, errors='coerce')
        if pd.notna(dt):
            # 🚨 SOLUCIÓN AÑO 2026: Si ponés "17-4", lo forzamos al año 2026.
            tiene_anio = re.search(r'\d{4}', f) or re.search(r'/\d{2}$', f) or re.search(r'-\d{2}$', f)
            if not tiene_anio:
                dt = dt.replace(year=2026) 
            elif dt.year < 2000:
                dt = dt.replace(year=2026)
        return dt
    except:
        return pd.NaT

# Función blindada para limpiar plata y números (Inmune a columnas duplicadas)
def limpiar_plata_general(x):
    try:
        # Si vienen datos duplicados juntos, agarramos solo el primero
        if isinstance(x, pd.Series): 
            x = x.iloc[0]
            
        if pd.isna(x) or str(x).strip() == '': return 0.0
        if isinstance(x, (int, float)): return float(x)
        
        x = str(x).replace('$', '').replace(' ', '').replace('.', '').replace(',', '.') 
        return float(x)
    except: 
        return 0.0

# --- CARGA Y LIMPIEZA DE PESTAÑA PRINCIPAL (TURNOS) ---
if hoja is not None:
    try:
        # 1. Leemos todo y lo pasamos a un DataFrame
        df = pd.DataFrame(hoja.get_all_records())
        
        # 2. Normalizamos nombres de columnas (Pasamos todo a MAYÚSCULAS y sin espacios)
        df.columns = [str(c).upper().strip() for c in df.columns]

        # 3. Limpieza de Fechas para todas las pestañas
        col_prom = next((c for c in df.columns if 'PROM' in c), None)
        col_taller = next((c for c in df.columns if 'FECHA TALLER' in c), None)

        if col_prom:
            df['FECHA_PROM_DT'] = df[col_prom].apply(limpiar_fecha_ar)
        if col_taller:
            df['FECHA_TALLER_DT'] = df[col_taller].apply(limpiar_fecha_ar)

        # Creamos una FECHA FINAL (usa Taller si existe, sino usa Promesa)
        if 'FECHA_TALLER_DT' in df.columns and 'FECHA_PROM_DT' in df.columns:
            df['FECHA_FINAL'] = df['FECHA_TALLER_DT'].combine_first(df['FECHA_PROM_DT'])
        elif 'FECHA_PROM_DT' in df.columns:
            df['FECHA_FINAL'] = df['FECHA_PROM_DT']

    except Exception as e:
        st.error(f"Error procesando los datos de TURNOS: {e}")
        df = pd.DataFrame()
else:
    df = pd.DataFrame()

# --- CARGA INSTANTÁNEA BLINDADA (REPUESTOS Y TERCEROS) ---
def cargar_hoja_directa(hoja_gs, nombre_grupo):
    try:
        datos = hoja_gs.get_all_values()
        if not datos: return pd.DataFrame()
        
        # Buscamos la fila de títulos
        idx = 0
        for i, fila in enumerate(datos):
            if any(str(c).strip() for c in fila):
                idx = i
                break
        
        df_res = pd.DataFrame(datos[idx+1:], columns=datos[idx])
        df_res.columns = [str(c).upper().strip() for c in df_res.columns]
        
        # 🚨 ELIMINAMOS COLUMNAS DUPLICADAS PARA EVITAR ERRORES
        df_res = df_res.loc[:, ~df_res.columns.duplicated()]
        
        df_res['GRUPO'] = nombre_grupo 
        return df_res
    except:
        return pd.DataFrame()

# Cargar Repuestos
if hoja_repuestos:
    df_repuestos = cargar_hoja_directa(hoja_repuestos, "REPUESTOS")
    if not df_repuestos.empty:
        if 'FECHA TALLER' in df_repuestos.columns:
            df_repuestos['FECHA_DT'] = df_repuestos['FECHA TALLER'].apply(limpiar_fecha_ar)
        if 'PRECIO' in df_repuestos.columns:
            df_repuestos['PRECIO_LIMPIO'] = df_repuestos['PRECIO'].apply(limpiar_plata_general)

# Cargar Terceros
if hoja_terceros:
    df_terceros_data = cargar_hoja_directa(hoja_terceros, "TERCEROS")
    if not df_terceros_data.empty:
        for col in ['PRECIO', 'COSTO', 'PAÑOS']:
            if col in df_terceros_data.columns:
                df_terceros_data[col] = df_terceros_data[col].apply(limpiar_plata_general)
        if 'FECHA PROM' in df_terceros_data.columns:
            df_terceros_data['FECHA_DT'] = df_terceros_data['FECHA PROM'].apply(limpiar_fecha_ar)
            
# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Taller CENOA - Salta", layout="wide", initial_sidebar_state="expanded")

# --- ESTILOS CSS INYECTADOS ---
st.markdown("""<style>
    /* Achicar la barra lateral */
    [data-testid="stSidebar"] { min-width: 240px !important; max-width: 240px !important; }
    
    .metric-card { background-color: white; border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 110px; margin-bottom: 15px;}
    .metric-title { color: #666; font-size: 0.85rem; font-weight: 600; margin-bottom: 5px; text-transform: uppercase; }
    .metric-value-money { color: #00235d; font-size: 1.8rem; font-weight: bold; margin: 0; }
    .metric-value-number { color: #00235d; font-size: 1.5rem; font-weight: bold; margin: 0; }
    .metric-subtitle-red { color: #dc3545; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .metric-subtitle-green { color: #28a745; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .metric-subtitle-blue { color: #17a2b8; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .metric-subtitle-gray { color: #888; font-size: 0.8rem; margin-top: 5px; }
    .metric-subtitle-purple { color: #6f42c1; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .kanban-col { background-color: #f8f9fa; border-radius: 8px; padding: 10px; border: 1px solid #e9ecef; }
</style>""", unsafe_allow_html=True)

# --- ENCABEZADO ---
st.title("🚀 Sistema de Gestión Taller CENOA - Salta")

# --- CONFIGURACIÓN DE GIDS Y VARIABLES ---
ID_NUEVO_SHEET = "1yVeTn7UJV5izBURIXFjROwnH1xD8L3vDpesPVZzy45c"
URL_BASE = f"https://docs.google.com/spreadsheets/d/{ID_NUEVO_SHEET}/export?format=csv&gid="
GID_TURNOS = "109364752" 

GIDS = {"GRUPO": "609774337", "PULIDOS": "527300176", "REPUESTOS": "1212138688", "TERCEROS": "431495457"}

MESES_ES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# NOTA: Ajustar nombres de asesores para Salta si es necesario
ASESORES_LISTA = ["SIN ASIGNAR", "CESAR OLIVA", "JAVIER GUTIERREZ", "ANDREA MARTINS"] 
CLIENTES_LISTA = ["CENOA", "CENOA SEGURO", "CIEL", "CIEL SEGURO", "CIEL OKM", "CIEL USADO", "AUTOSOL", "AUTOSOL SEGURO", "AUTOSOL OKM", "AUTOSOL USADO", "AUTOLUX", "AUTOLUX SEGURO", "AUTOLUX OKM", "AUTOLUX USADO", "PARTICULAR"]

OBJETIVO_MENSUAL_PANOS = 400.0

# --- HELPERS DE FORMATO ---
formato_pesos = lambda x: f"$ {x:,.0f}".replace(',', '.')
formato_panos = lambda x: f"{x:.1f}"

# --- LÓGICA DE DÍAS HÁBILES ---
anio_actual = datetime.now().year
FERIADOS_ARG = [
    date(anio_actual, 3, 24),
    date(anio_actual, 4, 2), 
    date(anio_actual, 4, 3)  
]

def dias_habiles_del_mes(anio, mes):
    _, ult_dia = calendar.monthrange(anio, mes)
    dias = sum(1 for d in range(1, ult_dia + 1) if date(anio, mes, d).weekday() < 5 and date(anio, mes, d) not in FERIADOS_ARG)
    return max(1, dias)

def dias_habiles_restantes_mes(anio, mes):
    hoy_f = datetime.today().date()
    if anio == hoy_f.year and mes == hoy_f.month:
        dia_inicio = hoy_f.day
    elif date(anio, mes, 1) < hoy_f:
        return 0
    else:
        dia_inicio = 1
        
    _, ult_dia = calendar.monthrange(anio, mes)
    dias_restantes = sum(1 for d in range(dia_inicio, ult_dia + 1) if date(anio, mes, d).weekday() < 5 and date(anio, mes, d) not in FERIADOS_ARG)
    return dias_restantes

# --- FUNCIONES ---
def parsear_fecha_español(texto):
    if pd.isna(texto) or str(texto).strip() == "": return None 
    texto = str(texto).lower().strip()
    
    meses_abrev = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12}
    
    match_abrev = re.search(r'(\d{1,2})[-/]([a-z]{3})', texto)
    if match_abrev:
        dia, mes_str = int(match_abrev.groups()[0]), match_abrev.groups()[1]
        if mes_num := meses_abrev.get(mes_str): return datetime(datetime.now().year, mes_num, dia)

    match_dm = re.match(r'^(\d{1,2})[-/](\d{1,2})$', texto)
    if match_dm: 
        try:
            return datetime(datetime.now().year, int(match_dm.groups()[1]), int(match_dm.groups()[0]))
        except ValueError:
            return None  # Si escriben una fecha que no existe (ej: 31/04), la ignora y no rompe la app
    
    try:
        res = pd.to_datetime(texto, dayfirst=True)
        if pd.notna(res): return res.to_pydatetime()
    except: pass
    
    try:
        match = re.search(r'(\d+)\s+de\s+([a-z]+)\s+de\s+(\d+)', texto)
        if match: return datetime(int(match.groups()[2]), MESES_ES.get(match.groups()[1], 1), int(match.groups()[0]))
    except: pass
    
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
        if fecha.weekday() < 5 and fecha.date() not in FERIADOS_ARG:
            dias_agregados += 1
    return f"{DIAS_SEMANA[fecha.weekday()]} {fecha.strftime('%d/%m')}"

@st.cache_data(ttl=300)
def obtener_turnos():
    columnas_base = ['Estado_Turno', 'Fecha', 'Hora', 'Vehiculo', 'Patente', 'Asesor', 'Precio', 'Paños', 'Observaciones', 'Tiempo', 'Cliente', 'Seguro', 'Ticket', 'Recibido', 'Fotos', 'Referencia', 'Motivo_Cancelacion']
    try:
        if hoja is None:
            return pd.DataFrame(columns=columnas_base)
        
        datos = hoja.get_all_values()
        if not datos or len(datos) <= 1:
            return pd.DataFrame(columns=columnas_base)
            
        # Buscamos la fila de títulos
        idx = 0
        for i, fila in enumerate(datos):
            fila_str = "".join(str(c).upper() for c in fila)
            if 'FECHA' in fila_str and 'PATENTE' in fila_str:
                idx = i
                break
                
        df_t = pd.DataFrame(datos[idx+1:], columns=datos[idx])
        
        # Blindaje anti-columnas duplicadas
        cols_limpias = []
        vistos = {}
        for c in df_t.columns:
            c_upper = str(c).upper().strip()
            if not c_upper: c_upper = "VACIA"
            if c_upper in vistos:
                vistos[c_upper] += 1
                cols_limpias.append(f"{c_upper}_{vistos[c_upper]}")
            else:
                vistos[c_upper] = 0
                cols_limpias.append(c_upper)
        df_t.columns = cols_limpias
        
        while len(df_t.columns) < 17:
            df_t[f'FALTANTE_{len(df_t.columns)}'] = ""
            
        df_t['Estado_Turno'] = df_t.iloc[:, 0]
        df_t['Fecha_Texto'] = df_t.iloc[:, 1]
        df_t['Hora'] = df_t.iloc[:, 2]
        df_t['Vehiculo'] = df_t.iloc[:, 3]
        df_t['Patente'] = df_t.iloc[:, 4]
        df_t['Asesor'] = df_t.iloc[:, 5]
        df_t['Observaciones'] = df_t.iloc[:, 8]
        df_t['Cliente'] = df_t.iloc[:, 10]
        df_t['Ticket'] = df_t.iloc[:, 12]
        df_t['Recibido_Texto'] = df_t.iloc[:, 13]
        df_t['Fotos_Texto'] = df_t.iloc[:, 14]
        df_t['Referencia'] = df_t.iloc[:, 15]
        df_t['Motivo_Cancelacion'] = df_t.iloc[:, 16]
        
        # 🚨 CONECTAMOS EL MOTOR DE FECHAS (Para solucionar el "17-4")
        df_t['Fecha_DT'] = df_t['Fecha_Texto'].apply(limpiar_fecha_ar)
        df_t['Fecha'] = df_t['Fecha_DT'].apply(lambda x: x.date() if pd.notna(x) else None)
        
        df_t['Cancelado'] = df_t['Estado_Turno'].astype(str).str.upper() == 'C'
        df_t['Tipo'] = df_t['Estado_Turno'].apply(lambda x: '🚶‍♂️ SIN TURNO' if str(x).upper() == 'N' else '📅 PROGRAMADO')
        df_t['Recibido'] = df_t['Recibido_Texto'].astype(str).str.upper() == 'SI'
        df_t['Fotos'] = df_t['Fotos_Texto'].astype(str).str.upper() == 'SI'
        
        for col in ['Ticket', 'Referencia', 'Observaciones', 'Asesor', 'Cliente', 'Vehiculo', 'Patente', 'Motivo_Cancelacion']:
            df_t[col] = df_t[col].fillna("")
            
        return df_t
        
    except Exception as e:
        print(f"Error cargando turnos: {e}")
        return pd.DataFrame(columns=columnas_base)

@st.cache_data(ttl=300)
def obtener_datos_maestros():
    dfs = []
    for n, gid in GIDS.items():
        try:
            d_raw = pd.read_csv(f"{URL_BASE}{gid}", dtype=str, header=None)
            
            idx_header = 0
            for i in range(min(15, len(d_raw))):
                fila_str = " ".join(d_raw.iloc[i].fillna("").astype(str).str.upper())
                # Buscamos la fila de títulos escaneando si tiene alguna de estas palabras
                if 'DOMINIO' in fila_str or 'PATENTE' in fila_str or 'CHASIS' in fila_str or 'VEHICULO' in fila_str:
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
                if 'ESTADO FAC' in c_str or c_str == 'FAC' or 'FACTURACION' in c_str: renames[c] = 'ESTADO_FAC'
                elif c_str == 'ESTADO' or 'ESTADO TALLER' in c_str: renames[c] = 'ESTADO_TALLER'
                elif 'FASE' in c_str: renames[c] = 'FASE_TALLER'
                elif 'EMPRESA' in c_str or 'COMPAÑIA' in c_str or 'CLIENTE' in c_str:
                    if 'EMPRESA_TALLER' not in renames.values(): renames[c] = 'EMPRESA_TALLER'
                elif 'OBSERVACION' in c_str or 'NOVEDAD' in c_str: renames[c] = 'OBSERVACIONES_TALLER'
                elif 'PROM' in c_str or 'ENTREGA' in c_str: 
                    if 'HORA' not in c_str: renames[c] = 'FECHA_PROMESA_I'
                elif 'FECHA TALLER' in c_str:
                    renames[c] = 'FECHA_TALLER_REAL'
                elif 'INGR' in c_str or 'RECEPCION' in c_str: renames[c] = 'FECHA_INGRESO_TALLER'
                elif 'HS PROM' in c_str or 'HORA' in c_str: renames[c] = 'HORA_ENTREGA'
                elif c_str == 'PATENTE' or c_str == 'DOMINIO': renames[c] = 'PATENTE'
                elif c_str == 'PRECIO' or c_str == 'MONTO': renames[c] = 'PRECIO'
                elif c_str == 'COSTO': renames[c] = 'COSTO'
                elif c_str == 'ASESOR' or 'RECEPCIONISTA' in c_str: renames[c] = 'ASESOR'
                elif c_str == 'VEHICULO' or 'MARCA' in c_str or 'MODELO' in c_str: renames[c] = 'VEHICULO'
                elif c_str == 'PAÑOS' or 'PAÑO' in c_str or 'PANO' in c_str: renames[c] = 'PAÑOS'
                elif 'DIAS' in c_str and ('TRABAJO' in c_str or 'REP' in c_str): renames[c] = 'DIAS_TRABAJO'
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
        # --- EL MOTOR INTELIGENTE DE FECHAS ---
        f_promesa_original = parsear_fecha_español(row.get('FECHA_PROMESA_I', ''))
        f_taller_real = parsear_fecha_español(row.get('FECHA_TALLER_REAL', ''))
        
        # LA REGLA DE ORO: Si existe FECHA TALLER, gana esa. Si no, queda la PROMESA.
        f_fin = f_taller_real if f_taller_real else f_promesa_original
        
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
            'Inicio': f_fin - timedelta(days=max(1, int(panos))), 
            'Fin': f_fin, 
            'Fecha_Promesa_Disp': f_fin_disp, 
            'Fecha_Ingreso': f_ingreso.date() if f_ingreso else None, 
            # Guardamos la promesa original pura por si querés ver cuánto se demoró
            'Fecha_Ticket': f_promesa_original.date() if f_promesa_original else None, 
            'Hora_Entrega': str(row.get('HORA_ENTREGA', '')).replace('nan', '').strip(),
            'Mes_Hist': mes_hist, 'Paños': panos, 'Dias_Reparacion': dias_rep, 'Tipo_ABC': clasificar_abc(panos),
            'Estado_Fac': estado_fac, 'Estado_Taller': estado, 'Fase_Taller': fase, 
            'Precio': precio_val, 'Costo': costo_val,
            'Observaciones': str(row.get('OBSERVACIONES_TALLER', '')).replace('nan', '').strip()
        })
    return pd.DataFrame(filas)

# --- MEMORIA Y CARGA DE DATOS ---
if 'memoria_turnos_v12' not in st.session_state: 
    st.session_state.memoria_turnos_v12 = obtener_turnos()

if 'entregas_confirmadas' not in st.session_state:
    st.session_state.entregas_confirmadas = []

df = obtener_datos_maestros()
df_turnos_display = st.session_state.memoria_turnos_v12.copy()
df_completo = df.copy() 

hoy = datetime.today()
hoy_ym = hoy.strftime('%Y-%m')

# --- LECTURA DINÁMICA ASESORES ---
if not df.empty:
    asesores_unicos = [str(a).strip().upper() for a in df['Asesor'].unique() if pd.notna(a) and str(a).strip().upper() != "SIN ASIGNAR"]
    ASESORES_LISTA = ["SIN ASIGNAR"] + sorted(list(set(asesores_unicos)))

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
    
    if mes_seleccionado_label == "🗓️ MES ACTUAL":
        mes_filtro = hoy_ym
    elif mes_seleccionado_label == "♾️ TODOS":
        mes_filtro = "TODOS"
    else:
        mes_filtro = mapa_meses.get(mes_seleccionado_label, "TODOS")
        
    st.caption("Aplica a Turnos, Taller y Facturación. El Histórico se mantiene global.")
    
    st.divider()
    st.markdown("### ⚙️ Sistema")
    if st.button("🔄 Forzar Actualización", use_container_width=True):
        st.cache_data.clear()
        if 'memoria_turnos_v12' in st.session_state:
            del st.session_state['memoria_turnos_v12']
        st.success("¡Datos actualizados y memoria limpia!"); time.sleep(0.5); st.rerun()
    st.caption("Datos extraídos de Google Sheets.")

# --- APLICAR FILTRO MENSUSAL GLOBAL A MAESTRO ---
if mes_filtro != "TODOS":
    df = df[(df['Mes_Hist'] == mes_filtro) | (df['Mes_Hist'] == 'SIN FECHA')]
    año_filtro, mes_num_filtro = map(int, mes_filtro.split('-'))
    DIAS_HABILES_MES = dias_habiles_del_mes(año_filtro, mes_num_filtro)
else:
    año_filtro, mes_num_filtro = hoy.year, hoy.month
    DIAS_HABILES_MES = dias_habiles_del_mes(año_filtro, mes_num_filtro)

CAPACIDAD_DIARIA_TALLER = OBJETIVO_MENSUAL_PANOS / DIAS_HABILES_MES
CAPACIDAD_DIARIA_GRUPO = CAPACIDAD_DIARIA_TALLER / 2
dias_restantes_calc = dias_habiles_restantes_mes(año_filtro, mes_num_filtro)

# --- APLICAR BUSCADOR GLOBAL ---
if busqueda_global:
    termino = busqueda_global.upper().strip()
    
    if not df.empty:
        if 'Chasis' not in df.columns: df['Chasis'] = ""
        df = df[(df['Patente'].str.contains(termino, na=False)) | 
                (df['Chasis'].str.contains(termino, na=False))]
                
    if not df_turnos_display.empty:
        if 'Chasis' not in df_turnos_display.columns: df_turnos_display['Chasis'] = ""
        df_turnos_display = df_turnos_display[(df_turnos_display['Patente'].str.contains(termino, na=False)) | 
                                              (df_turnos_display['Chasis'].str.contains(termino, na=False))]
    
    with contenedor_resultados_busqueda:
        st.markdown("### 📋 Resumen del Vehículo")
        if not df.empty:
            for _, row in df.head(5).iterrows():
                f_prom = row.get('Fecha_Promesa_Disp')
                fecha_str = f_prom.strftime('%d/%m/%Y') if pd.notna(f_prom) else "Sin Fecha"
                estado_taller = str(row.get('Estado_Taller', ''))
                
                if "ENTREGADO" in estado_taller: color_borde = "#28a745"
                elif "PROCESO" in estado_taller: color_borde = "#ffc107"
                elif "DETENIDO" in estado_taller: color_borde = "#dc3545"
                elif "TERM" in estado_taller: color_borde = "#17a2b8"
                else: color_borde = "#6c757d"
                
                st.markdown(f"""
                <div style='background-color: white; border: 1px solid #dee2e6; padding: 10px; border-radius: 8px; border-left: 6px solid {color_borde}; margin-bottom: 10px; font-size: 0.85em; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
                    <div style='font-size: 1.1em; font-weight: bold; color: #00235d; margin-bottom: 5px; border-bottom: 1px solid #eee; padding-bottom: 3px;'>🚗 {row['Patente']} - {str(row['Vehiculo'])[:12]}</div>
                    <strong>🏷️ Estado:</strong> {estado_taller}<br>
                    <strong>🏭 Grupo:</strong> {row['Grupo']}<br>
                    <strong>👔 Asesor:</strong> {row['Asesor']}<br>
                    <strong>📅 Entrega:</strong> <span style='color: #d32f2f; font-weight: bold;'>{fecha_str}</span>
                </div>
                """, unsafe_allow_html=True)
                
        elif not df_turnos_display.empty:
            for _, row in df_turnos_display.head(3).iterrows():
                fecha_turno = row['Fecha'].strftime('%d/%m/%Y') if pd.notna(row['Fecha']) else "Sin Fecha"
                st.markdown(f"""
                <div style='background-color: white; border: 1px solid #dee2e6; padding: 10px; border-radius: 8px; border-left: 6px solid #6f42c1; margin-bottom: 10px; font-size: 0.85em; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
                    <div style='font-size: 1.1em; font-weight: bold; color: #00235d; margin-bottom: 5px; border-bottom: 1px solid #eee; padding-bottom: 3px;'>📝 TURNO: {row['Patente']}</div>
                    <strong>🏷️ Tipo:</strong> {row['Tipo']}<br>
                    <strong>📅 Día Asignado:</strong> {fecha_turno}<br>
                    <strong>👔 Asesor:</strong> {row['Asesor']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("No se encontró el vehículo.")

# --- CÁLCULO GLOBAL DE CAPACIDAD ---
recomendaciones_grupos = {}
if not df.empty:
    # Solo consideramos los de Mano de Obra para sugerir turnos
    df_mo_global = df[df['Grupo'].isin(['GRUPO', 'PULIDOS'])]
    df_en_proceso_global = df_mo_global[df_mo_global['Estado_Taller'].str.contains("PROCESO", na=False)]
    if not df_en_proceso_global.empty:
        resumen = df_en_proceso_global.groupby('Grupo')['Paños'].sum().reset_index()
        for _, row in resumen.iterrows():
            dias_reales = row['Paños'] / CAPACIDAD_DIARIA_GRUPO
            fecha_recomendada = obtener_proxima_fecha_libre(dias_reales)
            recomendaciones_grupos[row['Grupo']] = fecha_recomendada

tab_turnos, tab_prog, tab_portal, tab_fac, tab_kpi, tab_hist = st.tabs([
    "📋 Turnero y Entregas", "🛠️ Programación del Taller", "🏢 Seguimiento Empresas", "💰 Facturación", "📊 KPIs", "📅 Históricos"
])

# ==========================================
# PESTAÑA 1: TURNERO Y ENTREGAS
# ==========================================
with tab_turnos:
    if recomendaciones_grupos and not busqueda_global:
        st.info("**📅 Asistente de Turnos (Disponibilidad Estimada por Sector):**\n" + 
                " | ".join([f"**{g}**: libre desde el {f}" for g, f in recomendaciones_grupos.items()]))
    
    st.markdown("<h4 style='color: #00235d; margin-top: 10px;'>🔍 Filtros de Visualización (Aplican a Ingresos y Salidas)</h4>", unsafe_allow_html=True)
    col_fecha, col_asesor, col_add = st.columns([1, 1, 2])
    
    with col_fecha:
        if mes_filtro != "TODOS":
            primer_dia = date(año_filtro, mes_num_filtro, 1)
            _, ult_dia_int = calendar.monthrange(año_filtro, mes_num_filtro)
            ultimo_dia = date(año_filtro, mes_num_filtro, ult_dia_int)
            
            if mes_seleccionado_label == "🗓️ MES ACTUAL":
                rango_default = (hoy.date(), hoy.date()) 
            else:
                rango_default = (primer_dia, ultimo_dia) 
        else:
            rango_default = (hoy.date(), hoy.date())
            
        fechas_seleccionadas = st.date_input("📅 Rango de Fechas", value=rango_default, format="DD/MM/YYYY")
        if isinstance(fechas_seleccionadas, tuple):
            f_inicio = f_fin = fechas_seleccionadas[0] if len(fechas_seleccionadas) < 2 else fechas_seleccionadas[0]
            if len(fechas_seleccionadas) == 2: f_fin = fechas_seleccionadas[1]
        else: f_inicio = f_fin = fechas_seleccionadas
        
    with col_asesor: 
        asesor_filtro = st.selectbox("👔 Filtrar por Asesor", ["TODOS"] + ASESORES_LISTA)
        
    with col_add:
        with st.expander("➕ Ingresar vehículo SIN TURNO (Walk-in)"):
            if "procesando_envio" not in st.session_state:
                st.session_state.procesando_envio = False

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
                st.write("📋 Checklist de Recepción (Al ingresar físicamente al taller):")
                c_chk1, c_chk2, c_ref = st.columns([1, 1, 2])
                val_recibido_bool = c_chk1.checkbox("✅ ¿Vehículo Recibido?")
                val_foto_bool = c_chk2.checkbox("📸 ¿Fotos tomadas?")
                nueva_referencia = c_ref.text_input("N° Referencia / OR")

                enviado = st.form_submit_button("Agregar al Turnero y Guardar en Sheets")
                
                if enviado:
                    if not st.session_state.procesando_envio:
                        if nueva_patente and nuevo_vehiculo:
                            st.session_state.procesando_envio = True
                            if hoja is not None:
                                try:
                                    val_recibido = "SI" if val_recibido_bool else ""
                                    val_foto = "SI" if val_foto_bool else ""
                                    fecha_str = f_inicio.strftime('%d/%m/%Y')
                                    
                                    nueva_fila = [
                                        "N", str(fecha_str), "-", str(nuevo_vehiculo).upper(), str(nueva_patente).upper(), 
                                        str(nuevo_asesor), str(nuevo_precio), str(nuevo_panos), str(nueva_obs), 
                                        str(nuevo_tiempo), str(nuevo_cliente).upper(), str(nuevo_seguro).upper(), 
                                        str(nuevo_ticket), val_recibido, val_foto, str(nueva_referencia), "" 
                                    ]
                                    
                                    hoja.append_row(nueva_fila)
                                    
                                    st.cache_data.clear()
                                    if 'memoria_turnos_v12' in st.session_state:
                                        del st.session_state['memoria_turnos_v12']
                                    
                                    st.success(f"¡Vehículo {nueva_patente.upper()} guardado exitosamente!")
                                    time.sleep(1)
                                    st.session_state.procesando_envio = False
                                    st.rerun()
                                except Exception as e:
                                    st.session_state.procesando_envio = False
                                    st.error(f"Error al guardar en Sheets: {e}")
                        else:
                            st.warning("Por favor completá Patente y Vehículo (son obligatorios).")
                    else:
                        st.error("Aguardá un momento, se está procesando el envío anterior.")

    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("<h2 style='color: #00235d; margin-top: 0;'>📥 1. INGRESOS: Recepción de Vehículos</h2>", unsafe_allow_html=True)
        st.write("Administración de turnos y vehículos programados para **entrar** al taller en las fechas seleccionadas.")
        
        # Conversión segura para evitar errores con celdas vacías
        fechas_turnos_dt = pd.to_datetime(df_turnos_display['Fecha'], errors='coerce')
        mask = (fechas_turnos_dt >= pd.to_datetime(f_inicio)) & (fechas_turnos_dt <= pd.to_datetime(f_fin))
        df_rango = df_turnos_display[mask].copy()
        if asesor_filtro != "TODOS": df_rango = df_rango[df_rango['Asesor'] == asesor_filtro]

        if df_rango.empty: 
            st.info("No hay turnos para los filtros seleccionados o la búsqueda actual.")
        else:
            df_activos = df_rango[df_rango['Cancelado'] == False]
            mascara_recibidos = ((df_activos['Ticket'].str.strip() != "") | (df_activos['Referencia'].str.strip() != "")) & (df_activos['Recibido'] == True) & (df_activos['Fotos'] == True)
            
            df_pendientes = df_activos[~mascara_recibidos].sort_values(['Fecha', 'Hora', 'Asesor'])
            df_recibidos = df_activos[mascara_recibidos].sort_values(['Fecha', 'Hora', 'Asesor'])

            st.write("#### ⏱️ Turnos Pendientes de Recepción")
            if not df_pendientes.empty:
                df_prog = df_pendientes[df_pendientes['Tipo'] == '📅 PROGRAMADO']
                df_sin = df_pendientes[df_pendientes['Tipo'] == '🚶‍♂️ SIN TURNO']
                edited_prog, edited_sin = pd.DataFrame(), pd.DataFrame()
                
                conf_columnas = {
                    "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"), 
                    "Asesor": st.column_config.SelectboxColumn("Asesor", options=ASESORES_LISTA), 
                    "Ticket": st.column_config.TextColumn("🎫 N° Ticket", max_chars=15), 
                    "Observaciones": st.column_config.TextColumn("💬 Observaciones", width="medium"), 
                    "Recibido": st.column_config.CheckboxColumn("✅ Recibido", default=False), 
                    "Fotos": st.column_config.CheckboxColumn("📸 Fotos", default=False), 
                    "Referencia": st.column_config.TextColumn("🏷️ N° Referencia", max_chars=15), 
                    "Cancelado": st.column_config.CheckboxColumn("❌ Cancelar", default=False),
                    "Motivo_Cancelacion": st.column_config.TextColumn("📝 Motivo Cancelación (Col Q)", width="medium")
                }
                
                orden_columnas = ['Fecha', 'Hora', 'Patente', 'Vehiculo', 'Cliente', 'Asesor', 'Ticket', 'Observaciones', 'Recibido', 'Fotos', 'Referencia', 'Cancelado', 'Motivo_Cancelacion']
                orden_columnas_sin = orden_columnas + ['Eliminar']
                
                if not df_prog.empty:
                    st.caption("📅 Programados (Doble clic en la celda para editar)")
                    edited_prog = st.data_editor(df_prog[orden_columnas], column_config=conf_columnas, hide_index=True, use_container_width=True, key="editor_prog")
                if not df_sin.empty:
                    st.caption("🚶‍♂️ Ingresos Adicionales (Sin Turno)")
                    # 🚨 BLINDAJE ANTI-ERRORES: Solo usa las columnas que realmente existen
                    columnas_seguras_sin = [col for col in orden_columnas_sin if col in df_sin.columns]
        
                    edited_sin = st.data_editor(df_sin[columnas_seguras_sin], column_config=conf_columnas, hide_index=True, use_container_width=True, key="editor_sin")

            if st.button("💾 Guardar Cambios e Ingresos"):
                    with st.spinner("Sincronizando con la base de datos..."):
                        patentes_sheet_raw = hoja.col_values(5) if hoja else []
                        patentes_limpias = ["".join(str(p).split()).upper() for p in patentes_sheet_raw]
                        
                        def procesar_guardado_fila(row, row_orig):
                            if (row['Fecha'] != row_orig['Fecha'] or row['Recibido'] != row_orig['Recibido'] or 
                                row['Fotos'] != row_orig['Fotos'] or str(row['Ticket']).strip() != str(row_orig['Ticket']).strip() or 
                                str(row['Referencia']).strip() != str(row_orig['Referencia']).strip() or row['Asesor'] != row_orig['Asesor'] or 
                                row['Cancelado'] != row_orig['Cancelado'] or 
                                str(row.get('Motivo_Cancelacion','')) != str(row_orig.get('Motivo_Cancelacion','')) or
                                str(row.get('Observaciones','')) != str(row_orig.get('Observaciones',''))):
                                
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
                                    except Exception as e: st.error(f"Error guardando {row['Patente']}: {e}")

                        if not edited_prog.empty:
                            for idx, row in edited_prog.iterrows(): procesar_guardado_fila(row, df_prog.loc[idx])
                                        
                        if not edited_sin.empty:
                            for idx, row in edited_sin.iterrows():
                                if row.get('Eliminar', False): 
                                    patente_buscada = "".join(str(row['Patente']).split()).upper()
                                    if hoja and patente_buscada in patentes_limpias:
                                        fila_invertida = len(patentes_limpias) - patentes_limpias[::-1].index(patente_buscada)
                                        try: hoja.delete_rows(fila_invertida)
                                        except: pass
                                else:
                                    procesar_guardado_fila(row, df_sin.loc[idx])
                                            
                        st.cache_data.clear()
                        claves_a_borrar = [k for k in st.session_state.keys() if k.startswith('memoria_turnos')]
                        for k in claves_a_borrar: del st.session_state[k]
                            
                        st.success("¡Sincronización completa!"); time.sleep(1.5); st.rerun()

            st.write("#### 🏁 Turnos Completados (Ya Recibidos)")
            if not df_recibidos.empty:
                conf_cols_recibidos = {
                    "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY", disabled=True), 
                    "Recibido": st.column_config.CheckboxColumn("✅ Recibido"), 
                    "Fotos": st.column_config.CheckboxColumn("📸 Fotos"), 
                    "Ticket": st.column_config.TextColumn("🎫 N° Ticket", max_chars=15),
                    "Referencia": st.column_config.TextColumn("🏷️ N° Ref.", max_chars=15)
                }
                edited_recibidos = st.data_editor(df_recibidos[['Tipo', 'Fecha', 'Patente', 'Vehiculo', 'Cliente', 'Asesor', 'Recibido', 'Fotos', 'Ticket', 'Referencia']], column_config=conf_cols_recibidos, hide_index=True, use_container_width=True, key="editor_recibidos")
                
                if st.button("💾 Guardar Correcciones (Completados)"):
                    with st.spinner("Actualizando planilla en la nube..."):
                        patentes_sheet_raw = hoja.col_values(5) if hoja else []
                        patentes_limpias = ["".join(str(p).split()).upper() for p in patentes_sheet_raw]
                        
                        cambios_detectados = False
                        
                        for idx, row in edited_recibidos.iterrows():
                            row_orig = df_recibidos.loc[idx]
                            
                            if (row['Recibido'] != row_orig['Recibido'] or 
                                row['Fotos'] != row_orig['Fotos'] or 
                                str(row['Ticket']).strip() != str(row_orig['Ticket']).strip() or 
                                str(row['Referencia']).strip() != str(row_orig['Referencia']).strip()):
                                
                                patente_buscada = "".join(str(row['Patente']).split()).upper()
                                cambios_detectados = True
                                
                                if hoja and patente_buscada in patentes_limpias:
                                    fila_sheet = len(patentes_limpias) - patentes_limpias[::-1].index(patente_buscada)
                                    try:
                                        hoja.update_acell(f'N{fila_sheet}', "SI" if row['Recibido'] else "")
                                        hoja.update_acell(f'O{fila_sheet}', "SI" if row['Fotos'] else "")
                                        hoja.update_acell(f'M{fila_sheet}', str(row['Ticket']) if pd.notna(row['Ticket']) else "")
                                        hoja.update_acell(f'P{fila_sheet}', str(row['Referencia']) if pd.notna(row['Referencia']) else "")
                                    except Exception as e:
                                        st.error(f"Error guardando la patente {patente_buscada}: {e}")
                                else:
                                    st.warning(f"Atención: La patente {patente_buscada} no se encontró en el Google Sheets.")
                        
                        if cambios_detectados:
                            st.cache_data.clear()
                            claves_a_borrar = [k for k in st.session_state.keys() if k.startswith('memoria_turnos')]
                            for k in claves_a_borrar: del st.session_state[k]
                                
                            st.success("¡Correcciones aplicadas y guardadas!"); time.sleep(1.5); st.rerun()
                        else:
                            st.info("No detecté cambios nuevos para guardar.")

    with st.container(border=True):
        st.markdown("<h2 style='color: #1e7e34; margin-top: 0;'>📤 2. SALIDAS: Agenda de Entregas</h2>", unsafe_allow_html=True)
        st.write("Vehículos listos para entregar al cliente en las fechas seleccionadas.")
        
        if not df.empty:
            # 🚨 FILTRO APLICADO: Solo agarramos la pestaña GRUPO (y PULIDOS)
            df_no_entregados = df[~df['Estado_Taller'].str.contains("ENTREGADO", na=False)].copy()
            df_no_entregados = df_no_entregados[df_no_entregados['Grupo'].isin(['GRUPO', 'PULIDOS'])]
            df_no_entregados = df_no_entregados[~df_no_entregados['Patente'].isin(st.session_state.entregas_confirmadas)]
            df_no_entregados['Entregado_OK'] = False
            
            # Conversión segura para fechas de promesa
            fechas_prom_dt = pd.to_datetime(df_no_entregados['Fecha_Promesa_Disp'], errors='coerce')
            entregas_rango = df_no_entregados[(fechas_prom_dt >= pd.to_datetime(f_inicio)) & (fechas_prom_dt <= pd.to_datetime(f_fin))].copy()
            entregas_atrasadas = df_no_entregados[(fechas_prom_dt.notna()) & (fechas_prom_dt < pd.to_datetime(hoy.date()))].copy()
            
            if asesor_filtro != "TODOS":
                entregas_rango = entregas_rango[entregas_rango['Asesor'] == asesor_filtro]
                entregas_atrasadas = entregas_atrasadas[entregas_atrasadas['Asesor'] == asesor_filtro]
            
            edit_rango_df = pd.DataFrame() 
            edit_atra = pd.DataFrame()
            
            st.markdown("#### 🔴 Entregas Atrasadas (Vencidas)")
            if not entregas_atrasadas.empty:
                entregas_atrasadas = entregas_atrasadas.sort_values(by='Fecha_Promesa_Disp', ascending=True)
                entregas_atrasadas['Fecha Prom.'] = entregas_atrasadas['Fecha_Promesa_Disp'].apply(lambda x: x.strftime('%d/%m/%Y'))
                entregas_atrasadas['Demora (Días)'] = entregas_atrasadas['Fecha_Promesa_Disp'].apply(lambda x: (hoy.date() - x).days if pd.notna(x) else 0)
                
                edit_atra = st.data_editor(
                    # 🚨 ELIMINAMOS LA COLUMNA 'GRUPO' DE LA LISTA DE ABAJO
                    entregas_atrasadas[['Entregado_OK', 'Demora (Días)', 'Fecha Prom.', 'Patente', 'Vehiculo', 'Asesor', 'Estado_Taller', 'Precio', 'Observaciones']], 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Entregado_OK": st.column_config.CheckboxColumn("✅ Listo", default=False),
                        "Demora (Días)": st.column_config.NumberColumn("⚠️ Demora", format="%d días"),
                        "Fecha Prom.": st.column_config.TextColumn("📅 Venció", disabled=True),
                        "Patente": st.column_config.TextColumn("Patente", disabled=True), 
                        "Vehiculo": st.column_config.TextColumn("Vehículo", disabled=True), 
                        "Asesor": st.column_config.TextColumn("Asesor", disabled=True), 
                        "Estado_Taller": st.column_config.TextColumn("Estado", disabled=True),
                        "Precio": st.column_config.NumberColumn("Monto ($)", format="$ %d", disabled=True),
                        "Observaciones": st.column_config.TextColumn("Observaciones", disabled=True)
                    },
                    key="editor_entregas_atra"
                )
            else:
                st.success("¡Excelente! No hay vehículos con la fecha de entrega atrasada.")
                
            st.divider()
            
            if f_inicio == f_fin:
                titulo_rango = f"HOY ({f_inicio.strftime('%d/%m')})" if f_inicio == hoy.date() else f"para el {f_inicio.strftime('%d/%m')}"
            else:
                titulo_rango = f"del {f_inicio.strftime('%d/%m')} al {f_fin.strftime('%d/%m')}"
                
            st.markdown(f"#### 🟢 Entregas Programadas {titulo_rango}")
            if not entregas_rango.empty:
                entregas_rango['Fecha Prom.'] = entregas_rango['Fecha_Promesa_Disp'].apply(lambda x: x.strftime('%d/%m') if pd.notna(x) else "")
                
                orden_grupos_maestro = ["GRUPO", "PULIDOS", "REPUESTOS", "TERCEROS"]
                grupos_rango_unicos = [g for g in orden_grupos_maestro if g in entregas_rango['Grupo'].unique()]
                otros_grupos = [g for g in entregas_rango['Grupo'].unique() if pd.notna(g) and g not in orden_grupos_maestro]
                grupos_rango_unicos.extend(otros_grupos)
                
                # Eliminamos las columnas divididas y lo mostramos a lo ancho
                for grupo_val in grupos_rango_unicos:
                    st.caption(f"📍 **Sector: {grupo_val}**")
                    df_g_rango = entregas_rango[entregas_rango['Grupo'] == grupo_val].sort_values(by=['Fecha_Promesa_Disp', 'Hora_Entrega'])
                    
                    edit_g = st.data_editor(
                        df_g_rango[['Entregado_OK', 'Fecha Prom.', 'Hora_Entrega', 'Patente', 'Vehiculo', 'Asesor', 'Precio', 'Observaciones']], 
                        hide_index=True, 
                        use_container_width=True,
                        column_config={
                            "Entregado_OK": st.column_config.CheckboxColumn("✅ Listo", default=False),
                            "Fecha Prom.": st.column_config.TextColumn("📅 Día", disabled=True),
                            "Hora_Entrega": st.column_config.TextColumn("⌚ Hora", disabled=True),
                            "Patente": st.column_config.TextColumn("Patente", disabled=True), 
                            "Vehiculo": st.column_config.TextColumn("Vehículo", disabled=True), 
                            "Asesor": st.column_config.TextColumn("Asesor", disabled=True),
                            "Precio": st.column_config.NumberColumn("Monto ($)", format="$ %d", disabled=True),
                            "Observaciones": st.column_config.TextColumn("Observaciones", disabled=True)
                        },
                        key=f"editor_entregas_rango_{grupo_val.replace(' ', '_')}"
                    )
                    edit_rango_df = pd.concat([edit_rango_df, edit_g])
            else:
                st.info("No hay entregas pendientes para el rango y/o asesor seleccionado.")
                    
            if not edit_rango_df.empty or not edit_atra.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Confirmar Salida de Vehículos Seleccionados", use_container_width=True):
                    nuevas_confirmadas = []
                    if not edit_rango_df.empty: nuevas_confirmadas.extend(edit_rango_df[edit_rango_df['Entregado_OK'] == True]['Patente'].tolist())
                    if not edit_atra.empty: nuevas_confirmadas.extend(edit_atra[edit_atra['Entregado_OK'] == True]['Patente'].tolist())
                    
                    if nuevas_confirmadas:
                        st.session_state.entregas_confirmadas.extend(nuevas_confirmadas)
                        st.success(f"Se registraron {len(nuevas_confirmadas)} entregas. ¡A seguir facturando!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("No marcaste ningún vehículo como entregado.")

    # --- BLOQUE: BALANCEO DE CARGA ---
    st.divider()
    st.markdown("### ⚖️ Balanceo de Carga Operativa (Mano de Obra)")
    st.write("Visualización de ingresos y entregas para evitar la saturación de principio/fin de semana y cuellos de botella.")
    
    if not df.empty:
        df_balance = df[df['Grupo'].isin(['GRUPO', 'PULIDOS'])].copy()
        df_balance['Fecha_Ingreso_Dt'] = pd.to_datetime(df_balance['Fecha_Ingreso'], errors='coerce')
        df_balance['Fecha_Promesa_Dt'] = pd.to_datetime(df_balance['Fecha_Promesa_Disp'], errors='coerce')
        
        if mes_filtro != "TODOS":
            df_balance = df_balance[(df_balance['Fecha_Promesa_Dt'].dt.month == mes_num_filtro) | (df_balance['Fecha_Ingreso_Dt'].dt.month == mes_num_filtro)]

        c_bal1, c_bal2 = st.columns(2)
        
        with c_bal1:
            dias_orden = {0: '1-Lun', 1: '2-Mar', 2: '3-Mié', 3: '4-Jue', 4: '5-Vie', 5: '6-Sáb', 6: '7-Dom'}
            ingresos = df_balance['Fecha_Ingreso_Dt'].dt.dayofweek.map(dias_orden).value_counts().reset_index()
            ingresos.columns = ['Día', 'Cantidad']
            ingresos['Movimiento'] = '📥 Recepciones'
            
            entregas = df_balance['Fecha_Promesa_Dt'].dt.dayofweek.map(dias_orden).value_counts().reset_index()
            entregas.columns = ['Día', 'Cantidad']
            entregas['Movimiento'] = '📤 Entregas'
            
            df_semana = pd.concat([ingresos, entregas]).dropna().sort_values('Día')
            df_semana['Día'] = df_semana['Día'].apply(lambda x: x.split('-')[1] if isinstance(x, str) else x)
            
            fig_sem = px.bar(df_semana, x='Día', y='Cantidad', color='Movimiento', barmode='group', 
                             title="Saturación por Día de la Semana",
                             color_discrete_map={'📥 Recepciones': '#00235d', '📤 Entregas': '#28a745'}, text_auto=True)
            fig_sem.update_layout(xaxis_title="", yaxis_title="Cant. de Vehículos", legend_title_text="")
            st.plotly_chart(fig_sem, use_container_width=True)

        with c_bal2:
            entregas_diarias = df_balance.dropna(subset=['Fecha_Promesa_Dt']).groupby('Fecha_Promesa_Dt').size().reset_index(name='Cantidad')
            if mes_filtro != "TODOS": entregas_diarias = entregas_diarias[entregas_diarias['Fecha_Promesa_Dt'].dt.month == mes_num_filtro]
                  
            fig_dia = px.bar(entregas_diarias, x='Fecha_Promesa_Dt', y='Cantidad', 
                             title="Calendario de Entregas (Pico de Fin de Mes)",
                             color_discrete_sequence=['#28a745'], text_auto=True)
            fig_dia.update_layout(xaxis_title="Fecha de Entrega", yaxis_title="Cant. de Vehículos")
            
            if not entregas_diarias.empty:
                promedio_entregas = entregas_diarias['Cantidad'].mean()
                fig_dia.add_hline(y=promedio_entregas, line_dash="dash", line_color="#dc3545", annotation_text=f"Promedio Ideal: {promedio_entregas:.1f}/día", annotation_position="top left")
                
            st.plotly_chart(fig_dia, use_container_width=True)


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

        # --- ANÁLISIS DE CARGA TOYOTA (ABC) REUBICADO ---
        st.markdown("### 📊 Análisis de Carga por Método Toyota (ABC)")
        df_abc = df_prog_filtrado[df_prog_filtrado['Estado_Taller'].str.contains("PROCESO|DETENIDO", na=False)]
        if not df_abc.empty:
            abc_stats = df_abc.groupby('Tipo_ABC').agg(Autos=('Patente', 'count'), Paños=('Paños', 'sum')).reset_index()
            
            c_abc1, c_abc2 = st.columns([2, 3])
            with c_abc1:
                st.dataframe(abc_stats, hide_index=True, use_container_width=True, column_config={"Tipo_ABC": "Categoría", "Autos": "Cant. Autos", "Paños": "Total Paños"})
                st.caption("💡 **Regla ABC:** A (1-3 paños), B (4-7 paños), C (8+ paños). Lo ideal es mantener un flujo mayoritario de A y B para evitar cuellos de botella.")
            with c_abc2:
                fig_abc = px.pie(abc_stats, names='Tipo_ABC', values='Autos', title="Distribución de Vehículos Activos", color='Tipo_ABC', color_discrete_map={'A (1-3 paños)':'#28a745', 'B (4-7 paños)':'#ffc107', 'C (8+ paños)':'#dc3545'}, hole=0.4)
                st.plotly_chart(fig_abc, use_container_width=True)
        else:
            st.info("No hay vehículos activos para el análisis ABC.")

        st.divider()

        st.markdown("### 📋 Tablero Kanban - Taller Salta")
        df_kanban = df_prog_filtrado[df_prog_filtrado['Estado_Taller'].str.contains("PROCESO|DETENIDO", na=False)].copy()
        df_kanban.loc[df_kanban['Estado_Taller'].str.contains("DETENIDO", na=False), 'Fase_Taller'] = "⛔ DETENIDOS"
        
        orden_ideal = ["SIN FASE ASIGNADA", "CHAPA", "PREPARACION", "PINTURA", "ARMADO", "⛔ DETENIDOS"]
        
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
        df_grupo = df[(df['Cliente'].str.contains('SOL|LUX|CIEL', case=False, na=False)) & (df['Grupo'].isin(['GRUPO', 'PULIDOS']))].copy()
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
            ce1.markdown(f'<div class="metric-card"><div class="metric-title">En Proceso</div><div class="metric-value-number">{en_proceso}</div><div class="metric-subtitle-blue">Vehículos en Taller</div></div>', unsafe_allow_html=True)
            ce2.markdown(f'<div class="metric-card"><div class="metric-title">Detenidos (Con Novedad)</div><div class="metric-value-number" style="color:#dc3545;">{detenidos}</div><div class="metric-subtitle-red">Revisar Observaciones</div></div>', unsafe_allow_html=True)
            ce3.markdown(f'<div class="metric-card"><div class="metric-title">Terminados (Pte. Entregar)</div><div class="metric-value-number" style="color:#28a745;">{terminados}</div><div class="metric-subtitle-green">Listos / Facturando</div></div>', unsafe_allow_html=True)
            st.divider()
            
            def calcular_fecha_entrega(row):
                f_prom = row['Fecha_Promesa_Disp']
                f_tick = row['Fecha_Ticket']
                if pd.isna(f_prom): return "Sin Fecha"
                texto_fecha = f_prom.strftime('%d/%m/%Y')
                if pd.notna(f_tick) and f_prom > f_tick: return f"{texto_fecha} 🟡 (Demorado)"
                return texto_fecha
            df_vista_emp['Fecha Entrega'] = df_vista_emp.apply(calcular_fecha_entrega, axis=1)
            
            def calcular_estado(estado):
                estado_str = str(estado).upper()
                if "DETENIDO" in estado_str: return f"🔴 {estado_str}"
                return estado_str
            df_vista_emp['Estado_Taller'] = df_vista_emp['Estado_Taller'].apply(calcular_estado)
            df_vista_emp['Fecha Ingreso'] = df_vista_emp['Fecha_Ingreso'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else "Sin Fecha")
            df_vista_emp['Fecha Ticket'] = df_vista_emp['Fecha_Ticket'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else "Sin Fecha")
            df_vista_emp['Fecha Ingreso Concesionario'] = None
            df_vista_emp['Asesor Concesionario'] = ""

            vista_columnas = ['Cliente', 'Vehiculo', 'Patente', 'Fecha Ingreso', 'Fecha Ticket', 'Estado_Taller', 'Fecha Entrega', 'Asesor', 'Fecha Ingreso Concesionario', 'Asesor Concesionario', 'Observaciones']
            mask_entregados = df_vista_emp['Estado_Taller'].str.contains('ENTREGADO', na=False)
            df_pendientes = df_vista_emp[~mask_entregados][vista_columnas].rename(columns={'Estado_Taller': 'Estado Actual'})
            df_entregados = df_vista_emp[mask_entregados][vista_columnas].rename(columns={'Estado_Taller': 'Estado Actual'})
            
            st.write("#### ⏳ Vehículos en Taller (Prioridad por Fecha Promesa)")
            st.data_editor(df_pendientes, hide_index=True, use_container_width=True, column_config={"Cliente": st.column_config.TextColumn("Cliente", disabled=True), "Vehiculo": st.column_config.TextColumn("Vehículo", disabled=True), "Patente": st.column_config.TextColumn("Patente", disabled=True), "Fecha Ingreso": st.column_config.TextColumn("Ingreso Taller", disabled=True), "Fecha Ticket": st.column_config.TextColumn("1ra Fecha Prom.", disabled=True), "Estado Actual": st.column_config.TextColumn("Estado Actual", disabled=True), "Fecha Entrega": st.column_config.TextColumn("Fecha Entrega", disabled=True), "Asesor": st.column_config.TextColumn("Asesor Taller", disabled=True), "Fecha Ingreso Concesionario": st.column_config.DateColumn("🗓️ Ingreso Conces.", format="DD/MM/YYYY"), "Asesor Concesionario": st.column_config.TextColumn("👤 Asesor Conces."), "Observaciones": st.column_config.TextColumn("📝 Observaciones (Doble Clic)", width="large", max_chars=1000)}, key="editor_observaciones_pendientes")
            st.write("#### 🚚 Vehículos Entregados (Historial Reciente)")
            st.dataframe(df_entregados, hide_index=True, use_container_width=True, column_config={"Observaciones": st.column_config.TextColumn("Observaciones", width="large")})
        else: st.info("No hay vehículos registrados para las empresas del grupo en este momento.")

# ==========================================
# PESTAÑA 4: FACTURACIÓN Y OBJETIVOS
# ==========================================
with tab_fac:
    if not df.empty:
        st.subheader("🎯 Análisis de Facturación, Paños y Objetivos")

        df_analisis = df.copy()

        # --- 1. BUSCADOR INTELIGENTE DE COLUMNAS (Anti-errores de Excel) ---
        def encontrar_columna(df_temp, palabras_clave, default):
            for c in df_temp.columns:
                c_upper = str(c).upper().strip()
                if any(p in c_upper for p in palabras_clave): return c
            return default

        col_fecha = encontrar_columna(df_analisis, ['FECHA PROM', 'PROMESA'], 'Fecha_Promesa_Disp')
        col_panos = encontrar_columna(df_analisis, ['PAÑO', 'PANOS'], 'Paños')
        col_precio = encontrar_columna(df_analisis, ['PRECIO', 'MONTO'], 'Precio')
        col_est_taller = encontrar_columna(df_analisis, ['ESTADO_TALLER', 'ESTADO TALLER'], 'Estado_Taller')
        col_est_fac = encontrar_columna(df_analisis, ['ESTADO_FAC', 'ESTADO FAC'], 'Estado_Fac')
        col_patente = encontrar_columna(df_analisis, ['PATENTE', 'DOMINIO'], 'Patente')
        col_asesor = encontrar_columna(df_analisis, ['ASESOR'], 'Asesor')
        col_cliente = encontrar_columna(df_analisis, ['CLIENTE', 'EMPRESA'], 'Cliente')
        col_costo = encontrar_columna(df_analisis, ['COSTO'], 'Costo')

        df_analisis['Fecha_Real_Dt'] = pd.to_datetime(df_analisis[col_fecha], dayfirst=True, errors='coerce')

        def limpiar_plata_general(x):
            if pd.isna(x): return 0.0
            if isinstance(x, (int, float)): return float(x)
            x = str(x).replace('$', '').replace(' ', '').replace('.', '').replace(',', '.') 
            try: return float(x)
            except: return 0.0

        def clasificar_estado(row):
            est_taller = str(row.get(col_est_taller, '')).upper()
            est_fac = str(row.get(col_est_fac, '')).upper()
            if 'DETENIDO' in est_taller: return 'En Taller (Otros)'
            if est_fac == 'FAC': return 'Facturado (FAC)'
            if est_fac == 'SI': return 'Aprobado (SI)'
            return 'En Taller (Otros)'

        df_analisis['Estado_Resumen'] = df_analisis.apply(clasificar_estado, axis=1)

        # ==========================================
        # 🚨 CIRUGÍA MAYOR: SEPARAMOS PROPIOS DE TERCEROS
        # ==========================================
        df_propios = df_analisis[df_analisis['Grupo'].astype(str).str.upper() != 'TERCEROS'].copy()
        df_terceros = df_analisis[df_analisis['Grupo'].astype(str).str.upper() == 'TERCEROS'].copy()

        # Todo el análisis principal ahora se hace SOLO sobre los Propios
        df_fac_prop = df_propios[df_propios['Estado_Resumen'] == 'Facturado (FAC)']
        df_si_prop = df_propios[df_propios['Estado_Resumen'] == 'Aprobado (SI)']

        # --- 2. CÁLCULOS SEPARADOS Y DESCUENTO DE M.O. (SOLO PROPIOS) ---
        fac_mo_bruto = df_fac_prop[col_precio].apply(limpiar_plata_general).sum() if col_precio in df_fac_prop else 0
        si_mo_bruto = df_si_prop[col_precio].apply(limpiar_plata_general).sum() if col_precio in df_si_prop else 0

        try:
            df_rep = df_repuestos.copy()
            df_rep['PRECIO_LIMPIO'] = df_rep['PRECIO'].apply(limpiar_plata_general)
            df_rep['Fecha_Dt'] = pd.to_datetime(df_rep['FECHA TALLER'], dayfirst=True, errors='coerce')
            if mes_filtro != "TODOS": df_rep = df_rep[df_rep['Fecha_Dt'].dt.month == mes_num_filtro]
            fac_rep = df_rep[df_rep['FAC'].astype(str).str.strip().str.upper() == 'FAC']['PRECIO_LIMPIO'].sum()
            si_rep = df_rep[df_rep['FAC'].astype(str).str.strip().str.upper() == 'SI']['PRECIO_LIMPIO'].sum()
        except:
            fac_rep, si_rep = 0, 0

        fac_mo = max(0, fac_mo_bruto - fac_rep)
        si_mo = max(0, si_mo_bruto - si_rep)

        pesos_fac, pesos_si = fac_mo + fac_rep, si_mo + si_rep
        pesos_est = pesos_fac + pesos_si

        panos_fac_prop = df_fac_prop[col_panos].apply(lambda x: pd.to_numeric(x, errors='coerce')).sum() if col_panos in df_fac_prop else 0
        panos_si_prop = df_si_prop[col_panos].apply(lambda x: pd.to_numeric(x, errors='coerce')).sum() if col_panos in df_si_prop else 0
        panos_est_prop = panos_fac_prop + panos_si_prop

        # --- 3. CÁLCULOS DE OBJETIVOS (SOLO CON PAÑOS PROPIOS) ---
        porcentaje_logro = min((panos_est_prop / OBJETIVO_MENSUAL_PANOS) * 100 if OBJETIVO_MENSUAL_PANOS > 0 else 0, 100)
        dias_restantes = dias_restantes_calc
        panos_faltantes = max(0, OBJETIVO_MENSUAL_PANOS - panos_est_prop)
        ritmo_diario_necesario = panos_faltantes / dias_restantes if dias_restantes > 0 else 0

        st.markdown("### 🎯 Control de Objetivo Mensual")
        c_obj1, c_obj2 = st.columns([3, 1])
        with c_obj1:
            st.progress(int(porcentaje_logro))
            st.caption(f"**Progreso del Mes:** {panos_est_prop:.1f} paños propios de un objetivo de {OBJETIVO_MENSUAL_PANOS} paños.")
        with c_obj2:
            st.markdown(f"<h3 style='text-align: right; color: {'#28a745' if porcentaje_logro >= 95 else '#ffc107' if porcentaje_logro >= 75 else '#dc3545'}; margin-top: 0;'>{porcentaje_logro:.1f}%</h3>", unsafe_allow_html=True)
        st.info(f"⏱️ **Termómetro de Ritmo:** Faltan **{panos_faltantes:.1f} paños propios** y quedan **{dias_restantes} días hábiles**. Para llegar a la meta, el taller interno debe sacar **{ritmo_diario_necesario:.1f} paños por día**.")

        st.write("### 💰 Rendimiento y Proyección al Cierre (Producción Interna)")
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.markdown(f'<div class="metric-card" style="border-left: 5px solid #28a745;"><div class="metric-title" style="color: #28a745;">Facturado Actual (FAC)</div><div class="metric-value-money" style="color: #28a745;">{formato_pesos(pesos_fac)}</div><div style="font-size: 0.85em; color: gray;">M.O.: {formato_pesos(fac_mo)} | Rep: {formato_pesos(fac_rep)}</div><div class="metric-subtitle-gray" style="font-size: 1.1rem; margin-top: 8px;">📦 {panos_fac_prop:.1f} paños propios</div></div>', unsafe_allow_html=True)
        c_r2.markdown(f'<div class="metric-card" style="border-left: 5px solid #17a2b8;"><div class="metric-title" style="color: #17a2b8;">Aprobado (SI)</div><div class="metric-value-money" style="color:#17a2b8;">{formato_pesos(pesos_si)}</div><div style="font-size: 0.85em; color: gray;">M.O.: {formato_pesos(si_mo)} | Rep: {formato_pesos(si_rep)}</div><div class="metric-subtitle-green" style="font-size: 1.1rem; color: #17a2b8; margin-top: 8px;">📦 {panos_si_prop:.1f} paños propios</div></div>', unsafe_allow_html=True)
        c_r3.markdown(f'<div class="metric-card" style="border-left: 5px solid #00235d;"><div class="metric-title" style="color:#00235d;">Estimado a Cierre de Mes</div><div class="metric-value-money" style="color:#00235d;">{formato_pesos(pesos_est)}</div><div style="font-size: 0.85em; color: gray;">M.O.: {formato_pesos(fac_mo + si_mo)} | Rep: {formato_pesos(fac_rep + si_rep)}</div><div class="metric-subtitle-gray" style="font-size: 1.1rem; color:#00235d; font-weight: bold; margin-top: 8px;">📦 {panos_est_prop:.1f} paños propios</div></div>', unsafe_allow_html=True)

        # ==========================================
        # --- GESTIÓN DE TERCEROS Y GRAN TOTAL ---
        # ==========================================
        st.divider() # Línea divisoria bien pegadita a lo de arriba
        st.markdown("<h3 style='margin-top: -15px;'>🤝 Gestión Financiera de Terceros</h3>", unsafe_allow_html=True)
        
        # Filtramos por estado para el desglose
        df_ter_fac = df_terceros[df_terceros['Estado_Resumen'] == 'Facturado (FAC)'].copy()
        df_ter_si = df_terceros[df_terceros['Estado_Resumen'] == 'Aprobado (SI)'].copy()
        
        # Cálculos de Ventas (Precios)
        v_fac_ter = df_ter_fac[col_precio].apply(limpiar_plata_general).sum() if not df_ter_fac.empty else 0
        v_si_ter = df_ter_si[col_precio].apply(limpiar_plata_general).sum() if not df_ter_si.empty else 0
        
        # Cálculos de Costos
        c_fac_ter = df_ter_fac[col_costo].apply(limpiar_plata_general).sum() if not df_ter_fac.empty else 0
        c_si_ter = df_ter_si[col_costo].apply(limpiar_plata_general).sum() if not df_ter_si.empty else 0
        
        # Cálculos de Paños
        p_fac_ter = df_ter_fac[col_panos].apply(pd.to_numeric, errors='coerce').sum() if not df_ter_fac.empty else 0
        p_si_ter = df_ter_si[col_panos].apply(pd.to_numeric, errors='coerce').sum() if not df_ter_si.empty else 0

        # Totales Generales (La suma de ambos)
        tot_ter_fac = v_fac_ter + v_si_ter
        tot_ter_costo = c_fac_ter + c_si_ter
        tot_ter_margen = tot_ter_fac - tot_ter_costo
        tot_ter_panos = p_fac_ter + p_si_ter
        
        if tot_ter_fac > 0 or tot_ter_panos > 0:
            c_t1, c_t2, c_t3, c_t4 = st.columns(4)
            
            # Tarjeta Venta
            c_t1.markdown(f'''
                <div class="metric-card">
                    <div class="metric-title">Total Venta (Terceros)</div>
                    <div class="metric-value-money" style="font-size: 1.5rem;">{formato_pesos(tot_ter_fac)}</div>
                    <div style="font-size: 0.8em; color: gray;">FAC: {formato_pesos(v_fac_ter)} | SI: {formato_pesos(v_si_ter)}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            # Tarjeta Costo
            c_t2.markdown(f'''
                <div class="metric-card">
                    <div class="metric-title">Costo Total</div>
                    <div class="metric-value-money" style="color:#dc3545; font-size: 1.5rem;">{formato_pesos(tot_ter_costo)}</div>
                    <div style="font-size: 0.8em; color: gray;">FAC: {formato_pesos(c_fac_ter)} | SI: {formato_pesos(c_si_ter)}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            # Tarjeta Margen
            c_t3.markdown(f'''
                <div class="metric-card">
                    <div class="metric-title">Margen de Ganancia</div>
                    <div class="metric-value-money" style="color:#28a745; font-size: 1.5rem;">{formato_pesos(tot_ter_margen)}</div>
                    <div style="font-size: 0.8em; color: gray;">Rentabilidad de Terceros</div>
                </div>
            ''', unsafe_allow_html=True)
            
            # Tarjeta Paños
            c_t4.markdown(f'''
                <div class="metric-card">
                    <div class="metric-title">Paños de Terceros</div>
                    <div class="metric-value-number" style="font-size: 1.5rem; color:#6f42c1;">{tot_ter_panos:.1f}</div>
                    <div style="font-size: 0.8em; color: gray;">FAC: {p_fac_ter:.1f} | SI: {p_si_ter:.1f}</div>
                </div>
            ''', unsafe_allow_html=True)
        else:
            st.info("No hay datos de Terceros para el período seleccionado.")
            
        # 📈 EL GRAN TOTAL DE PAÑOS 📈
        gran_total_panos = panos_est_prop + tot_ter_panos
        st.markdown(f"<div style='text-align: right; color: #00235d; font-size: 1.1rem; margin-top: 5px; margin-bottom: -10px;'><strong>📈 Gran Total de Producción (Propios + Terceros):</strong> {gran_total_panos:.1f} paños</div>", unsafe_allow_html=True)
        
        # ==========================================
        # 🚨 TARJETAS DE ALERTA: PENDIENTES DE FACTURACIÓN
        # ==========================================
        st.divider() # La línea nueva que pediste para separar la gestión administrativa
        st.markdown("<h3 style='margin-top: -15px;'>⚠️ Pendientes de Gestión Administrativa</h3>", unsafe_allow_html=True)
        
        # Filtramos estados críticos
        df_pte_entregar = df_analisis[df_analisis[col_est_taller].str.contains('TERM PEND ENTREG', na=False)].copy()
        df_pte_factura = df_analisis[df_analisis[col_est_taller].str.contains('TERM PEND FACT|ENTREGADO PEND FACT', na=False)].copy()
        
        # Calculamos montos y paños para Tarjeta 1
        monto_pte_entregar = df_pte_entregar[col_precio].apply(limpiar_plata_general).sum() if col_precio in df_pte_entregar.columns else 0
        panos_pte_entregar = df_pte_entregar[col_panos].apply(pd.to_numeric, errors='coerce').sum() if col_panos in df_pte_entregar.columns else 0

        # Calculamos montos y paños para Tarjeta 2
        df_t_f = df_pte_factura[df_pte_factura[col_est_taller].str.contains('TERM', na=False)]
        monto_t_f = df_t_f[col_precio].apply(limpiar_plata_general).sum() if col_precio in df_t_f.columns else 0
        panos_t_f = df_t_f[col_panos].apply(pd.to_numeric, errors='coerce').sum() if col_panos in df_t_f.columns else 0

        # Calculamos montos y paños para Tarjeta 3
        df_e_f = df_pte_factura[df_pte_factura[col_est_taller].str.contains('ENTREGADO', na=False)]
        monto_e_f = df_e_f[col_precio].apply(limpiar_plata_general).sum() if col_precio in df_e_f.columns else 0
        panos_e_f = df_e_f[col_panos].apply(pd.to_numeric, errors='coerce').sum() if col_panos in df_e_f.columns else 0

        # Calculamos Repuestos Pendientes (Solo Salta) - BLINDADO
        cant_rep_pte = 0
        monto_rep_pte = 0.0
        try:
            if 'df_repuestos' in globals() and not df_repuestos.empty:
                col_fac_r = encontrar_columna(df_repuestos, ['FAC', 'ESTADO'], 'FAC')
                col_pre_r = encontrar_columna(df_repuestos, ['PRECIO', 'MONTO'], 'PRECIO')
                
                df_rep_pte = df_repuestos[df_repuestos[col_fac_r].astype(str).str.strip().str.upper() == 'SI'].copy()
                cant_rep_pte = len(df_rep_pte)
                
                if col_pre_r in df_rep_pte.columns:
                    precios = df_rep_pte[col_pre_r]
                    if isinstance(precios, pd.DataFrame): 
                        precios = precios.iloc[:, 0]
                    monto_rep_pte = float(precios.apply(limpiar_plata_general).sum())
        except Exception as e:
            pass

        c_alt1, c_alt2, c_alt3, c_alt4 = st.columns(4)
        
        # Tarjeta 1: Terminados sin entregar
        c_alt1.markdown(f'''
            <div class="metric-card" style="border-left: 5px solid #ffc107;">
                <div class="metric-title">Terminados Pte. Entrega</div>
                <div class="metric-value-number" style="color:#856404;">{len(df_pte_entregar)} autos</div>
                <div style="font-weight: bold; color: #6c757d; font-size: 1.1rem; margin-top: 5px;">{formato_pesos(monto_pte_entregar)}</div>
                <div class="metric-subtitle-purple" style="margin-top: 2px;">{panos_pte_entregar:.1f} paños</div>
            </div>
        ''', unsafe_allow_html=True)

        # Tarjeta 2: Terminados sin facturar
        c_alt2.markdown(f'''
            <div class="metric-card" style="border-left: 5px solid #dc3545;">
                <div class="metric-title">Terminados Pte. Factura</div>
                <div class="metric-value-number" style="color:#721c24;">{len(df_t_f)} autos</div>
                <div style="font-weight: bold; color: #6c757d; font-size: 1.1rem; margin-top: 5px;">{formato_pesos(monto_t_f)}</div>
                <div class="metric-subtitle-red" style="margin-top: 2px;">{panos_t_f:.1f} paños</div>
            </div>
        ''', unsafe_allow_html=True)

        # Tarjeta 3: Entregados sin facturar
        c_alt3.markdown(f'''
            <div class="metric-card" style="border-left: 5px solid #6f42c1;">
                <div class="metric-title">Entregados Pte. Factura</div>
                <div class="metric-value-number" style="color:#4b2354;">{len(df_e_f)} autos</div>
                <div style="font-weight: bold; color: #6c757d; font-size: 1.1rem; margin-top: 5px;">{formato_pesos(monto_e_f)}</div>
                <div class="metric-subtitle-purple" style="margin-top: 2px;">{panos_e_f:.1f} paños</div>
            </div>
        ''', unsafe_allow_html=True)

        # Tarjeta 4: Repuestos Pendientes (Salta Especial)
        c_alt4.markdown(f'''
            <div class="metric-card" style="border-left: 5px solid #17a2b8;">
                <div class="metric-title">Repuestos Pte. Factura</div>
                <div class="metric-value-number" style="color:#0c5460;">{cant_rep_pte} pedidos</div>
                <div style="font-weight: bold; color: #17a2b8; font-size: 1.1rem; margin-top: 5px;">{formato_pesos(monto_rep_pte)}</div>
            </div>
        ''', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        with st.expander("🔍 Radiografía del Aprobado Propios (¿Dónde está la plata del 'SI'?)", expanded=True):
            df_si_detail = df_si_prop.copy()
            def status_si(row):
                est = str(row.get(col_est_taller, '')).upper()
                f_prom = row.get('Fecha_Real_Dt')
                if 'ENTREGADO' in est: return '1. 🚚 Entregados (Pendiente Facturar)'
                if 'TERM PEND ENTREG' in est: return '2. ⏳ Terminados (Pendiente Entregar)'
                if 'TERM' in est: return '3. ⚠️ Terminados (Pendiente Facturar)'
                if pd.notna(f_prom) and f_prom.date() < hoy.date(): return '5. 🔴 Atrasados en Producción'
                return '4. 🟢 En Taller (A tiempo)'

            df_si_detail['Categoría_Real'] = df_si_detail.apply(status_si, axis=1)
            resumen_si_cat = df_si_detail.groupby('Categoría_Real').agg(Vehículos=(col_patente, 'count') if col_patente in df_si_detail else ('Categoría_Real', 'count'), Paños=(col_panos, lambda x: pd.to_numeric(x, errors='coerce').sum()) if col_panos in df_si_detail else ('Categoría_Real', 'count'), MO=(col_precio, lambda x: x.apply(limpiar_plata_general).sum()) if col_precio in df_si_detail else ('Categoría_Real', 'count')).reset_index().sort_values('Categoría_Real')
            resumen_si_cat['M.O. ($)'] = resumen_si_cat['MO'].apply(formato_pesos)
            st.dataframe(resumen_si_cat[['Categoría_Real', 'Vehículos', 'Paños', 'M.O. ($)']], hide_index=True, use_container_width=True)

        st.divider()
        
        # ==========================================
        # 🔭 RADAR DEL MES SIGUIENTE (ESTADO 'NO')
        # ==========================================
        st.markdown("<br>", unsafe_allow_html=True) # Espacio limpio sin líneas feas
        st.markdown("### 🔭 Radar del Mes Siguiente (Estado 'NO')")
        st.write("Vehículos marcados con estado **'NO'** en la facturación. Esto representa el colchón de trabajo/plata que se patea y asegura para arrancar el próximo mes.")
        
        # Filtramos los que dicen "NO" en la columna de Facturación de tu hoja principal
        df_radar_no = df_analisis[df_analisis[col_est_fac].astype(str).str.strip().str.upper() == 'NO'].copy()
        
        cant_autos_no = len(df_radar_no)
        panos_no = df_radar_no[col_panos].apply(lambda x: pd.to_numeric(x, errors='coerce')).fillna(0).sum() if col_panos in df_radar_no else 0
        plata_no = df_radar_no[col_precio].apply(limpiar_plata_general).sum() if col_precio in df_radar_no else 0
        
        c_rn1, c_rn2, c_rn3 = st.columns(3)
        
        c_rn1.markdown(f'''
            <div class="metric-card" style="border: 1px solid #e0e0e0; box-shadow: none;">
                <div class="metric-title" style="text-align: center; color: gray; font-size: 0.85rem;">AUTOS PARA PRÓX. MES</div>
                <div class="metric-value-number" style="color:#6f42c1; text-align: center;">{cant_autos_no}</div>
            </div>
        ''', unsafe_allow_html=True)
        
        c_rn2.markdown(f'''
            <div class="metric-card" style="border: 1px solid #e0e0e0; box-shadow: none;">
                <div class="metric-title" style="text-align: center; color: gray; font-size: 0.85rem;">PAÑOS ASEGURADOS</div>
                <div class="metric-value-number" style="color:#6f42c1; text-align: center;">{panos_no:.1f}</div>
            </div>
        ''', unsafe_allow_html=True)
        
        c_rn3.markdown(f'''
            <div class="metric-card" style="border: 1px solid #e0e0e0; box-shadow: none;">
                <div class="metric-title" style="text-align: center; color: gray; font-size: 0.85rem;">PLATA PROYECTADA</div>
                <div class="metric-value-money" style="color:#6f42c1; text-align: center;">{formato_pesos(plata_no)}</div>
            </div>
        ''', unsafe_allow_html=True)
        
        if cant_autos_no > 0:
            with st.expander(" > Ver detalle de los autos marcados con 'NO'"):
                # Buscamos columnas seguras para mostrar en la tablita desplegable
                cols_mostrar = [c for c in [col_patente, 'Vehiculo', col_asesor, col_est_taller, col_panos, col_precio] if c in df_radar_no.columns]
                
                # Le damos formato a la tabla para que el precio se vea lindo
                st.dataframe(
                    df_radar_no[cols_mostrar], 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        col_precio: st.column_config.NumberColumn("Precio ($)", format="$ %d")
                    }
                )

        st.divider()

        # --- CURVAS (Construidas SOLO con producción propia) ---
        if mes_filtro != "TODOS":
            st.markdown("### 📈 Curva de Producción y Facturación del Mes (Producción Propia)")
            primer_dia = date(año_filtro, mes_num_filtro, 1)
            _, ult_dia = calendar.monthrange(año_filtro, mes_num_filtro)
            fechas_mes = [date(año_filtro, mes_num_filtro, d) for d in range(1, ult_dia + 1)]

            df_dias = pd.DataFrame({'Fecha': fechas_mes})
            df_dias['Es_Habil'] = df_dias['Fecha'].apply(lambda x: x.weekday() < 5 and x not in FERIADOS_ARG)
            df_habiles = df_dias[df_dias['Es_Habil']].copy()
            df_habiles['Dia_Habil_Num'] = range(1, len(df_habiles) + 1)
            df_habiles['Meta Lineal (Paños)'] = df_habiles['Dia_Habil_Num'] * CAPACIDAD_DIARIA_TALLER

            df_proyeccion = df_propios[df_propios['Estado_Resumen'].isin(['Facturado (FAC)', 'Aprobado (SI)'])].copy()

            def asignar_fecha_curva(row):
                f = row['Fecha_Real_Dt']
                if pd.isna(f) or f.month != mes_num_filtro or f.year != año_filtro: return hoy.date() if hoy.month == mes_num_filtro else primer_dia
                return f.date()

            df_proyeccion['Fecha_Curva'] = df_proyeccion.apply(asignar_fecha_curva, axis=1)
            df_proyeccion['Es_Hecho'] = df_proyeccion[col_est_taller].astype(str).str.contains('ENTREGADO|TERM', na=False) | (df_proyeccion['Estado_Resumen'] == 'Facturado (FAC)')

            agrupado = df_proyeccion.groupby('Fecha_Curva').agg(Paños_Esperados=(col_panos, lambda x: pd.to_numeric(x, errors='coerce').sum())).reset_index() if col_panos in df_proyeccion else pd.DataFrame(columns=['Fecha_Curva', 'Paños_Esperados'])
            agrupado_hecho = df_proyeccion[df_proyeccion['Es_Hecho']].groupby('Fecha_Curva').agg(Paños_Hechos=(col_panos, lambda x: pd.to_numeric(x, errors='coerce').sum())).reset_index() if col_panos in df_proyeccion else pd.DataFrame(columns=['Fecha_Curva', 'Paños_Hechos'])

            df_habiles = df_habiles.merge(agrupado, left_on='Fecha', right_on='Fecha_Curva', how='left').fillna(0)
            df_habiles = df_habiles.merge(agrupado_hecho, left_on='Fecha', right_on='Fecha_Curva', how='left').fillna(0)

            df_habiles['1. Proyección Esperada (SI+FAC)'] = df_habiles['Paños_Esperados'].cumsum() if 'Paños_Esperados' in df_habiles else 0
            df_habiles['2. Avance Real Hecho'] = df_habiles['Paños_Hechos'].cumsum() if 'Paños_Hechos' in df_habiles else 0
            df_habiles.loc[df_habiles['Fecha'] > hoy.date(), '2. Avance Real Hecho'] = None

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_habiles['Fecha'], y=df_habiles['Meta Lineal (Paños)'], name='Meta Exigida', mode='lines', line=dict(color='gray', dash='dash', width=2)))
            fig.add_trace(go.Scatter(x=df_habiles['Fecha'], y=df_habiles['1. Proyección Esperada (SI+FAC)'], name='Proyección Ideal', mode='lines+markers', line=dict(color='#00A8E8', width=2)))
            fig.add_trace(go.Scatter(x=df_habiles['Fecha'], y=df_habiles['2. Avance Real Hecho'], name='Avance Real', mode='lines+markers', line=dict(color='#28a745', width=4)))

            fig.update_layout(title="Curva de Acumulación de Trabajo (Solo Propios)", xaxis_title="Días Hábiles", yaxis_title="Cantidad de Paños", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # --- ANÁLISIS DETALLADO ESTILO JUJUY ---
        st.write("### 📊 Análisis de Producción Detallado")

        def crear_tabla_resumen(df_origen, columna_indice):
            df_temp = df_origen.copy()
            df_temp['Valor_Plata'] = df_temp[col_precio].apply(limpiar_plata_general)
            df_temp['Valor_Panos'] = df_temp[col_panos].apply(lambda x: pd.to_numeric(x, errors='coerce')).fillna(0)

            pivot = df_temp.pivot_table(index=columna_indice, columns='Estado_Resumen', values=['Valor_Panos', 'Valor_Plata'], aggfunc='sum', fill_value=0)

            for est in ['Facturado (FAC)', 'Aprobado (SI)', 'En Taller (Otros)']:
                if ('Valor_Panos', est) not in pivot.columns: pivot[('Valor_Panos', est)] = 0
                if ('Valor_Plata', est) not in pivot.columns: pivot[('Valor_Plata', est)] = 0

            df_res = pd.DataFrame(index=pivot.index)
            df_res['📦 FAC'] = pivot[('Valor_Panos', 'Facturado (FAC)')]
            df_res['📦 SI'] = pivot[('Valor_Panos', 'Aprobado (SI)')]
            df_res['📦 EST. CIERRE (FAC+SI)'] = df_res['📦 FAC'] + df_res['📦 SI']
            df_res['📦 OTROS (En Taller)'] = pivot[('Valor_Panos', 'En Taller (Otros)')]

            df_res['💰 FAC'] = pivot[('Valor_Plata', 'Facturado (FAC)')]
            df_res['💰 SI'] = pivot[('Valor_Plata', 'Aprobado (SI)')]
            df_res['💰 EST. CIERRE (FAC+SI)'] = df_res['💰 FAC'] + df_res['💰 SI']
            df_res['💰 OTROS (En Taller)'] = pivot[('Valor_Plata', 'En Taller (Otros)')]

            return df_res.sort_values(by='📦 EST. CIERRE (FAC+SI)', ascending=False)

        colores_grafico = {'Facturado': '#28a745', 'Aprobado (SI)': '#adb5bd', 'Proyección al Cierre': '#00A8E8'}
        tab_grupos, tab_asesores, tab_empresas, tab_rep = st.tabs(["👥 Producción por Grupo", "👔 Producción por Asesor", "🏢 Estimado Cierre por Empresa", "⚙️ Repuestos"])

        def render_graficos_y_tabla(tabla_resumen, col_agrupador, titulo_panos, titulo_plata):
            df_panos_chart = tabla_resumen.reset_index()[[col_agrupador, '📦 FAC', '📦 SI', '📦 EST. CIERRE (FAC+SI)']].melt(id_vars=col_agrupador, var_name='Métrica', value_name='Paños')
            df_panos_chart['Métrica'] = df_panos_chart['Métrica'].replace({'📦 FAC': 'Facturado', '📦 SI': 'Aprobado (SI)', '📦 EST. CIERRE (FAC+SI)': 'Proyección al Cierre'})
            
            df_pesos_chart = tabla_resumen.reset_index()[[col_agrupador, '💰 FAC', '💰 SI', '💰 EST. CIERRE (FAC+SI)']].melt(id_vars=col_agrupador, var_name='Métrica', value_name='Precio')
            df_pesos_chart['Métrica'] = df_pesos_chart['Métrica'].replace({'💰 FAC': 'Facturado', '💰 SI': 'Aprobado (SI)', '💰 EST. CIERRE (FAC+SI)': 'Proyección al Cierre'})

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                fig_panos = px.bar(df_panos_chart, x=col_agrupador, y='Paños', color='Métrica', barmode='group', text_auto='.1f', title=titulo_panos, color_discrete_map=colores_grafico)
                fig_panos.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), legend_title_text='')
                st.plotly_chart(fig_panos, use_container_width=True)
            with col_g2:
                fig_pesos = px.bar(df_pesos_chart, x=col_agrupador, y='Precio', color='Métrica', barmode='group', text_auto='$.2s', title=titulo_plata, color_discrete_map=colores_grafico)
                fig_pesos.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), legend_title_text='')
                st.plotly_chart(fig_pesos, use_container_width=True)

            col_p1, col_p2 = st.columns(2)
            df_pie = tabla_resumen.reset_index()
            with col_p1:
                df_panos_pie = df_pie[df_pie['📦 EST. CIERRE (FAC+SI)'] > 0]
                if not df_panos_pie.empty: st.plotly_chart(px.pie(df_panos_pie, values='📦 EST. CIERRE (FAC+SI)', names=col_agrupador, hole=0.4, title='Distribución de Paños Totales'), use_container_width=True)
            with col_p2:
                df_pesos_pie = df_pie[df_pie['💰 EST. CIERRE (FAC+SI)'] > 0]
                if not df_pesos_pie.empty: st.plotly_chart(px.pie(df_pesos_pie, values='💰 EST. CIERRE (FAC+SI)', names=col_agrupador, hole=0.4, title='Distribución de Ingresos Totales ($)'), use_container_width=True)

            dict_formato_tablas = {c: formato_pesos for c in tabla_resumen.columns if '💰' in c}
            dict_formato_tablas.update({c: "{:.1f}" for c in tabla_resumen.columns if '📦' in c})
            st.dataframe(tabla_resumen.style.format(dict_formato_tablas), use_container_width=True)

        with tab_grupos:
            # Mandamos df_propios en vez de df_analisis para no mezclar Terceros en las tablas
            tabla_grupo = crear_tabla_resumen(df_propios, 'Grupo')
            render_graficos_y_tabla(tabla_grupo, 'Grupo', '📦 Paños Propios por Grupo', '💰 Montos por Grupo')

        with tab_asesores:
            if col_asesor in df_propios.columns:
                df_asesores_limpio = df_propios[df_propios[col_asesor].astype(str).str.strip().str.upper() != 'SIN ASIGNAR'].copy()
                tabla_asesor = crear_tabla_resumen(df_asesores_limpio, col_asesor)
                render_graficos_y_tabla(tabla_asesor, col_asesor, '📦 Paños Propios por Asesor', '💰 Montos por Asesor')

        with tab_empresas:
            if col_cliente in df_propios.columns:
                tabla_empresa = crear_tabla_resumen(df_propios, col_cliente)
                render_graficos_y_tabla(tabla_empresa, col_cliente, '📦 Paños Propios por Empresa', '💰 Montos por Empresa')

        with tab_rep:
            st.write("**Detalle de Costos de Repuestos (FAC + SI)**")
            try:
                df_rep_tab = df_rep[df_rep['FAC'].astype(str).str.strip().str.upper().isin(['FAC', 'SI'])]
                df_rep_tab = df_rep_tab[df_rep_tab['PRECIO_LIMPIO'] > 0]
                if not df_rep_tab.empty:
                    cols_rep = ['PATENTE', 'ASESOR', 'PRECIO_LIMPIO', 'FAC']
                    cols_rep = [c for c in cols_rep if c in df_rep_tab.columns]
                    df_rep_disp = df_rep_tab[cols_rep].sort_values('PRECIO_LIMPIO', ascending=False)
                    st.dataframe(df_rep_disp, hide_index=True, use_container_width=True, column_config={"PRECIO_LIMPIO": st.column_config.NumberColumn("Monto Fac ($)", format="$ %d")})
                else:
                    st.info("No hay repuestos facturados o aprobados en este período.")
            except:
                st.info("Conectá correctamente la pestaña de REPUESTOS para ver el detalle.")

        # --- AUDITORÍA DE DATOS DETALLADA (Con exclusión de Repuestos) ---
        st.divider()
        st.markdown("### 🚨 Auditoría de Carga (Detectores de Errores)")
        st.write("Vehículos que requieren corrección manual en el Google Sheets por datos faltantes o mal cargados.")
        
        if col_precio in df.columns and col_panos in df.columns:
            df_temp = df.copy()
            df_temp['Precio_Num'] = df_temp[col_precio].apply(limpiar_plata_general)
            df_temp['Panos_Num'] = df_temp[col_panos].apply(lambda x: pd.to_numeric(x, errors='coerce')).fillna(0)
            
            # 1. Error de Precio
            errores_precio = df_temp[(df_temp[col_est_fac].isin(['FAC', 'SI'])) & (df_temp['Precio_Num'] <= 0)]
            
            # 2. Error de Paños (EXCLUYENDO REPUESTOS)
            condicion_no_entregado = ~df_temp[col_est_taller].astype(str).str.upper().str.contains("ENTREGADO", na=False)
            condicion_cero_panos = df_temp['Panos_Num'] <= 0
            condicion_no_es_repuesto = df_temp['Grupo'].astype(str).str.upper() != 'REPUESTOS'
            
            errores_panos = df_temp[condicion_no_entregado & condicion_cero_panos & condicion_no_es_repuesto]
            
            alertas = []
            for _, row in errores_precio.iterrows():
                alertas.append({"Dominio": row[col_patente], "Error": "💰 Falta Precio (o tiene letras)", "Grupo": row['Grupo'], "Asesor": row[col_asesor]})
            for _, row in errores_panos.iterrows():
                alertas.append({"Dominio": row[col_patente], "Error": "📦 Faltan Paños (o tiene letras)", "Grupo": row['Grupo'], "Asesor": row[col_asesor]})
                
            if alertas:
                df_alertas = pd.DataFrame(alertas)
                st.error(f"⚠️ Se detectaron {len(df_alertas)} errores de carga en la planilla.")
                st.dataframe(
                    df_alertas, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Dominio": st.column_config.TextColumn("Patente", width="small"),
                        "Error": st.column_config.TextColumn("Tipo de Error", width="large"),
                        "Grupo": st.column_config.TextColumn("Sector"),
                        "Asesor": st.column_config.TextColumn("Responsable")
                    }
                )
            else:
                st.success("✅ ¡Planilla impecable! No se detectaron errores de carga de datos de paños o precios.")
                
# ==========================================
# PESTAÑA 5: KPIs
# ==========================================
with tab_kpi:
    if not df.empty:
        st.subheader("📊 Panel de Control y KPIs del Taller (Mano de Obra)")
        
        with st.container(border=True):
            st.markdown("#### 🏷️ Parámetros de Referencia")
            c_ref1, c_ref2, c_ref3 = st.columns([1, 1, 2])
            with c_ref1:
                precio_base_iva = st.number_input("Precio Paño Seguro (Con IVA)", value=192000.0, step=1000.0)
            with c_ref2:
                valor_ref_neto = precio_base_iva / 1.21
                st.markdown(f'<div class="metric-card" style="min-height: 80px; padding: 10px; margin-bottom: 0;"><div class="metric-title">Valor Neto Objetivo (Sin IVA)</div><div class="metric-value-money" style="font-size: 1.4rem; color: #6f42c1;">{formato_pesos(valor_ref_neto)}</div></div>', unsafe_allow_html=True)
            with c_ref3:
                st.caption("Todo lo que se venda por debajo de este promedio indica pérdida de rentabilidad frente al acuerdo. Lo que esté por encima es ganancia extra o venta de mayor margen.")

        df_kpi = df[(df['Precio'] > 0) & (df['Paños'] > 0) & (df['Grupo'].isin(['GRUPO', 'PULIDOS']))].copy()
        
        if not df_kpi.empty:
            st.markdown("### 📈 Indicadores Globales del Período")
            ticket_promedio_global = df_kpi['Precio'].sum() / len(df_kpi)
            intensidad_global = df_kpi['Paños'].sum() / len(df_kpi)
            precio_prom_pano_global = df_kpi['Precio'].sum() / df_kpi['Paños'].sum()
            brecha_global = precio_prom_pano_global - valor_ref_neto

            c_g1, c_g2, c_g3, c_g4 = st.columns(4)
            color_brecha = "#28a745" if brecha_global >= 0 else "#dc3545"
            signo_brecha = "+" if brecha_global >= 0 else ""

            c_g1.markdown(f'<div class="metric-card"><div class="metric-title">Precio Prom. Real x Paño</div><div class="metric-value-money">{formato_pesos(precio_prom_pano_global)}</div><div style="color:{color_brecha}; font-weight:bold; font-size:0.9rem; margin-top:5px;">{signo_brecha}{formato_pesos(brecha_global)} vs Seguro</div></div>', unsafe_allow_html=True)
            c_g2.markdown(f'<div class="metric-card"><div class="metric-title">Ticket Promedio ($/Auto)</div><div class="metric-value-money" style="color:#00235d;">{formato_pesos(ticket_promedio_global)}</div></div>', unsafe_allow_html=True)
            c_g3.markdown(f'<div class="metric-card"><div class="metric-title">Intensidad (Paños/Auto)</div><div class="metric-value-number" style="color:#17a2b8;">{intensidad_global:.2f}</div></div>', unsafe_allow_html=True)
            c_g4.markdown(f'<div class="metric-card"><div class="metric-title">Volumen (Autos Computados)</div><div class="metric-value-number" style="color:#6c757d;">{len(df_kpi)}</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            def formato_alerta(val):
                if pd.isna(val): return ""
                if val < 0: return f"🔴 -$ {abs(val):,.0f}".replace(',', '.')
                else: return f"🟢 +$ {abs(val):,.0f}".replace(',', '.')

            kpi_asesor = df_kpi.groupby('Asesor').agg(Autos=('Patente', 'count'), Paños_Totales=('Paños', 'sum'), Facturación_Total=('Precio', 'sum')).reset_index()
            kpi_asesor['Precio_Promedio_Paño'] = kpi_asesor['Facturación_Total'] / kpi_asesor['Paños_Totales']
            kpi_asesor['Brecha'] = (kpi_asesor['Precio_Promedio_Paño'] - valor_ref_neto).apply(formato_alerta)
            
            kpi_grupo = df_kpi.groupby('Grupo').agg(Autos=('Patente', 'count'), Paños_Totales=('Paños', 'sum'), Facturación_Total=('Precio', 'sum')).reset_index()
            kpi_grupo['Precio_Promedio_Paño'] = kpi_grupo['Facturación_Total'] / kpi_grupo['Paños_Totales']
            kpi_grupo['Brecha'] = (kpi_grupo['Precio_Promedio_Paño'] - valor_ref_neto).apply(formato_alerta)

            col_kpi1, col_kpi2 = st.columns(2)
            with col_kpi1:
                with st.container(border=True):
                    st.markdown("#### 👔 Rendimiento por Asesor")
                    vista_asesor = kpi_asesor[['Asesor', 'Precio_Promedio_Paño', 'Brecha', 'Autos']].sort_values('Precio_Promedio_Paño', ascending=False)
                    st.dataframe(
                        vista_asesor, hide_index=True, use_container_width=True,
                        column_config={
                            "Precio_Promedio_Paño": st.column_config.NumberColumn("Precio Prom. x Paño", format="$ %.0f"),
                            "Brecha": st.column_config.TextColumn("Brecha vs. Seguro"),
                            "Autos": st.column_config.NumberColumn("Autos")
                        }
                    )
            with col_kpi2:
                with st.container(border=True):
                    st.markdown("#### 🏭 Rendimiento por Sector")
                    vista_grupo = kpi_grupo[['Grupo', 'Precio_Promedio_Paño', 'Brecha', 'Autos']].sort_values('Precio_Promedio_Paño', ascending=False)
                    st.dataframe(
                        vista_grupo, hide_index=True, use_container_width=True,
                        column_config={
                            "Precio_Promedio_Paño": st.column_config.NumberColumn("Precio Prom. x Paño", format="$ %.0f"),
                            "Brecha": st.column_config.TextColumn("Brecha vs. Seguro"),
                            "Autos": st.column_config.NumberColumn("Autos")
                        }
                    )
                
            c_graf1, c_graf2 = st.columns(2)
            with c_graf1:
                with st.container(border=True):
                    kpi_grupo['Intensidad'] = kpi_grupo['Paños_Totales'] / kpi_grupo['Autos']
                    fig_intensidad = px.bar(kpi_grupo, x='Grupo', y='Intensidad', text_auto='.2f', title='📦 Intensidad del Daño (Paños por Auto)', color_discrete_sequence=['#17a2b8'])
                    fig_intensidad.update_layout(xaxis_title="", yaxis_title="Promedio de Paños")
                    st.plotly_chart(fig_intensidad, use_container_width=True)

            with c_graf2:
                with st.container(border=True):
                    kpi_asesor['Ticket_Promedio'] = kpi_asesor['Facturación_Total'] / kpi_asesor['Autos']
                    fig_ticket = px.bar(kpi_asesor, x='Asesor', y='Ticket_Promedio', text_auto='$.3s', title='💰 Ticket Promedio de Venta ($ por Auto)', color_discrete_sequence=['#28a745'])
                    fig_ticket.update_layout(xaxis_title="", yaxis_title="Monto Promedio")
                    st.plotly_chart(fig_ticket, use_container_width=True)
        else:
            st.warning("No hay suficientes datos válidos (con paños y precios mayores a cero) para calcular los KPIs de rendimiento.")
            
# ==========================================
# PESTAÑA 6: HISTÓRICOS
# ==========================================
with tab_hist:
    if not df_completo.empty: 
        st.subheader("📅 Histórico Mensual (Mano de Obra)")
        df_hist = df_completo[(df_completo['Mes_Hist'] != 'SIN FECHA') & (df_completo['Grupo'].isin(['GRUPO', 'PULIDOS']))].sort_values('Mes_Hist')
        if not df_hist.empty:
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                pivot_panos = pd.pivot_table(df_hist, values='Paños', index='Mes_Hist', columns='Cliente', aggfunc='sum', fill_value=0)
                st.dataframe(pivot_panos.style.format("{:.1f}"), use_container_width=True)
            with c_h2:
                pivot_pesos = pd.pivot_table(df_hist, values='Precio', index='Mes_Hist', columns='Cliente', aggfunc='sum', fill_value=0)
                st.dataframe(pivot_pesos.style.format(lambda x: f"$ {x:,.0f}".replace(',', '.')), use_container_width=True)
            st.divider()
            st.plotly_chart(px.bar(df_hist, x="Mes_Hist", y="Paños", color="Cliente", barmode="group", title="Paños Facturados/Proyectados por Mes"), use_container_width=True)
        else: st.info("No hay datos con fechas válidas para mostrar el historial.")
