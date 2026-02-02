import streamlit as st
import json
import re
import os

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="BrewMaster Web Pro", layout="wide", page_icon="🍺")

def clean_json_comments(text):
    """Uklanja // komentare iz datoteka prije parsiranja."""
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_all_databases():
    hops, malts, styles = [], [], []
    
    # 1. Učitavanje BJCP Stilova (bjcp_data.json)
    if os.path.exists('bjcp_data.json'):
        try:
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                content = clean_json_comments(f.read())
                data = json.loads(content)
                styles = data.get('beerjson', {}).get('styles', [])
        except Exception as e:
            st.error(f"Greška u bjcp_data.json: {e}")

    # 2. Učitavanje Hmeljeva (brew_data.json)
    if os.path.exists('brew_data.json'):
        try:
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                content = clean_json_comments(f.read())
                data = json.loads(content)
                hops = data.get('beerjson', {}).get('hop_varieties', [])
        except Exception as e:
            st.error(f"Greška u brew_data.json: {e}")

    # 3. Učitavanje Sladova (fermentables_data.json)
    if os.path.exists('fermentables_data.json'):
        try:
            with open('fermentables_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                malts = data.get('beerjson', {}).get('fermentables', [])
        except Exception as e:
            st.error(f"Greška u fermentables_data.json: {e}")
            
    return hops, malts, styles

# Inicijalizacija baze
hops_db, malts_db, styles_db = load_all_databases()

# --- GLAVNI INTERFEJS ---
st.title("🍺 BrewMaster Web Calculator")
st.markdown("Jedinice: **Kilogrami (kg), Grami (g), Litre (L), Celzijusi (°C)**")

if not styles_db or not malts_db:
    st.error("Kritične datoteke nisu pronađene! Provjeri jesu li nazivi na GitHubu ispravni.")
    st.stop()

# --- SIDEBAR: Postavke sustava ---
with st.sidebar:
    st.header("⚙️ Parametri kuhanja")
    batch_size = st.number_input("Količina šarže (L)", value=20.0, step=1.0, help="Finalni volumen piva u litrama")
    efficiency = st.slider("Efikasnost ukomljavanja (%)", 40, 95, 75, help="Postotak šećera koji uspijete izvući iz slada")
    boil_temp = st.number_input("Temperatura kuhanja (°C)", value=100.0, step=0.5)
    
    st.divider()
    style_names = [s['name'] for s in styles_db]
    style_choice = st.selectbox("Ciljani BJCP Stil", style_names)
    selected_style = next(s for s in styles_db if s['name'] == style_choice)

# --- RECEPT (Lijeva strana) ---
col1, col2 = st.columns([2, 1])

with col1:
    # Sekcija za sladove
    st.subheader("🌾 Grain Bill (Sladovi u kg)")
    m_selection = st.multiselect("Dodaj sladove:", [m['name'] for m in malts_db])
    active_malts = []
    
    for name in m_selection:
        m_info = next(m for m in malts_db if m['name'] == name)
        c_m1, c_m2 = st.columns([3, 1])
        with c_m1:
            color = m_info.get('color', 0)
            st.write(f"**{name}** ({color} EBC)")
        with c_m2:
            w = st.number_input(f"kg", value=1.0, step=0.1, key=f"m_qty_{name}", label_visibility="collapsed")
        active_malts.append({'info': m_info, 'weight': w})

    st.divider()
    
    # Sekcija za hmeljeve
    st.subheader("🌿 Hop Schedule (Hmeljevi u g)")
    h_selection = st.multiselect("Dodaj hmeljeve (60 min kuhanja):", [h['name'] for h in hops_db])
    active_hops = []
    
    for name in h_selection:
        h_info = next(h for h in hops_db if h['name'] == name)
        aa_val = h_info.get('alpha_acid', {}).get('value', 5.0)
        c_h1, c_h2 = st.columns([3, 1])
        with c_h1:
            st.write(f"**{name}** ({aa_val}% Alpha)")
        with c_h2:
            g = st.number_input(f"g", value=20.0, step=1.0, key=f"h_qty_{name}", label_visibility="collapsed")
        active_hops.append({'info': h_info, 'weight': g})

# --- KALKULACIJE ---
def run_calculations():
    # 1. Original Gravity (OG) - Metrički izračun
    pts = 0
    for m in active_malts:
        yield_val = m['info'].get('yield', 75.0)
        if isinstance(yield_val, dict):
            yield_val = yield_val.get('fine_grind', 75.0)
        # Pretvorba kg u lbs i L u galone za standardnu formulu unutar koda
        pts += (m['weight'] * 2.204) * (yield_val * 0.01 * 384) * (efficiency / 100)
    
    og = 1 + (pts / (batch_size / 3.785) / 1000) if batch_size > 0 else 1.0
    
    # 2. International Bitterness Units (IBU) - Tinseth metrički
    total_ibu = 0
    for h in active_hops:
        aa = h['info'].get('alpha_acid', {}).get('value', 5.0)
        f_og = 1.65 * (0.000125**(og - 1))
        f_time = (1 - 2.718**(-0.04 * 60)) / 4.15 # fiksno na 60 min kuhanja
        utilization = f_og * f_time
        # (grami * alpha% * utilization * 10) / litre
        total_ibu += (h['weight'] * aa * utilization * 10) / batch_size if batch_size > 0 else 0
        
    # 3. Boja (EBC) - Morey formula
    mcu = 0
    for m in active_malts:
        mcu += (m['weight'] * 2.204 * m['info'].get('color', 0)) / (batch_size / 3.785)
    srm = 1.4922 * (mcu ** 0.6859) if mcu > 0 else 0
    ebc = srm * 1.97
    
    return og, total_ibu, ebc

res_og, res_ibu, res_ebc = run_calculations()

# --- REZULTATI (Desna strana) ---
with col2:
    st.subheader("📊 Rezultati kuhanja")
    
    # OG Metrika
    og_min = selected_style.get('original_gravity', {}).get('minimum', {}).get('value', 1.0)
    og_max = selected_style.get('original_gravity', {}).get('maximum', {}).get('value', 1.1)
    st.metric("Gustoća (OG)", f"{res_og:.3f}")
    if og_min <= res_og <= og_max:
        st.success(f"Gustoća OK (Cilj: {og_min}-{og_max})")
    else:
        st.warning(f"Izvan stila (Cilj: {og_min}-{og_max})")
    
    st.divider()
    
    # IBU Metrika
    ibu_min = selected_style.get('international_bitterness_units', {}).get('minimum', {}).get('value', 0)
    ibu_max = selected_style.get('international_bitterness_units', {}).get('maximum', {}).get('value', 100)
    st.metric("Gorčina (IBU)", f"{int(res_ibu)}")
    st.caption(f"BJCP Cilj: {int(ibu_min)} - {int(ibu_max)}")

    # Boja Metrika
    st.metric("Boja (EBC)", f"{int(res_ebc)}")
    
    st.divider()
    with st.expander("📝 Detalji BJCP stila"):
        st.write(f"**Kategorija:** {selected_style.get('category', 'N/A')}")
        st.write(selected_style.get('overall_impression', 'Nema opisa.'))
