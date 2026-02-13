import streamlit as st
import json
import re
import os
import pandas as pd

# --- KONFIGURACIJA ---
st.set_page_config(page_title="BrewMaster Pro", layout="wide", page_icon="🍺")

# --- CSS STILOVI ---
st.markdown("""
<style>
    .bar-bg { width: 100%; background-color: #e0e0e0; border-radius: 10px; height: 20px; margin-top: 5px; }
    .bar-fill { height: 100%; border-radius: 10px; text-align: right; padding-right: 5px; color: white; font-weight: bold; line-height: 20px; font-size: 12px; }
    .metric-box { border: 1px solid #ddd; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .metric-label { font-size: 12px; color: #666; }
    .metric-value { font-size: 20px; font-weight: bold; color: #333; }
</style>
""", unsafe_allow_html=True)

def clean_json_comments(text):
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_data():
    hops, malts, styles, yeasts = [], [], [], []
    try:
        # BJCP
        if os.path.exists('bjcp_data.json'):
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                styles = json.loads(clean_json_comments(f.read())).get('beerjson', {}).get('styles', [])
        # Hmelj i Kvasac
        if os.path.exists('brew_data.json'):
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                d = json.loads(clean_json_comments(f.read())).get('beerjson', {})
                hops = d.get('hop_varieties', [])
                yeasts = d.get('cultures', [])
        # Sladovi
        if os.path.exists('fermentables_data.json'):
            with open('fermentables_data.json', 'r', encoding='utf-8') as f:
                malts = json.load(f).get('beerjson', {}).get('fermentables', [])
    except Exception as e:
        st.error(f"Greška pri učitavanju podataka: {e}")
    return hops, malts, styles, yeasts

hops_db, malts_db, styles_db, yeasts_db = load_data()

# --- SESSION STATE ---
if 'recipe_malts' not in st.session_state: st.session_state.recipe_malts = []
if 'recipe_hops' not in st.session_state: st.session_state.recipe_hops = []

st.title("🍺 BrewMaster - Analizator Recepta")

# --- SIDEBAR: ODABIR STILA ---
with st.sidebar:
    st.header("1. Odaberi Stil")
    style_list = [s['name'] for s in styles_db] if styles_db else ["N/A"]
    target_style_name = st.selectbox("BJCP Stil", style_list)
    
    # Pronađi podatke o odabranom stilu
    style_data = next((s for s in styles_db if s['name'] == target_style_name), {})
    
    if style_data:
        st.subheader("🎯 Ciljane vrijednosti")
        # Izvlačenje limita
        s_og_min = float(style_data.get('original_gravity', {}).get('minimum', {}).get('value', 1.0))
        s_og_max = float(style_data.get('original_gravity', {}).get('maximum', {}).get('value', 1.1))
        s_ibu_min = float(style_data.get('international_bitterness_units', {}).get('minimum', {}).get('value', 0))
        s_ibu_max = float(style_data.get('international_bitterness_units', {}).get('maximum', {}).get('value', 100))
        s_col_min = float(style_data.get('color', {}).get('minimum', {}).get('value', 0))
        s_col_max = float(style_data.get('color', {}).get('maximum', {}).get('value', 40))
        s_abv_min = float(style_data.get('alcohol_by_volume', {}).get('minimum', {}).get('value', 0))
        s_abv_max = float(style_data.get('alcohol_by_volume', {}).get('maximum', {}).get('value', 12))

        # Prikaz ciljeva u sidebaru
        st.info(f"""
        **OG:** {s_og_min:.3f} - {s_og_max:.3f}
        **IBU:** {int(s_ibu_min)} - {int(s_ibu_max)}
        **ABV:** {s_abv_min}% - {s_abv_max}%
        **Boja:** {int(s_col_min)} - {int(s_col_max)} SRM
        """)
    else:
        # Defaultne vrijednosti ako stil nije odabran
        s_og_min, s_og_max = 1.0, 1.1
        s_ibu_min, s_ibu_max = 0, 100
        s_col_min, s_col_max = 0, 40
        s_abv_min, s_abv_max = 0, 12

    st.divider()
    st.header("2. Oprema")
    batch_size = st.number_input("Batch Size (L)", 20.0, step=1.0)
    efficiency = st.number_input("Efikasnost (%)", 70.0, step=5.0)
    boil_time = st.number_input("Vrijeme kuhanja (min)", 60, step=10)

