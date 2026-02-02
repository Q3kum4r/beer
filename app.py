import streamlit as st
import json
import re
import os

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="BrewMaster Web Pro", layout="wide", page_icon="🍺")

def clean_json_comments(text):
    """Uklanja // komentare koji se nalaze u tvojim datotekama."""
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

    # 3. Učitavanje Sladova (fermentables_data.json - tvoj konvertirani file)
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
st.markdown("Integrirana baza: BJCP 2021 + BrewTarget Hops + Custom Fermentables")

if not styles_db or not malts_db:
    st.error("Kritične datoteke nedostaju ili su prazne! Provjeri GitHub repozitorij.")
    st.stop()

# --- SIDEBAR: Postavke sustava ---
with st.sidebar:
    st.header("⚙️ Parametri kuhanja")
    batch_size = st.number_input("Količina šarže (Litre)", value=20.0, step=1.0)
    efficiency = st.slider("Efikasnost ukomljavanja (%)", 40, 95, 75)
    
    st.divider()
    style_names = [s['name'] for s in styles_db]
    style_choice = st.selectbox("Ciljani BJCP Stil", style_names)
    selected_style = next(s for s in styles_db if s['name'] == style_choice)

# --- RECEPT (Lijeva strana) ---
col1, col2 = st.columns([2, 1])

with col1:
    # Sekcija za sladove
    st.subheader("🌾 Grain Bill (Sladovi i Ekstrakti)")
    m_selection = st.multiselect("Dodaj sastojke:", [m['name'] for m in malts_db])
    active_malts = []
    
    for name in m_selection:
        m_info = next(m for m in malts_db if m['name'] == name)
        c_m1, c_m2 = st.columns([3, 1])
        with c_m1:
            color = m_info.get('color', 0)
            st.write(f"**{name}** ({color} EBC/SRM)")
        with c_m2:
            w = st.number_input(f"kg", value=1.0, step=0.1, key=f"m_qty_{name}", label_visibility="collapsed")
        active_malts.append({'info': m_info, 'weight': w})

    st.divider()
    
    # Sekcija za hmeljeve
    st.subheader("🌿 Hop Schedule (Hmeljevi - 60 min)")
    h_selection = st.multiselect("Dodaj hmeljeve:", [h['name'] for h in hops_db])
    active_hops = []
    
    for name in h_selection:
        h_info = next(h for h in hops_db if h['name'] == name)
        # BeerJSON struktura za alpha kiseline
        aa_val = h_info.get('alpha_acid', {}).get('value', 5.0)
        c_h1, c_h2 = st.columns([3, 1])
        with c_h1:
            st.write(f"**{name}** ({aa_val}% AA)")
        with c_h2:
            g = st.number_input(f"g", value=20.0, step=1.0, key=f"h_qty_{name}", label_visibility="collapsed")
        active_hops.append({'info': h_info, 'weight': g})

# --- KALKULACIJE ---
def run_calculations():
    # 1. Original Gravity (OG)
    pts = 0
    for m in active_malts:
        # yield u BeerJSON-u je postotak
        yield_pct = m['info'].get('yield', 75.0)
        # Ako je yield objekt (neki formati), uzmi fine_grind
        if isinstance(yield_pct, dict):
            yield_pct = yield_pct.get('fine_grind', 75.0)
            
        pts += (m['weight'] * 2.204) * (yield_pct * 0.01 * 384) * (efficiency / 100)
    
    og = 1 + (pts / (batch_size / 3.785) / 1000) if batch_size > 0 else 1.0
    
    # 2. International Bitterness Units (IBU)
    total_ibu = 0
    for h in active_hops:
        aa = h['info'].get('alpha_acid', {}).get('value', 5.0)
        # Tinseth aproksimacija (f_og * f_time)
        f_og = 1.65 * (0.000125**(og - 1))
        f_time = (1 - 2.718**(-0.04 * 60)) / 4.15 # fiksno 60 min
        utilization = f_og * f_time
        total_ibu += (h['weight'] * aa * utilization * 10) / batch_size if batch_size > 0 else 0
        
    # 3. Boja (SRM/EBC) - Morey formula
    mcu = 0
    for m in active_malts:
        mcu += (m['weight'] * 2.204 * m['info'].get('color', 0)) / (batch_size / 3.785)
    srm = 1.4922 * (mcu ** 0.6859) if mcu > 0 else 0
    
    return og, total_ibu, srm * 1.97 # Vraćamo OG, IBU i EBC

res_og, res_ibu, res_ebc = run_calculations()

# --- REZULTATI (Desna strana) ---
with col2:
    st.subheader("📊 Rezultati kuhanja")
    
    # OG Metrika i provjera stila
    og_min = selected_style.get('original_gravity', {}).get('minimum', {}).get('value', 1.0)
    og_max = selected_style.get('original_gravity', {}).get('maximum', {}).get('value', 1.1)
    st.metric("Original Gravity (OG)", f"{res_og:.3f}")
    
    if og_min <= res_og <= og_max:
        st.success(f"Gustoća OK (Cilj: {og_min}-{og_max})")
    else:
        st.warning(f"Izvan stila (Cilj: {og_min}-{og_max})")
    
    st.divider()
    
    # IBU Metrika
    ibu_min = selected_style.get('international_bitterness_units', {}).get('minimum', {}).get('value', 0)
    ibu_max = selected_style.get('international_bitterness_units', {}).get('maximum', {}).get('value', 100)
    st.metric("Gorčina (IBU)", f"{int(res_ibu)}")
    st.caption(f"Cilj stila: {int(ibu_min)} - {int(ibu_max)}")

    # Boja Metrika
    st.metric("Boja (EBC)", f"{int(res_ebc)}")
    
    st.divider()
    with st.expander("📝 Više o stilu"):
        st.write(selected_style.get('overall_impression', 'Nema opisa.'))
