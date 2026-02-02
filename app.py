import streamlit as st
import json
import re
import os

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="BrewMaster Pro", layout="wide", page_icon="🍺")

def clean_json_comments(text):
    """Uklanja // komentare iz datoteka."""
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_all_databases():
    hops, malts, styles = [], [], []
    # 1. BJCP Stilovi
    if os.path.exists('bjcp_data.json'):
        try:
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                data = json.loads(clean_json_comments(f.read()))
                styles = data.get('beerjson', {}).get('styles', [])
        except: pass
    # 2. Hmeljevi
    if os.path.exists('brew_data.json'):
        try:
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                data = json.loads(clean_json_comments(f.read()))
                hops = data.get('beerjson', {}).get('hop_varieties', [])
        except: pass
    # 3. Sladovi
    if os.path.exists('fermentables_data.json'):
        try:
            with open('fermentables_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                malts = data.get('beerjson', {}).get('fermentables', [])
        except: pass
    return hops, malts, styles

hops_db, malts_db, styles_db = load_all_databases()

# --- POMOĆNA FUNKCIJA ZA BOJU ---
def ebc_to_hex(ebc):
    """Pretvara EBC vrijednost u HEX boju za grafički prikaz."""
    srm = ebc * 0.508
    if srm < 2: return "#FFE699"
    if srm < 5: return "#FFD878"
    if srm < 8: return "#FFCA5A"
    if srm < 12: return "#FFBF42"
    if srm < 15: return "#FBB123"
    if srm < 18: return "#F8A600"
    if srm < 22: return "#F39C00"
    if srm < 26: return "#EA8F00"
    if srm < 30: return "#E58500"
    if srm < 35: return "#D36E00"
    if srm < 40: return "#BD5400"
    if srm < 50: return "#8F3300"
    if srm < 60: return "#611200"
    if srm < 70: return "#420000"
    if srm < 80: return "#260000"
    return "#000000"

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Parametri sustava")
    batch_size = st.number_input("Količina šarže (L)", value=20.0, step=1.0)
    efficiency = st.slider("Efikasnost (%)", 40, 95, 75)
    
    st.divider()
    style_names = [s['name'] for s in styles_db] if styles_db else ["N/A"]
    style_choice = st.selectbox("Ciljani BJCP Stil", style_names)
    selected_style = next((s for s in styles_db if s['name'] == style_choice), {})

# --- GLAVNI PROZOR S TABOVIMA ---
tab_recipe, tab_tools = st.tabs(["📋 Recept", "🧮 Kalkulatori"])

with tab_recipe:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🌾 Sladovi (kg)")
        m_selection = st.multiselect("Dodaj sastojke:", [m['name'] for m in malts_db])
        active_malts = []
        for name in m_selection:
            m_info = next(m for m in malts_db if m['name'] == name)
            c1, c2 = st.columns([3, 1])
            with c1: st.write(f"**{name}** ({m_info.get('color', 0)} EBC)")
            with c2: w = st.number_input(f"kg", value=1.0, step=0.1, key=f"m_{name}", label_visibility="collapsed")
            active_malts.append({'info': m_info, 'weight': w})

        st.divider()
        st.subheader("🌿 Hmeljevi (g)")
        h_selection = st.multiselect("Dodaj hmeljeve:", [h['name'] for h in hops_db])
        active_hops = []
        for name in h_selection:
            h_info = next(h for h in hops_db if h['name'] == name)
            aa = h_info.get('alpha_acid', {}).get('value', 5.0)
            c1, c2 = st.columns([3, 1])
            with c1: st.write(f"**{name}** ({aa}% AA)")
            with c2: g = st.number_input(f"g", value=20.0, step=1.0, key=f"h_{name}", label_visibility="collapsed")
            active_hops.append({'info': h_info, 'weight': g})

    # --- IZRAČUN REZULTATA ---
    pts = 0
    mcu = 0
    for m in active_malts:
        y = m['info'].get('yield', 75.0)
        if isinstance(y, dict): y = y.get('fine_grind', 75.0)
        pts += (m['weight'] * 2.204) * (y * 0.01 * 384) * (efficiency / 100)
        mcu += (m['weight'] * 2.204 * m['info'].get('color', 0)) / (batch_size / 3.785)
    
    og = 1 + (pts / (batch_size / 3.785) / 1000) if batch_size > 0 else 1.0
    srm = 1.4922 * (mcu ** 0.6859) if mcu > 0 else 0
    ebc = int(srm * 1.97)

    total_ibu = 0
    for h in active_hops:
        aa = h['info'].get('alpha_acid', {}).get('value', 5.0)
        f_og = 1.65 * (0.000125**(og - 1))
        f_time = (1 - 2.718**(-0.04 * 60)) / 4.15
        total_ibu += (h['weight'] * aa * (f_og * f_time) * 10) / batch_size if batch_size > 0 else 0

    with col2:
        st.subheader("📊 Analiza")
        st.metric("Gustoća (OG)", f"{og:.3f}")
        st.metric("Gorčina (IBU)", f"{int(total_ibu)}")
        st.metric("Boja (EBC)", f"{ebc}")
        
        # GRAFIČKI PRIKAZ BOJE
        beer_hex = ebc_to_hex(ebc)
        st.markdown(f"""
            <div style="width: 100%; height: 80px; background-color: {beer_hex}; 
            border-radius: 10px; border: 2px solid #333; display: flex; 
            align-items: center; justify-content: center;">
                <span style="color: {'white' if ebc > 30 else 'black'}; font-weight: bold;">PRIKAZ BOJE PIVA</span>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        og_min = selected_style.get('original_gravity', {}).get('minimum', {}).get('value', 1.0)
        og_max = selected_style.get('original_gravity', {}).get('maximum', {}).get('value', 1.1)
        if og_min <= og <= og_max: st.success("Gustoća u stilu! ✅")
        else: st.warning("Gustoća izvan stila! ⚠️")

with tab_tools:
    st.subheader("🛠️ Brewing Tools")
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("🌡️ Strike Water Temperature")
        target_mash = st.number_input("Ciljana temperatura ukomljavanja (°C)", value=67.0)
        grain_temp = st.number_input("Temperatura slada (°C)", value=20.0)
        ratio = st.number_input("Omjer voda/slad (L/kg)", value=3.0)
        # Formula: Ts = (0.41 / R) * (T2 - T1) + T2
        strike_temp = (0.41 / ratio) * (target_mash - grain_temp) + target_mash
        st.success(f"Zagrij vodu na: **{strike_temp:.1f} °C**")

    with c2:
        st.info("🍬 Priming Sugar (Dextrose)")
        co2_vol = st.number_input("Ciljani volumen CO2", value=2.4, step=0.1)
        temp_beer = st.number_input("Temperatura piva pri punjenju (°C)", value=20.0)
        # Pojednostavljena formula za gramažu dekstroze
        sugar_needed = (batch_size * (co2_vol - 3.0378 + (0.050062 * temp_beer) - (0.00026555 * temp_beer**2)) * 4.0)
        st.success(f"Dodaj: **{max(0, int(sugar_needed))} g** dekstroze")
