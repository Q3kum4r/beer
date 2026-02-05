import streamlit as st
import json
import re
import os

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="BrewMaster Pro", layout="wide", page_icon="🍺")

def clean_json_comments(text):
    """Uklanja komentare iz datoteka koji kvare JSON parser."""
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_all_databases():
    hops, malts, styles, yeasts = [], [], [], []
    
    # 1. BJCP Stilovi
    if os.path.exists('bjcp_data.json'):
        try:
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                data = json.loads(clean_json_comments(f.read()))
                styles = data.get('beerjson', {}).get('styles', [])
        except Exception as e: st.error(f"BJCP Error: {e}")

    # 2. Hmeljevi i Kvasci (brew_data.json)
    if os.path.exists('brew_data.json'):
        try:
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                content = clean_json_comments(f.read())
                full_data = json.loads(content).get('beerjson', {})
                hops = full_data.get('hop_varieties', [])
                yeasts = full_data.get('cultures', []) # Tvoj format koristi 'cultures'
        except Exception as e: st.error(f"Brew Data Error: {e}")

    # 3. Sladovi (fermentables_data.json)
    if os.path.exists('fermentables_data.json'):
        try:
            with open('fermentables_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f).get('beerjson', {})
                malts = data.get('fermentables', [])
        except Exception as e: st.error(f"Malt Data Error: {e}")
        
    return hops, malts, styles, yeasts

hops_db, malts_db, styles_db, yeasts_db = load_all_databases()

# --- POMOĆNA FUNKCIJA ZA BOJU ---
def ebc_to_hex(ebc):
    srm = ebc * 0.508
    if srm < 2: return "#FFE699"
    elif srm < 5: return "#FFD878"
    elif srm < 8: return "#FFCA5A"
    elif srm < 12: return "#FFBF42"
    elif srm < 15: return "#FBB123"
    elif srm < 18: return "#F8A600"
    elif srm < 22: return "#F39C00"
    elif srm < 26: return "#EA8F00"
    elif srm < 30: return "#E58500"
    elif srm < 35: return "#D36E00"
    elif srm < 40: return "#BD5400"
    elif srm < 50: return "#8F3300"
    elif srm < 60: return "#611200"
    elif srm < 70: return "#420000"
    return "#000000"

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Parametri sustava")
    batch_size = st.number_input("Količina piva (L)", value=20.0, step=1.0)
    efficiency = st.slider("Sustavna efikasnost (%)", 40, 100, 75)
    
    st.divider()
    style_names = [s['name'] for s in styles_db] if styles_db else ["N/A"]
    style_choice = st.selectbox("Ciljani BJCP Stil", style_names)
    selected_style = next((s for s in styles_db if s['name'] == style_choice), {})

# --- GLAVNI PROZOR ---
tab_recipe, tab_tools = st.tabs(["📋 Planiranje Recepta", "🧮 Pomoćni Kalkulatori"])

with tab_recipe:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # SEKCIJA ZA SLADOVE
        st.subheader("🌾 Grain Bill (kg)")
        m_selection = st.multiselect("Odaberi sladove/ekstrakte:", [m['name'] for m in malts_db])
        active_malts = []
        total_gravity_pts = 0
        total_mcu = 0
        
        for name in m_selection:
            m_info = next(m for m in malts_db if m['name'] == name)
            c1, c2 = st.columns([3, 1])
            with c1: st.write(f"**{name}** ({m_info.get('color', 0)} EBC)")
            with c2: w = st.number_input(f"kg", value=1.0, min_value=0.0, step=0.1, key=f"m_{name}", label_visibility="collapsed")
            
            # MATEMATIKA ZA OG
            yield_pct = float(m_info.get('yield', 75.0))
            # 100% yield u 1L daje 384 gravity points. 
            points_per_kg = (yield_pct / 100.0) * 384.0
            
            # Ekstrakti i šećeri su 100% efikasni
            m_type = str(m_info.get('type', '')).lower()
            current_eff = 100 if ('extract' in m_type or 'sugar' in m_type or 'extract' in name.lower()) else efficiency
            
            total_gravity_pts += (w * points_per_kg * (current_eff / 100.0)) / batch_size
            total_mcu += (w * float(m_info.get('color', 0))) / batch_size
            active_malts.append({'info': m_info, 'weight': w})

        st.divider()
        # SEKCIJA ZA HMELJEVE
        st.subheader("🌿 Hmeljevi (g)")
        h_selection = st.multiselect("Dodaj hmeljeve (60 min):", [h['name'] for h in hops_db])
        active_hops = []
        for name in h_selection:
            h_info = next(h for h in hops_db if h['name'] == name)
            aa_data = h_info.get('alpha_acid', 5.0)
            aa = float(aa_data.get('value', 5.0)) if isinstance(aa_data, dict) else float(aa_data)
            c1, c2 = st.columns([3, 1])
            with c1: st.write(f"**{name}** ({aa}% Alpha)")
            with c2: g = st.number_input(f"g", value=20.0, min_value=0.0, step=1.0, key=f"h_{name}", label_visibility="collapsed")
            active_hops.append({'weight': g, 'aa': aa})

        st.divider()
        # SEKCIJA ZA KVASAC (Redizajnirano)
        st.subheader("🧫 Kvasac")
        if yeasts_db:
            producers = sorted(list(set([y.get('producer', 'Nepoznat') for y in yeasts_db])))
            sel_producer = st.selectbox("Proizvođač:", producers)
            
            filtered_yeasts = [y for y in yeasts_db if y.get('producer') == sel_producer]
            yeast_ids = [y.get('product_id', 'N/A') for y in filtered_yeasts]
            sel_id = st.selectbox("Product ID (Vrsta):", yeast_ids)
            
            sel_yeast = next(y for y in filtered_yeasts if y.get('product_id') == sel_id)
            st.info(f"💡 **Preporuka/Stil:** {sel_yeast.get('name', 'N/A')}")
            
            att_range = sel_yeast.get('attenuation_range', {})
            att_min = float(att_range.get('minimum', {}).get('value', 70))
            att_max = float(att_range.get('maximum', {}).get('value', 80))
            attenuation = (att_min + att_max) / 2
        else:
            attenuation = 75.0

    # --- IZRAČUN REZULTATA ---
    og = 1 + (total_gravity_pts / 1000)
    fg = 1 + ((og - 1) * (1 - (attenuation / 100.0)))
    abv = (og - fg) * 131.25
    ebc = int((1.4922 * ((total_mcu/1.97)**0.6859)) * 1.97) if total_mcu > 0 else 0

    total_ibu = 0
    for h in active_hops:
        f_og = 1.65 * (0.000125**(og - 1))
        f_time = (1 - 2.718**(-0.04 * 60)) / 4.15
        total_ibu += (h['weight'] * h['aa'] * (f_og * f_time) * 10) / batch_size if batch_size > 0 else 0

    with col2:
        st.subheader("📊 Analiza")
        st.metric("Alkohol (ABV)", f"{abv:.1f} %")
        st.metric("Gustoća (OG)", f"{og:.3f}")
        st.metric("Završna (FG)", f"{fg:.3f}")
        st.metric("Gorčina (IBU)", f"{int(total_ibu)}")
        st.metric("Boja (EBC)", f"{ebc}")
        
        # VIZUALNI PRIKAZ BOJE
        beer_hex = ebc_to_hex(ebc)
        st.markdown(f"""
            <div style="width: 100%; height: 60px; background-color: {beer_hex}; 
            border-radius: 10px; border: 2px solid #555; display: flex; 
            align-items: center; justify-content: center;">
                <span style="color: {'white' if ebc > 25 else 'black'}; font-weight: bold;">BOJA PIVA</span>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        if selected_style:
            og_min = float(selected_style.get('original_gravity', {}).get('minimum', {}).get('value', 1.0))
            og_max = float(selected_style.get('original_gravity', {}).get('maximum', {}).get('value', 1.1))
            if og_min <= og <= og_max: st.success("OG u stilu! ✅")
            else: st.warning(f"OG van stila ({og_min:.3f}-{og_max:.3f})")

with tab_tools:
    st.subheader("🛠️ Brewing Tools")
    # (Strike water i Priming sugar ostaju isti)
