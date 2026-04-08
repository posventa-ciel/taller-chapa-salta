import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re
import json
import gspread

# --- VARIABLES SALTA ---
ID_PLANILLA = "1yVeTn7UJV5izBURIXFjROwnH1xD8L3vDpesPVZzy45c" 
GIDS = {"TALLER SALTA": "609774337"} 
URL_BASE = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid="

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Taller CENOA - Salta", layout="wide", initial_sidebar_state="expanded")

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    creds_dict = json.loads(st.secrets["google_credentials"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds_dict)
    planilla = gc.open_by_key(ID_PLANILLA)
    # Comento la parte de 'TURNOS' por si en Salta no tienen esa pestaña creada igual que en Jujuy
    # hoja = planilla.worksheet("TURNOS") 
except Exception as e:
    st.error(f"Error de conexión a Google Sheets. Detalle: {e}")

# --- ESTILOS CSS ---
st.markdown("""<style>
    [data-testid="stSidebar"] { min-width: 240px !important; max-width: 240px !important; }
    .metric-card { background-color: white; border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; margin-bottom: 15px;}
    .metric-title { color: #666; font-size: 0.85rem; font-weight: 600; margin-bottom: 5px; text-transform: uppercase; }
    .metric-value-money { color: #00235d; font-size: 1.8rem; font-weight: bold; margin: 0; }
    .metric-value-number { color: #00235d; font-size: 1.5rem; font-weight: bold; margin: 0; }
    .metric-subtitle-red { color: #dc3545; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .metric-subtitle-green { color: #28a745; font-size: 0.95rem; font-weight: bold; margin-top: 5px; }
    .kanban-col { background-color: #f8f9fa; border-radius: 8px; padding: 10px; border: 1px solid #e9ecef; }
</style>""", unsafe_allow_html=True)

formato_pesos = lambda x: f"$ {x:,.0f}".replace(',', '.')

# --- FUNCIONES DE LECTURA ---
@st.cache_data(ttl=300)
def obtener_datos_maestros():
    dfs = []
    for n, gid in GIDS.items():
        try:
            # OJO: Para que esta lectura CSV rápida funcione, el Excel debe estar compartido 
            # como "Cualquier persona con el enlace puede leer"
            d_raw = pd.read_csv(f"{URL_BASE}{gid}", dtype=str, header=None)
            
            idx_header = 0
            for i in range(min(15, len(d_raw))):
                fila_str = " ".join(d_raw.iloc[i].fillna("").astype(str).str.upper())
                if 'ESTADO' in fila_str or 'PATENTE' in fila_str or 'DOMINIO' in fila_str:
                    idx_header = i
                    break
                    
            cols = []
            for j, val in enumerate(d_raw.iloc[idx_header]):
                val_str = str(val).strip().upper()
                if val_str == 'NAN' or val_str == 'NONE' or not val_str:
                    cols.append(f"VACIA_{j}")
                else:
                    cols.append(val_str)
                    
            d_raw.columns = cols
            d = d_raw.iloc[idx_header + 1:].reset_index(drop=True)

            renames = {}
            for c in d.columns:
                c_str = str(c).upper().strip()
                if 'ESTADO FAC' in c_str or c_str == 'FAC': renames[c] = 'ESTADO_FAC'
                elif 'ESTADO' in c_str and 'TALLER' in c_str: renames[c] = 'ESTADO_TALLER'
                elif c_str == 'ESTADO': renames[c] = 'ESTADO_TALLER'
                elif 'FASE' in c_str: renames[c] = 'FASE_TALLER'
                elif 'DOMINIO' in c_str or 'PATENTE' in c_str: renames[c] = 'PATENTE'
                elif 'CLIENTE' in c_str or 'COMPAÑIA' in c_str: renames[c] = 'CLIENTE'
                elif 'ASESOR' in c_str: renames[c] = 'ASESOR'
                elif 'VEHIC' in c_str or 'MARCA' in c_str: renames[c] = 'VEHICULO'
                elif 'PAÑO' in c_str: renames[c] = 'PAÑOS'
                elif 'PRECIO' in c_str and 'REPUESTO' in c_str: renames[c] = 'PRECIO_REP'
                elif 'COSTO' in c_str and 'REPUESTO' in c_str: renames[c] = 'COSTO_REP'
                elif 'PRECIO' in c_str or 'MANO DE OBRA' in c_str: renames[c] = 'PRECIO_MO'
                elif 'COSTO' in c_str: renames[c] = 'COSTO_MO'

            d = d.rename(columns=renames)
            d = d.loc[:, ~d.columns.duplicated()]
            
            if 'PATENTE' in d.columns: 
                d = d.dropna(subset=['PATENTE'])
                d = d[d['PATENTE'].str.strip() != ""]
                d['GRUPO'] = n
                dfs.append(d)
        except Exception as e: 
            print(f"Error cargando datos: {e}")
        
    if not dfs: return pd.DataFrame()
    df_raw = pd.concat(dfs, ignore_index=True)
    
    filas = []
    for _, row in df_raw.iterrows():
        def limpiar_monto(val):
            v = str(val).replace('$', '').replace('.', '').replace(',', '.').strip()
            try: return float(v) if v and v.lower() != 'nan' else 0.0
            except: return 0.0

        p_mo = limpiar_monto(row.get('PRECIO_MO', 0))
        c_mo = limpiar_monto(row.get('COSTO_MO', 0))
        p_rep = limpiar_monto(row.get('PRECIO_REP', 0))
        c_rep = limpiar_monto(row.get('COSTO_REP', 0))
        
        try:
            t_panos = str(row.get('PAÑOS', '0')).replace(',', '.')
            panos = float(re.findall(r"[-+]?\d*\.\d+|\d+", t_panos)[0]) if re.findall(r"[-+]?\d*\.\d+|\d+", t_panos) else 0.0
        except: panos = 0.0

        estado = str(row.get('ESTADO_TALLER', '')).replace('nan', '').strip().upper() or "SIN ESTADO"
        estado_fac = str(row.get('ESTADO_FAC', '')).replace('.', '').strip().upper()

        filas.append({
            'Patente': str(row.get('PATENTE', '')).upper(),
            'Vehiculo': str(row.get('VEHICULO', '')).upper(),
            'Cliente': str(row.get('CLIENTE', 'PARTICULAR')).upper(),
            'Asesor': str(row.get('ASESOR', 'SIN ASIGNAR')).upper(),
            'Estado_Taller': estado,
            'Estado_Fac': estado_fac,
            'Fase_Taller': str(row.get('FASE_TALLER', '')).upper(),
            'Paños': panos,
            'Precio_MO': p_mo, 'Costo_MO': c_mo,
            'Precio_REP': p_rep, 'Costo_REP': c_rep,
            'Venta_Total': p_mo + p_rep,
            'Costo_Total': c_mo + c_rep
        })
    return pd.DataFrame(filas)

# --- CARGA DE DATOS ---
df = obtener_datos_maestros()

# --- INTERFAZ GRAFICA ---
st.title("🚀 Sistema de Gestión Taller CENOA - Salta")
if st.button("🔄 Actualizar Datos"):
    st.cache_data.clear()
    st.rerun()

if df.empty:
    st.warning("⚠️ No se pudieron cargar los datos de la tabla. Verificá que el Excel de Salta esté configurado como 'Cualquier persona con el enlace puede leer'.")
else:
    tab_taller, tab_fac = st.tabs(["🛠️ Tablero de Producción", "💰 Facturación y Repuestos"])

    with tab_taller:
        st.markdown("### 📋 Tablero Kanban - Taller Único")
        df_kanban = df[df['Estado_Taller'].str.contains("PROCESO|DETENIDO", na=False)].copy()
        df_kanban.loc[df_kanban['Estado_Taller'].str.contains("DETENIDO", na=False), 'Fase_Taller'] = "⛔ DETENIDOS"
        
        orden_ideal = ["SIN ASIGNAR", "CHAPA", "PREPARACION", "PINTURA", "ARMADO", "PULIDO", "⛔ DETENIDOS"]
        
        cols_kanban = st.columns(len(orden_ideal))
        for idx, fase in enumerate(orden_ideal):
            with cols_kanban[idx]:
                st.markdown(f"<div class='kanban-col'><h5 style='text-align:center; color:#00235d; margin: 0; font-size: 0.85rem;'>{fase}</h5></div>", unsafe_allow_html=True)
                
                if fase == "SIN ASIGNAR":
                    df_fase = df_kanban[(df_kanban['Fase_Taller'] == "") | (df_kanban['Fase_Taller'].isna()) | (df_kanban['Fase_Taller'] == "SIN FASE ASIGNADA")]
                else:
                    df_fase = df_kanban[df_kanban['Fase_Taller'].str.contains(fase[:4], na=False, case=False)]
                
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

    with tab_fac:
        st.subheader("Análisis de Facturación: Mano de Obra + Repuestos")
        
        df_ventas = df[df['Estado_Fac'].isin(['FAC', 'SI'])].copy()
        
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
            
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown("#### 🔧 Mano de Obra")
                st.markdown(f'<div class="metric-card"><div class="metric-title">Venta MO</div><div class="metric-value-money">{formato_pesos(v_mo)}</div><div class="metric-subtitle-green" style="font-size:0.8rem; color:#666;">Costo: {formato_pesos(c_mo)}</div></div>', unsafe_allow_html=True)

            with c2:
                st.markdown("#### 📦 Repuestos")
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">Venta Repuestos</div>
                        <div class="metric-value-money" style="color: #28a745;">{formato_pesos(v_rep)}</div>
                        <div class="metric-subtitle-red" style="font-size:0.9rem;">Costo: {formato_pesos(c_rep)}</div>
                        <div style="font-size: 0.8rem; color: #00235d; font-weight: bold; margin-top:5px;">Margen Rep: {porc_margen_rep:.1f}%</div>
                    </div>
                """, unsafe_allow_html=True)

            with c3:
                st.markdown("#### 🏆 Total Operación")
                st.markdown(f'<div class="metric-card" style="border: 2px solid #00235d;"><div class="metric-title">Facturación Total (MO + Rep)</div><div class="metric-value-money">{formato_pesos(total_venta)}</div><div class="metric-subtitle-green" style="margin-top:5px;">Margen Bruto: {formato_pesos(total_margen)}</div></div>', unsafe_allow_html=True)

            st.divider()
            st.write("### 🔍 Detalle de Rentabilidad por Unidad (Aprobados/Facturados)")
            
            df_detalle = df_ventas[['Patente', 'Cliente', 'Precio_MO', 'Precio_REP', 'Venta_Total', 'Costo_Total']].copy()
            df_detalle['Margen ($)'] = df_detalle['Venta_Total'] - df_detalle['Costo_Total']
            
            st.dataframe(
                df_detalle.sort_values('Venta_Total', ascending=False),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Precio_MO": st.column_config.NumberColumn("Venta MO ($)", format="$ %.0f"),
                    "Precio_REP": st.column_config.NumberColumn("Venta Repuestos ($)", format="$ %.0f"),
                    "Venta_Total": st.column_config.NumberColumn("Total Facturado ($)", format="$ %.0f"),
                    "Costo_Total": st.column_config.NumberColumn("Costo Total ($)", format="$ %.0f"),
                    "Margen ($)": st.column_config.NumberColumn("Margen de Ganancia ($)", format="$ %.0f")
                }
            )
        else:
            st.info("No hay vehículos marcados como 'FAC' o 'SI' en la columna de Estado de Facturación.")
