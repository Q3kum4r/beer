import streamlit as st
import json
import re
import os
import pandas as pd

# --- KONFIGURACIJA ---
st.set_page_config(page_title="BrewMaster Pro", layout="wide", page_icon="🍺")

# --- CSS ZA PROGRESS BAROVE (DA IZGLEDAJU KAO NA SLICI) ---
st.markdown("""
<style>
    .metric-container {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .bar-bg {
        width: 100%;
        background-color: #e0e0e0;
        border-radius: 10px;
        height: 20px;
        margin-top: 5px;
    }
    .bar-fill {
        height: 100%;
        border-radius: 10px;
        text-align: right;
        padding-right: 5px;
        color: white;
        font-weight: bold;
        line-height: 20px;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

# --- UČITAVANJE PODATAKA ---
def clean_json_comments(text):
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_data():
    hops, malts, styles, yeasts = [], [], [], []
    try:
        if os.path.exists('bjcp_data.json'):
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                styles = json.loads(clean_json_comments(f.read())).get('beerjson', {}).get('styles', [])
        if os.path.exists('brew_data.json'):
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                d = json.loads(clean_json_comments(f.read())).get('beerjson', {})
                hops = d.get('hop_varieties', [])
                yeasts = d.get('cultures', [])
        if os.path.exists('fermentables_data.json'):
            with open('fermentables_data.json', 'r', encoding='utf-8') as f:
                malts = json.load(f).get('beerjson', {}).get('fermentables', [])
    except Exception as e:
        st.error(f"Greška pri učitavanju podataka: {e}")
    return hops, malts, styles, yeasts

hops_db, malts_db, styles_db, yeasts_db = load_data()

# --- INICIJALIZACIJA SESSION STATE ZA RECEPTE ---
if 'recipe_malts' not in st.session_state:
    st.session_state.recipe_malts = []
if 'recipe_hops' not in st.session_state:
    st.session_state.recipe_hops = []

# --- UI LOGIKA ---
st.title("🍺 BrewMaster - Recipe Builder")

# Gornji dio - Postavke
with st.expander("⚙️ Postavke Opreme", expanded=True):
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1: batch_size = st.number_input("Batch Size (L)", 20.0, step=1.0)
    with col_s2: efficiency = st.number_input("Mash Efficiency (%)", 70.0, step=5.0)
    with col_s3: boil_time = st.number_input("Vrijeme kuhanja (min)", 60, step=10)
    with col_s4: 
        style_list = [s['name'] for s in styles_db] if styles_db else ["N/A"]
        target_style_name = st.selectbox("Ciljani Stil", style_list)
        target_style = next((s for s in styles_db if s['name'] == target_style_name), {})

# --- TABLICA SLADOVA ---
st.subheader("🌾 Fermentables (Sastojci)")
col_add_m1, col_add_m2 = st.columns([3, 1])
with col_add_m1:
    selected_malt_add = st.selectbox("Odaberi slad/ekstrakt za dodavanje:", [m['name'] for m in malts_db] if malts_db else [])
with col_add_m2:
    if st.button("➕ Dodaj Slad"):
        malt_data = next((m for m in malts_db if m['name'] == selected_malt_add), None)
        if malt_data:
            # Dodajemo novi red u session state
            st.session_state.recipe_malts.append({
                "Name": malt_data['name'],
                "Type": malt_data.get('type', 'Grain'),
                "Amount (kg)": 1.0, # Default
                "Yield (%)": float(malt_data.get('yield', 75)),
                "Color (EBC)": float(malt_data.get('color', 0))
            })

# Prikaz i uređivanje tablice (Data Editor)
if st.session_state.recipe_malts:
    df_malts = pd.DataFrame(st.session_state.recipe_malts)
    edited_malts = st.data_editor(
        df_malts, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Amount (kg)": st.column_config.NumberColumn(min_value=0, max_value=50, step=0.1, format="%.2f kg"),
            "Yield (%)": st.column_config.NumberColumn(format="%.1f %%", disabled=True),
            "Color (EBC)": st.column_config.NumberColumn(format="%.1f EBC", disabled=True),
            "Type": st.column_config.TextColumn(disabled=True)
        }
    )
    # Ažuriraj session state s novim vrijednostima iz tablice
    st.session_state.recipe_malts = edited_malts.to_dict('records')
else:
    st.info("Dodaj sladove koristeći izbornik iznad.")

# --- TABLICA HMELJEVA ---
st.subheader("🌿 Hops (Hmeljevi)")
col_add_h1, col_add_h2 = st.columns([3, 1])
with col_add_h1:
    selected_hop_add = st.selectbox("Odaberi hmelj:", [h['name'] for h in hops_db] if hops_db else [])
with col_add_h2:
    if st.button("➕ Dodaj Hmelj"):
        hop_data = next((h for h in hops_db if h['name'] == selected_hop_add), None)
        if hop_data:
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
        df_hops,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Amount (g)": st.column_config.NumberColumn(min_value=0, max_value=500, step=1, format="%d g"),
            "Time (min)": st.column_config.NumberColumn(min_value=0, max_value=120, step=5),
            "Alpha (%)": st.column_config.NumberColumn(format="%.1f %%"),
            "Use": st.column_config.SelectboxColumn(options=["Boil", "Dry Hop", "Mash", "Whirlpool"])
        }
    )
    st.session_state.recipe_hops = edited_hops.to_dict('records')

# --- KVASAC ---
st.subheader("🧫 Kvasac")
if yeasts_db:
    producers = sorted(list(set([y.get('producer', 'Unknown') for y in yeasts_db])))
    c_y1, c_y2 = st.columns(2)
    with c_y1: sel_prod = st.selectbox("Proizvođač", producers)
    
    avail_yeasts = [y for y in yeasts_db if y.get('producer') == sel_prod]
    with c_y2: sel_yeast_id = st.selectbox("Soj", [y.get('product_id', 'N/A') for y in avail_yeasts])
    
    current_yeast = next((y for y in avail_yeasts if y.get('product_id') == sel_yeast_id), {})
    
    # Atenuacija
    att_range = current_yeast.get('attenuation_range', {})
    att_min = float(att_range.get('minimum', {}).get('value', 70))
    att_max = float(att_range.get('maximum', {}).get('value', 80))
    attenuation = (att_min + att_max) / 2
    st.caption(f"{current_yeast.get('name')} | Avg. Attenuation: {attenuation}%")
else:
    attenuation = 75.0

# --- KALKULACIJE ---
total_points = 0
total_mcu = 0

for m in st.session_state.recipe_malts:
    w_kg = m['Amount (kg)']
    yield_pct = m['Yield (%)']
    color = m['Color (EBC)']
    m_type = m['Type'].lower()
    
    # Ako je ekstrakt ili šećer, efikasnost je 100%, inače koristimo zadanu efikasnost
    item_eff = 100 if ('extract' in m_type or 'sugar' in m_type) else efficiency
    
    # Formula: kg * (Yield% / 100) * 384 (pts/kg/L) * (Eff / 100)
    # Rezultat je u Gravity Points * L
    points = w_kg * (yield_pct / 100) * 384 * (item_eff / 100)
    total_points += points
    
    total_mcu += (w_kg * color) / batch_size

# OG
if batch_size > 0:
    og = 1 + (total_points / batch_size) / 1000
else:
    og = 1.0

# FG
fg = 1 + ((og - 1) * (1 - (attenuation / 100)))

# ABV
abv = (og - fg) * 131.25

# EBC
ebc = 1.4922 * (total_mcu ** 0.6859) * 1.97 # Dodatni faktor za usklađivanje s modernim formulama

# IBU
total_ibu = 0
for h in st.session_state.recipe_hops:
    if h['Use'] == "Boil":
        w_g = h['Amount (g)']
        alpha = h['Alpha (%)']
        time = h['Time (min)']
        
        # Tinseth
        if batch_size > 0:
            gravity_factor = 1.65 * (0.000125 ** (og - 1))
            time_factor = (1 - 2.71828 ** (-0.04 * time)) / 4.15
            utilization = gravity_factor * time_factor
            ibu = (w_g * alpha * utilization * 10) / batch_size
            total_ibu += ibu

# --- VIZUALNI REZULTATI (DASHBOARD) ---
st.divider()
st.subheader("📊 Analiza Recepta")

# Funkcija za progress bar
def custom_bar(label, value, min_v, max_v, unit, color_gradient):
    pct = max(0, min(100, (value - min_v) / (max_v - min_v) * 100)) if max_v > min_v else 0
    st.markdown(f"""
    <div style="margin-bottom: 10px;">
        <div style="display:flex; justify-content:space-between; font-size:14px; font-weight:bold;">
            <span>{label}</span>
            <span>{value:.3f} {unit}</span>
        </div>
        <div style="width:100%; background-color:#ddd; height:20px; border-radius:10px; overflow:hidden;">
            <div style="width:{pct}%; background:{color_gradient}; height:100%; text-align:right; padding-right:5px; line-height:20px; color:white; font-size:12px;">
            </div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:10px; color:#666;">
            <span>{min_v}</span>
            <span>{max_v}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Dohvati granice stila
s_og_min = float(target_style.get('original_gravity', {}).get('minimum', {}).get('value', 1.000))
s_og_max = float(target_style.get('original_gravity', {}).get('maximum', {}).get('value', 1.100))
s_fg_min = float(target_style.get('final_gravity', {}).get('minimum', {}).get('value', 1.000))
s_fg_max = float(target_style.get('final_gravity', {}).get('maximum', {}).get('value', 1.030))
s_abv_min = float(target_style.get('alcohol_by_volume', {}).get('minimum', {}).get('value', 0))
s_abv_max = float(target_style.get('alcohol_by_volume', {}).get('maximum', {}).get('value', 12))
s_ibu_min = float(target_style.get('international_bitterness_units', {}).get('minimum', {}).get('value', 0))
s_ibu_max = float(target_style.get('international_bitterness_units', {}).get('maximum', {}).get('value', 100))
s_col_min = float(target_style.get('color', {}).get('minimum', {}).get('value', 0))
s_col_max = float(target_style.get('color', {}).get('maximum', {}).get('value', 40))

c1, c2, c3 = st.columns(3)

with c1:
    custom_bar("Original Gravity", og, s_og_min - 0.010, s_og_max + 0.010, "", "linear-gradient(90deg, #a8e063, #56ab2f)")
    custom_bar("Final Gravity", fg, s_fg_min - 0.005, s_fg_max + 0.005, "", "linear-gradient(90deg, #a8e063, #56ab2f)")

with c2:
    custom_bar("Alcohol (ABV)", abv, s_abv_min - 1, s_abv_max + 2, "%", "linear-gradient(90deg, #4facfe, #00f2fe)")
    custom_bar("Bitterness (IBU)", total_ibu, 0, s_ibu_max + 20, "IBU", "linear-gradient(90deg, #43e97b, #38f9d7)")

with c3:
    # Boja - poseban tretman
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
    custom_bar("Color (EBC)", ebc, 0, 80, "EBC", beer_color)
    st.write(f"Stil: {s_col_min}-{s_col_max} EBC")
