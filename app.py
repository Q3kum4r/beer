import streamlit as st
import json
import os
import re

st.set_page_config(page_title="BrewMaster BeerJSON", layout="wide", page_icon="🍺")

def clean_json_comments(text):
    """Uklanja // komentare prije parsiranja JSON-a"""
    return re.sub(r'//.*', '', text)

@st.cache_data
def load_data():
    try:
        # Učitavanje brew_data.json
        with open('brew_data.json', 'r', encoding='utf-8') as f:
            raw_brew = f.read()
            brew_db = json.loads(clean_json_comments(raw_brew))
        
        # Učitavanje bjcp_data.json
        with open('bjcp_data.json', 'r', encoding='utf-8') as f:
            raw_bjcp = f.read()
            bjcp_db = json.loads(clean_json_comments(raw_bjcp))

        # Ekstrakcija prema BeerJSON 2.01 standardu iz tvog primjera
        # Putanja: beerjson -> hop_varieties
        hops = brew_db.get('beerjson', {}).get('hop_varieties', [])
        # Putanja: beerjson -> fermentables (pretpostavka na temelju standarda)
        malts = brew_db.get('beerjson', {}).get('fermentables', [])
        # Putanja: beerjson -> styles
        styles = bjcp_db.get('beerjson', {}).get('styles', [])

        return hops, malts, styles
    except Exception as e:
        st.error(f"Greška pri čitanju: {e}")
        return [], [], []

hops_list, malts_list, styles_list = load_data()

# --- POMOĆNE FUNKCIJE ZA IZRAČUN ---
def get_og(active_malts, batch_size, efficiency):
    total_pts = 0
    for m in active_malts:
        # BeerJSON koristi yield/potential. Ako ga nema, koristimo prosjek 75%
        yield_val = m['info'].get('yield', {}).get('fine_grind', 75.0)
        pts = (m['weight'] * 2.204) * (yield_val * 0.01 * 384) * (efficiency / 100)
        total_pts += pts
    return 1 + (total_pts / (batch_size / 3.785) / 1000)

def get_ibu(active_hops, og, batch_size):
    total_ibu = 0
    for h in active_hops:
        # Putanja u tvom JSON-u: alpha_acid -> value
        aa = h['info'].get('alpha_acid', {}).get('value', 5.0)
        utilization = 0.24 # Aproksimacija za 60 min
        total_ibu += (h['weight'] * aa * utilization * 10) / batch_size
    return total_ibu

# --- UI ---
st.title("🍺 BrewMaster BeerJSON Edition")

if not hops_list or not styles_list:
    st.warning("Provjeri jesu li brew_data.json i bjcp_data.json u istom folderu kao app.py.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Postavke")
    batch_size = st.number_input("Batch (L)", value=20.0)
    efficiency = st.slider("Efikasnost (%)", 50, 95, 75)
    
    selected_style_name = st.selectbox("Ciljani Stil", [s['name'] for s in styles_list])
    style = next(s for s in styles_list if s['name'] == selected_style_name)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🌾 Recept")
    
    # Sladovi
    if malts_list:
        selected_m = st.multiselect("Dodaj sladove:", [m['name'] for m in malts_list])
        active_malts = []
        for name in selected_m:
            m_data = next(m for m in malts_list if m['name'] == name)
            w = st.number_input(f"kg - {name}", value=1.0, step=0.1, key=f"m_{name}")
            active_malts.append({'info': m_data, 'weight': w})
    else:
        st.info("Nisu pronađeni sladovi (fermentables) u brew_data.json")
        active_malts = []

    # Hmeljevi
    selected_h = st.multiselect("Dodaj hmeljeve:", [h['name'] for h in hops_list])
    active_hops = []
    for name in selected_h:
        h_data = next(h for h in hops_list if h['name'] == name)
        g = st.number_input(f"g - {name}", value=20.0, step=1.0, key=f"h_{name}")
        active_hops.append({'info': h_data, 'weight': g})

# Rezultati
og = get_og(active_malts, batch_size, efficiency)
ibu = get_ibu(active_hops, og, batch_size)

with col2:
    st.subheader("📊 Analiza")
    st.metric("Gustoća (OG)", f"{og:.3f}")
    
    # Izvlačenje min/max OG iz BeerJSON strukture
    og_min = style.get('original_gravity', {}).get('minimum', {}).get('value', 1.000)
    og_max = style.get('original_gravity', {}).get('maximum', {}).get('value', 1.100)
    st.caption(f"Cilj stila: {og_min} - {og_max}")
    
    st.metric("Gorčina (IBU)", f"{int(ibu)}")

    if og_min <= og <= og_max:
        st.success("Gustoća OK! ✅")
    else:
        st.error("Izvan gustoće stila! ❌")

    # Opis stila
    with st.expander("Više o stilu"):
        st.write(style.get('overall_impression', 'Nema opisa.'))
