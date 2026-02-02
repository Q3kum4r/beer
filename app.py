import streamlit as st
import json
import re
import os

# --- KONFIGURACIJA ---
st.set_page_config(page_title="BrewTarget Web", layout="wide", page_icon="🍺")

def clean_json_comments(text):
    """Uklanja // komentare i čisti tekst za JSON parser."""
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_brew_data():
    hops, malts, styles = [], [], []
    
    # 1. Učitavanje BJCP Stilova
    if os.path.exists('bjcp_data.json'):
        try:
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                content = clean_json_comments(f.read())
                data = json.loads(content)
                styles = data.get('beerjson', {}).get('styles', [])
        except Exception as e:
            st.error(f"Greška u bjcp_data.json: {e}")

    # 2. Učitavanje Sastojaka (Brew Data)
    if os.path.exists('brew_data.json'):
        try:
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                content = clean_json_comments(f.read())
                data = json.loads(content)
                hops = data.get('beerjson', {}).get('hop_varieties', [])
                malts = data.get('beerjson', {}).get('fermentables', [])
        except Exception as e:
            st.error(f"Greška u brew_data.json: {e}")
            
    return hops, malts, styles

# Učitaj baze
hops_db, malts_db, styles_db = load_brew_data()

# --- INTERFEJS ---
st.title("🍺 BrewTarget Web Clone")

if not styles_db:
    st.error("Baza stilova nije učitana. Provjeri bjcp_data.json!")
    st.stop()

# --- SIDEBAR: Oprema i Stil ---
with st.sidebar:
    st.header("⚙️ Postavke")
    batch_size = st.number_input("Batch Size (L)", value=20.0, step=1.0)
    efficiency = st.slider("Efikasnost (%)", 50, 95, 75)
    
    st.divider()
    style_name = st.selectbox("Ciljani BJCP Stil", [s['name'] for s in styles_db])
    selected_style = next(s for s in styles_db if s['name'] == style_name)

# --- RECEPT (LIJEVA KOLONA) ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🌾 Grain Bill (Sladovi)")
    if malts_db:
        malt_names = st.multiselect("Dodaj sladove:", [m['name'] for m in malts_db])
        chosen_malts = []
        for mn in malt_names:
            m_info = next(m for m in malts_db if m['name'] == mn)
            w = st.number_input(f"kg: {mn}", value=1.0, step=0.1, key=f"malt_{mn}")
            chosen_malts.append({'info': m_info, 'weight': w})
    else:
        st.warning("Sladovi nisu pronađeni u brew_data.json. Koristim testni Pilsner.")
        # Fallback ako je brew_data.json nepotpun
        pils_weight = st.number_input("Testni Pilsner Slad (kg)", value=5.0)
        chosen_malts = [{'info': {'yield': {'fine_grind': 80.0}, 'color': 3.5}, 'weight': pils_weight}]

    st.divider()
    st.subheader("🌿 Hop Schedule (Hmeljevi)")
    hop_names = st.multiselect("Dodaj hmeljeve (60 min):", [h['name'] for h in hops_db])
    chosen_hops = []
    for hn in hop_names:
        h_info = next(h for h in hops_db if h['name'] == hn)
        g = st.number_input(f"grama: {hn}", value=20.0, step=1.0, key=f"hop_{hn}")
        chosen_hops.append({'info': h_info, 'weight': g})

# --- KALKULACIJE ---
def calculate_brew():
    # OG izračun
    total_pts = 0
    for m in chosen_malts:
        # BeerJSON standard za yield
        potential = m['info'].get('yield', {}).get('fine_grind', 75.0) * 0.01 * 384
        pts = (m['weight'] * 2.204) * potential * (efficiency / 100)
        total_pts += pts
    
    og = 1 + (total_pts / (batch_size / 3.785) / 1000)
    
    # IBU izračun (Tinseth)
    ibu = 0
    for h in chosen_hops:
        aa = h['info'].get('alpha_acid', {}).get('value', 5.0)
        utilization = 0.24 # aproksimacija za 60 min
        ibu += (h['weight'] * aa * utilization * 10) / batch_size
        
    return og, ibu

current_og, current_ibu = calculate_brew()

# --- REZULTATI (DESNA KOLONA) ---
with col2:
    st.subheader("📊 Analiza")
    
    # OG Prikaz
    og_min = selected_style.get('original_gravity', {}).get('minimum', {}).get('value', 1.000)
    og_max = selected_style.get('original_gravity', {}).get('maximum', {}).get('value', 1.100)
    
    st.metric("Gustoća (OG)", f"{current_og:.3f}")
    if og_min <= current_og <= og_max:
        st.success(f"U stilu ({og_min}-{og_max}) ✅")
    else:
        st.error(f"Izvan stila ({og_min}-{og_max}) ❌")

    # IBU Prikaz
    ibu_min = selected_style.get('international_bitterness_units', {}).get('minimum', {}).get('value', 0)
    ibu_max = selected_style.get('international_bitterness_units', {}).get('maximum', {}).get('value', 100)
    
    st.metric("Gorčina (IBU)", f"{int(current_ibu)}")
    if ibu_min <= current_ibu <= ibu_max:
        st.success(f"U stilu ({int(ibu_min)}-{int(ibu_max)}) ✅")
    else:
        st.error(f"Izvan stila ({int(ibu_min)}-{int(ibu_max)}) ❌")

    st.divider()
    with st.expander("Opis stila"):
        st.write(selected_style.get('overall_impression', 'Nema opisa.'))