# --- GLAVNI EKRAN: UNOS ---
with st.expander("📝 Uređivanje Recepta", expanded=True):
    c1, c2, c3 = st.columns([1, 1, 1])
    
    # 1. SLADOVI
    with c1:
        st.subheader("🌾 Sladovi")
        sel_malt = st.selectbox("Dodaj slad:", [m['name'] for m in malts_db] if malts_db else [], key="sel_m")
        if st.button("Dodaj Slad"):
            m_dat = next((m for m in malts_db if m['name'] == sel_malt), None)
            if m_dat:
                st.session_state.recipe_malts.append({
                    "Name": m_dat['name'],
                    "Type": str(m_dat.get('type', 'Grain')),
                    "Amount (kg)": 1.0,
                    "Yield (%)": float(m_dat.get('yield', 75)),
                    "Color (EBC)": float(m_dat.get('color', 0))
                })
        
        if st.session_state.recipe_malts:
            df_m = pd.DataFrame(st.session_state.recipe_malts)
            edited_m = st.data_editor(df_m, num_rows="dynamic", use_container_width=True, key="editor_m",
                column_config={"Amount (kg)": st.column_config.NumberColumn(format="%.2f", min_value=0, step=0.1)})
            st.session_state.recipe_malts = edited_m.to_dict('records')

    # 2. HMELJEVI
    with c2:
        st.subheader("🌿 Hmeljevi")
        sel_hop = st.selectbox("Dodaj hmelj:", [h['name'] for h in hops_db] if hops_db else [], key="sel_h")
        if st.button("Dodaj Hmelj"):
            h_dat = next((h for h in hops_db if h['name'] == sel_hop), None)
            if h_dat:
                aa = h_dat.get('alpha_acid', 5.0)
                if isinstance(aa, dict): aa = aa.get('value', 5.0)
                st.session_state.recipe_hops.append({
                    "Name": h_dat['name'], "Amount (g)": 20.0, "Time": 60, "Alpha": float(aa), "Use": "Boil"
                })

        if st.session_state.recipe_hops:
            df_h = pd.DataFrame(st.session_state.recipe_hops)
            edited_h = st.data_editor(df_h, num_rows="dynamic", use_container_width=True, key="editor_h",
                column_config={
                    "Amount (g)": st.column_config.NumberColumn(format="%d"),
                    "Use": st.column_config.SelectboxColumn(options=["Boil", "Dry Hop", "Mash"])
                })
            st.session_state.recipe_hops = edited_h.to_dict('records')

    # 3. KVASAC
    with c3:
        st.subheader("🧫 Kvasac")
        if yeasts_db:
            prods = sorted(list(set([y.get('producer', '?') for y in yeasts_db])))
            s_prod = st.selectbox("Proizvođač", prods)
            av_y = [y for y in yeasts_db if y.get('producer') == s_prod]
            s_id = st.selectbox("Soj", [y.get('product_id', y.get('name')) for y in av_y])
            curr_y = next((y for y in av_y if y.get('product_id') == s_id or y.get('name') == s_id), {})
            
            att_range = curr_y.get('attenuation_range', {})
            att_min = float(att_range.get('minimum', {}).get('value', 70))
            att_max = float(att_range.get('maximum', {}).get('value', 80))
            attenuation = (att_min + att_max) / 2
            st.info(f"**{curr_y.get('name')}**\nAtenuacija: {attenuation:.0f}%")
        else:
            attenuation = 75.0

