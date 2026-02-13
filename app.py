import streamlit as st
import json
import re
import os
import pandas as pd

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="BrewMaster Pro", layout="wide", page_icon="🍺")

# --- CSS ZA LJEPŠI PRIKAZ ---
st.markdown("""
<style>
    .bar-bg { width: 100%; background-color: #e0e0e0; border-radius: 10px; height: 20px; margin-top: 5px; }
    .bar-fill { height: 100%; border-radius: 10px; text-align: right; padding-right: 5px; color: white; font-weight: bold; line-height: 20px; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

def clean_json_comments(text):
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_data():
    hops, malts, styles, yeasts = [], [], [], []
    try:
        # Učitavanje BJCP
        if os.path.exists('bjcp_data.json'):
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                styles = json.loads(clean_json_comments(f.read())).get('beerjson', {}).get('styles', [])
        
        # Učitavanje Hmeljeva i Kvasaca
        if os.path.exists('brew_data.json'):
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                d = json.loads(clean_json_comments(f.read())).get('beerjson', {})
                hops = d.get('hop_varieties', [])
                yeasts = d.get('cultures', []) # Tvoj format ima 'cultures'
        
        # Učitavanje Sladova
        if os.path.exists('fermentables_data.json'):
            with open('fermentables_data.json', 'r', encoding='utf-8') as f:
                malts = json.load(f).get('beerjson', {}).get('fermentables', [])
    except Exception as e:
        st.error(f"Greška pri učitavanju podataka: {e}")
    return hops, malts, styles, yeasts

hops_db, malts_db, styles_db, yeasts_db = load_data()

# --- SESSION STATE (Pamtimo recept dok klikćeš) ---
if 'recipe_malts' not in st.session_state:
    st.session_state.recipe_malts = []
if 'recipe_hops' not in st.session_state:
    st.session_state.recipe_hops = []

st.title("🍺 BrewMaster - Recipe Builder")

# --- GORNJI DIO: POSTAVKE ---
with st.expander("⚙️ Postavke Opreme", expanded=True):
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1: batch_size = st.number_input("Batch Size (L)", 20.0, step=1.0)
    with col_s2: efficiency = st.number_input("Mash Efficiency (%)", 70.0, step=5.0)
    with col_s3: boil_time = st.number_input("Vrijeme kuhanja (min)", 60, step=10)
    with col_s4: 
        style_list = [s['name'] for s in styles_db] if styles_db else ["N/A"]
        target_style_name = st.selectbox("Ciljani Stil", style_list)
        target_style = next((s for s in styles_db if s['name'] == target_style_name), {})

# --- 1. TABLICA SLADOVA (FERMENTABLES) ---
st.subheader("🌾 Fermentables (Sastojci)")
col_add_m1, col_add_m2 = st.columns([3, 1])
with col_add_m1:
    selected_malt_add = st.selectbox("Odaberi slad/ekstrakt:", [m['name'] for m in malts_db] if malts_db else [])
with col_add_m2:
    if st.button("➕ Dodaj Slad"):
        malt_data = next((m for m in malts_db if m['name'] == selected_malt_add), None)
        if malt_data:
            # Tu je bila greška - sada spremamo sigurno
            st.session_state.recipe_malts.append({
                "Name": malt_data['name'],
                "Type": str(malt_data.get('type', 'Grain')), # Osigurač: pretvori u tekst
                "Amount (kg)": 1.0,
                "Yield (%)": float(malt_data.get('yield', 75)),
                "Color (EBC)": float(malt_data.get('color', 0))
            })

if st.session_state.recipe_malts:
    df_malts = pd.DataFrame(st.session_state.recipe_malts)
    edited_malts = st.data_editor(
        df_malts, num_rows="dynamic", use_container_width=True,
        column_config={
            "Amount (kg)": st.column_config.NumberColumn(format="%.2f kg", min_value=0, step=0.1),
            "Yield (%)": st.column_config.NumberColumn(format="%.1f %%", disabled=True),
            "Color (EBC)": st.column_config.NumberColumn(format="%.1f EBC", disabled=True),
            "Type": st.column_config.TextColumn(disabled=True)
        }
    )
    st.session_state.recipe_malts = edited_malts.to_dict('records')

# --- 2. TABLICA HMELJEVA (HOPS) ---
st.subheader("🌿 Hops (Hmeljevi)")
col_add_h1, col_add_h2 = st.columns([3, 1])
with col_add_h1:
    selected_hop_add = st.selectbox("Odaberi hmelj:", [h['name'] for h in hops_db] if hops_db else [])
with col_add_h2:
    if st.button("➕ Dodaj Hmelj"):
        hop_data = next((h for h in hops_db if h['name'] == selected_hop_add), None)
        if hop_data:
            # Alpha acid može biti broj ili objekt
            aa = hop_data.get('alpha_acid', 5.0)
            if isinstance(aa, dict): aa = aa.get('value', 5.0)
            
            st.session_state.recipe_hops.append({
                "Name": hop_data['name'],
                "Amount (g)": 20.0,
                "Time (min)": 60,
                "Alpha (%)": float(aa),
                "Use": "Boil"
            })

if st.session_state.recipe_hops:
    df_hops = pd.DataFrame(st.session_state.recipe_hops)
    edited_hops = st.data_editor(
        df_hops, num_rows="dynamic", use_container_width=True,
        column_config={
            "Amount (g)": st.column_config.NumberColumn(format="%d g", min_value=0, step=1),
            "Time (min)": st.column_config.NumberColumn(min_value=0, step=5),
            "Alpha (%)": st.column_config.NumberColumn(format="%.1f %%"),
            "Use": st.column_config.SelectboxColumn(options=["Boil", "Dry Hop", "Mash", "Whirlpool"])
        }
    )
    st.session_state.recipe_hops = edited_hops.to_dict('records')

# --- 3. KVASAC ---
st.subheader("🧫 Kvasac")
if yeasts_db:
    # Poboljšani selektor (Proizvođač -> Soj)
    producers = sorted(list(set([y.get('producer', 'Unknown') for y in yeasts_db])))
    c_y1, c_y2 = st.columns(2)
    with c_y1: sel_prod = st.selectbox("Proizvođač", producers)
    
    avail_yeasts = [y for y in yeasts_db if y.get('producer') == sel_prod]
    # Ako nema Product ID, koristi Name
    with c_y2: sel_yeast_id = st.selectbox("Soj", [y.get('product_id', y.get('name')) for y in avail_yeasts])
    
    current_yeast = next((y for y in avail_yeasts if y.get('product_id') == sel_yeast_id or y.get('name') == sel_yeast_id), {})
    
    # Izračun atenuacije
    att_range = current_yeast.get('attenuation_range', {})
    if att_range:
        att_min = float(att_range.get('minimum', {}).get('value', 70))
        att_max = float(att_range.get('maximum', {}).get('value', 80))
        attenuation = (att_min + att_max) / 2
    else:
        attenuation = 75.0 # Default ako nema podataka
        
    st.info(f"💡 Odabran: **{current_yeast.get('name')}** (Atenuacija: ~{attenuation:.0f}%)")
else:
    attenuation = 75.0
    st.warning("Baza kvasaca je prazna.")

# --- 4. GLAVNE KALKULACIJE (POPRAVLJENO) ---
total_points = 0
total_mcu = 0

for m in st.session_state.recipe_malts:
    w_kg = float(m['Amount (kg)'])
    yield_pct = float(m['Yield (%)'])
    color = float(m['Color (EBC)'])
    
    # === POPRAVAK GREŠKE ===
    # Sigurna konverzija tipa u tekst (string) prije .lower()
    m_type_raw = m.get('Type', '')
    m_type = str(m_type_raw).lower()
    m_name = str(m.get('Name', '')).lower()
    
    # Pametna detekcija: Je li ovo ekstrakt/šećer?
    # Gledamo i TIP i IME. Ako piše "Extract" ili "Sugar", efikasnost je 100%
    is_extract = ('extract' in m_type) or ('sugar' in m_type) or ('extract' in m_name) or ('sugar' in m_name)
    item_eff = 100 if is_extract else efficiency
    
    # Izračun bodova gustoće
    # Formula: kg * (Yield% / 100) * 384 (pts/kg/L) * (Eff / 100)
    points = w_kg * (yield_pct / 100) * 384 * (item_eff / 100)
    total_points += points
    
    total_mcu += (w_kg * color) / batch_size if batch_size > 0 else 0

# Finalni brojevi
og = 1 + (total_points / batch_size) / 1000 if batch_size > 0 else 1.0
fg = 1 + ((og - 1) * (1 - (attenuation / 100)))
abv = (og - fg) * 131.25
ebc = 1.4922 * (total_mcu ** 0.6859) * 1.97

total_ibu = 0
for h in st.session_state.recipe_hops:
    if h.get('Use') == "Boil":
        w_g = float(h['Amount (g)'])
        alpha = float(h['Alpha (%)'])
        time = float(h['Time (min)'])
        if batch_size > 0:
            gf = 1.65 * (0.000125 ** (og - 1))
            tf = (1 - 2.71828 ** (-0.04 * time)) / 4.15
            total_ibu += (w_g * alpha * gf * tf * 10) / batch_size

# --- 5. DASHBOARD REZULTATA ---
st.divider()
st.subheader("📊 Analiza Recepta")

def custom_bar(label, value, min_v, max_v, unit, color_gradient):
    pct = max(0, min(100, (value - min_v) / (max_v - min_v) * 100)) if max_v > min_v else 0
    st.markdown(f"""
    <div style="margin-bottom: 8px;">
        <div style="display:flex; justify-content:space-between; font-size:14px; font-weight:bold;">
            <span>{label}</span><span>{value:.3f} {unit}</span>
        </div>
        <div style="width:100%; background-color:#ddd; height:18px; border-radius:10px;">
            <div style="width:{pct}%; background:{color_gradient}; height:100%; border-radius:10px;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:10px; color:#666;">
            <span>{min_v:.3f}</span><span>{max_v:.3f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Dohvati granice stila
if target_style:
    s_og_min = float(target_style.get('original_gravity', {}).get('minimum', {}).get('value', 1.000))
    s_og_max = float(target_style.get('original_gravity', {}).get('maximum', {}).get('value', 1.100))
    s_fg_min = float(target_style.get('final_gravity', {}).get('minimum', {}).get('value', 1.000))
    s_fg_max = float(target_style.get('final_gravity', {}).get('maximum', {}).get('value', 1.030))
    s_abv_min = float(target_style.get('alcohol_by_volume', {}).get('minimum', {}).get('value', 0))
    s_abv_max = float(target_style.get('alcohol_by_volume', {}).get('maximum', {}).get('value', 12))
    s_ibu_min = float(target_style.get('international_bitterness_units', {}).get('minimum', {}).get('value', 0))
    s_ibu_max = float(target_style.get('international_bitterness_units', {}).get('maximum', {}).get('value', 100))
else:
    s_og_min, s_og_max = 1.0, 1.1
    s_fg_min, s_fg_max = 1.0, 1.03
    s_abv_min, s_abv_max = 0, 10
    s_ibu_min, s_ibu_max = 0, 100

c1, c2, c3 = st.columns(3)
with c1:
    custom_bar("OG", og, s_og_min - 0.01, s_og_max + 0.01, "", "linear-gradient(90deg, #a8e063, #56ab2f)")
    custom_bar("FG", fg, s_fg_min - 0.005, s_fg_max + 0.005, "", "linear-gradient(90deg, #a8e063, #56ab2f)")
with c2:
    custom_bar("ABV", abv, s_abv_min - 1, s_abv_max + 2, "%", "linear-gradient(90deg, #4facfe, #00f2fe)")
    custom_bar("IBU", total_ibu, 0, s_ibu_max + 20, "", "linear-gradient(90deg, #ff9966, #ff5e62)")
with c3:
    def get_hex(e):
        s = e * 0.508
        if s<2: return "#FFE699"
        if s<6: return "#FFD878"
        if s<12: return "#FBB123"
        if s<20: return "#EA8F00"
        if s<30: return "#D36E00"
        return "#260000"
    custom_bar("Color", ebc, 0, 80, " EBC", get_hex(ebc))
