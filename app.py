import streamlit as st
import json
import requests

# Postavke stranice
st.set_page_config(page_title="BrewMaster Web", layout="wide", page_icon="🍺")

# --- FUNKCIJE ZA UČITAVANJE ---
@st.cache_data
def load_data():
    # Linkovi na tvoje sirove (raw) podatke
    brew_url = "https://raw.githubusercontent.com/Q3kum4r/beer/main/brew_data.json"
    bjcp_url = "https://raw.githubusercontent.com/Q3kum4r/beer/main/bjcp_data.json"
    
    brew_data = requests.get(brew_url).json()
    bjcp_data = requests.get(bjcp_url).json()
    
    return brew_data, bjcp_data

try:
    brew_db, bjcp_db = load_data()
    # Ekstrakcija lista iz BrewTarget strukture
    hops_list = brew_db.get('hops', [])
    malts_list = brew_db.get('fermentables', [])
    # Ekstrakcija iz BJCP (ovisno o strukturi tvoje datoteke)
    styles_list = bjcp_db if isinstance(bjcp_db, list) else bjcp_db.get('styles', [])
except Exception as e:
    st.error(f"Greška pri učitavanju podataka: {e}")
    st.stop()

# --- LOGIKA IZRAČUNA ---
def calculate_metrics(selected_malts, selected_hops, batch_size, efficiency):
    # OG Izračun
    total_points = 0
    total_ebc = 0
    for m in selected_malts:
        # yield u BrewTarget JSON-u je postotak (npr. 80.0)
        potential = m['info']['yield'] * 0.01 * 384 
        points = (m['weight'] * 2.204) * potential * (efficiency / 100)
        total_points += points
        # Boja (Morey formula)
        total_ebc += (m['weight'] * m['info']['color'] * 4.25) / batch_size
    
    og = 1 + (total_points / (batch_size / 3.785) / 1000)
    
    # IBU Izračun (Tinseth aproksimacija za 60 min)
    total_ibu = 0
    for h in selected_hops:
        utilization = 0.24 # Prosjek za 60 min kuhanja
        mg_l_alpha = (h['info']['alpha_acid'] / 100) * h['weight'] * 1000 / batch_size
        total_ibu += mg_l_alpha * utilization
        
    return og, total_ibu, total_ebc

# --- UI INTERFACE ---
st.title("🍺 BrewMaster Web Calculator")
st.markdown("Bazirano na BrewTarget i BJCP podacima")

with st.sidebar:
    st.header("⚙️ Parametri kuhanja")
    batch_size = st.number_input("Količina piva (L)", value=20.0)
    efficiency = st.slider("Efikasnost ukomljavanja (%)", 50, 95, 75)
    
    st.divider()
    selected_style_name = st.selectbox("Ciljani BJCP Stil", [s['name'] for s in styles_list])
    style_info = next(s for s in styles_list if s['name'] == selected_style_name)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🌾 Sastojci")
    
    # Odabir sladova (Multi-select)
    malt_names = st.multiselect("Dodaj sladove:", [m['name'] for m in malts_list])
    active_malts = []
    for name in malt_names:
        m_data = next(m for m in malts_list if m['name'] == name)
        w = st.number_input(f"Težina za {name} (kg)", value=1.0, step=0.1, key=f"w_{name}")
        active_malts.append({'info': m_data, 'weight': w})
    
    st.divider()
    
    # Odabir hmelja
    hop_names = st.multiselect("Dodaj hmeljeve (60 min):", [h['name'] for h in hops_list])
    active_hops = []
    for name in hop_names:
        h_data = next(h for h in hops_list if h['name'] == name)
        g = st.number_input(f"Količina {name} (g)", value=20.0, step=1.0, key=f"g_{name}")
        active_hops.append({'info': h_data, 'weight': g})

# Izračun
og, ibu, ebc = calculate_metrics(active_malts, active_hops, batch_size, efficiency)

with col2:
    st.subheader("📊 Rezultati")
    
    # OG Prikaz
    st.metric("Original Gravity (OG)", f"{og:.3f}")
    og_min, og_max = float(style_info.get('og_min', 1.0)), float(style_info.get('og_max', 1.1))
    st.caption(f"Stil: {og_min} - {og_max}")
    
    # IBU Prikaz
    st.metric("Gorčina (IBU)", f"{int(ibu)}")
    ibu_min, ibu_max = float(style_info.get('ibu_min', 0)), float(style_info.get('ibu_max', 100))
    st.caption(f"Stil: {ibu_min} - {ibu_max}")
    
    # Boja Prikaz
    st.metric("Boja (EBC)", f"{int(ebc)}")

    st.divider()
    if og_min <= og <= og_max:
        st.success("OG je unutar stila! ✅")
    else:
        st.warning("OG je izvan stila! ⚠️")
