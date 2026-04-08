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

# --- VARIABLES SALTA (Lo movemos arriba de todo) ---
ID_PLANILLA = "1yVeTn7UJV5izBURIXFjROwnH1xD8L3vDpesPVZzy45c" 
GIDS = {"TALLER SALTA": "609774337"} 
URL_BASE = f"https://docs.google.com/spreadsheets/d/{ID_PLANILLA}/export?format=csv&gid="

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Taller CENOA - Salta", layout="wide", initial_sidebar_state="expanded")

# --- CONEXIÓN A GOOGLE SHEETS (GSPREAD) ---
try:
    creds_dict = json.loads(st.secrets["google_credentials"])
    gc = gspread.service_account_from_dict(creds_dict)
    planilla = gc.open_by_key(ID_PLANILLA)
    hoja = planilla.worksheet("TURNOS") # Asegurate de que exista una pestaña que se llame TURNOS
except Exception as e:
    st.error(f"Error de conexión a Google Sheets: Revisar credenciales o permisos. Detalle: {e}")
    hoja = None
    
# --- ESTILOS CSS ---
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

# Helpers
formato_pesos = lambda x: f"$ {x:,.0f}".replace(',', '.')
hoy = datetime.today()

# --- FUNCIONES DE LECTURA ---
# (De acá para abajo dejás el código exactamente igual que antes, a partir de @st.cache_data)