# --- IZRAČUN ---
pts = 0
mcu = 0
for m in st.session_state.recipe_malts:
    w = float(m['Amount (kg)'])
    y = float(m['Yield (%)'])
    c = float(m['Color (EBC)'])
    # Detekcija ekstrakta
    is_ext = 'extract' in str(m['Type']).lower() or 'sugar' in str(m['Type']).lower() or 'extract' in str(m['Name']).lower()
    eff = 100 if is_ext else efficiency
    pts += w * (y / 100) * 384 * (eff / 100)
    mcu += (w * c) / batch_size if batch_size else 0

og = 1 + (pts / batch_size) / 1000 if batch_size else 1.0
fg = 1 + ((og - 1) * (1 - (attenuation / 100)))
abv = (og - fg) * 131.25
ebc = 1.4922 * (mcu ** 0.6859) * 1.97
srm = ebc * 0.508

ibu = 0
for h in st.session_state.recipe_hops:
    if h['Use'] == 'Boil':
        w = float(h['Amount (g)'])
        a = float(h['Alpha'])
        t = float(h['Time'])
        if batch_size > 0:
            gf = 1.65 * (0.000125 ** (og - 1))
            tf = (1 - 2.71828 ** (-0.04 * t)) / 4.15
            ibu += (w * a * gf * tf * 10) / batch_size

# --- ANALIZA PREMA STILU ---
st.divider()
st.subheader(f"📊 Analiza: {target_style_name}")

# Funkcija za crtanje bara s markerom
def style_meter(label, value, min_v, max_v, unit):
    # Logika boje
    if min_v <= value <= max_v:
        status_color = "#28a745" # Zeleno
        status_icon = "✅"
    else:
        status_color = "#dc3545" # Crveno
        status_icon = "⚠️"
        
    # Pozicija markera u postotcima (s malo paddinga)
    range_span = max_v - min_v
    if range_span == 0: range_span = 1
    # Prikazujemo širi raspon od limita stila
    display_min = min_v - (range_span * 0.5)
    display_max = max_v + (range_span * 0.5)
    
    pct = (value - display_min) / (display_max - display_min) * 100
    pct = max(0, min(100, pct)) # Clamp 0-100
    
    # Pozicija "zelene zone" (stil)
    style_start = (min_v - display_min) / (display_max - display_min) * 100
    style_width = (max_v - min_v) / (display_max - display_min) * 100

    st.markdown(f"""
    <div style="margin-bottom: 15px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
            <span style="font-weight:bold;">{label} {status_icon}</span>
            <span style="font-weight:bold; color:{status_color}">{value:.3f} {unit}</span>
        </div>
        
        <div style="position:relative; width:100%; height:20px; background:#eee; border-radius:10px;">
            <div style="position:absolute; left:{style_start}%; width:{style_width}%; height:100%; background:rgba(40, 167, 69, 0.3); border-left:2px solid #28a745; border-right:2px solid #28a745;"></div>
            
            <div style="position:absolute; left:{pct}%; width:4px; height:120%; top:-10%; background:black; border-radius:2px; z-index:10;"></div>
        </div>
        
        <div style="display:flex; justify-content:space-between; font-size:11px; color:#666; margin-top:2px;">
            <span>Low: {min_v}</span>
            <span>High: {max_v}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    style_meter("Original Gravity (OG)", og, s_og_min, s_og_max, "")
    style_meter("Final Gravity (FG)", fg, 1.008, 1.015, "") # FG je često procjena

with c2:
    style_meter("Bitterness (IBU)", ibu, s_ibu_min, s_ibu_max, "IBU")
    style_meter("Alcohol (ABV)", abv, s_abv_min, s_abv_max, "%")

with c3:
    # Boja hex
    def get_hex(e):
        s = e * 0.508
        if s<2: return "#FFE699"
        if s<6: return "#FFD878"
        if s<12: return "#FBB123"
        if s<20: return "#EA8F00"
        if s<30: return "#D36E00"
        if s<40: return "#8F3300"
        return "#260000"
    
    beer_color = get_hex(ebc)
    style_meter("Color (SRM)", srm, s_col_min, s_col_max, "SRM")
    st.markdown(f'<div style="width:100%; height:30px; background:{beer_color}; border-radius:5px; border:1px solid #999; margin-top:-10px;"></div>', unsafe_allow_html=True)
