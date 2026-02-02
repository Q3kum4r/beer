import streamlit as st
import json
import os

# Postavke stranice
st.set_page_config(page_title="BrewMaster Pro", layout="wide", page_icon="🍺")

@st.cache_data
def load_data():
    files = {'brew': 'brew_data.json', 'bjcp': 'bjcp_data.json'}
    loaded_data = {}

    for key, filename in files.items():
        if not os.path.exists(filename):
            return f"Datoteka {filename} nije pronađena u repozitoriju!", None, None
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return f"Datoteka {filename} je potpuno prazna!", None, None
                loaded_data[key] = json.loads(content)
        except json.JSONDecodeError as e:
            return f"Greška u formatu {filename}: Možda nije čisti JSON? (Detalji: {e})", None, None
        except Exception as e:
            return f"Neočekivana greška kod {filename}: {e}", None, None

    # Ekstrakcija podataka
    try:
        brew_db = loaded_data['brew']
        bjcp_db = loaded_data['bjcp']
        
        hops = brew_db.get('hops', [])
        malts = brew_db.get('fermentables', [])
        
        # BJCP struktura (prilagođeno za listu ili objekt)
        if isinstance(bjcp_db, list):
            styles = bjcp_db
        else:
            styles = bjcp_db.get('styles', [])
            
        return None, hops, malts, styles
    except Exception as e:
        return f"Greška u strukturi JSON-a: {e}", None, None, None

# Izvršavanje učitavanja
error_msg, hops_list, malts_list, styles_list = load_data()

if error_msg:
    st.error("❌ " + error_msg)
    st.info("Savjet: Provjeri jesu li datoteke na GitHubu 'Public' i jesu li ispravno kopirane (mora biti samo tekst u vitičastim zagradama).")
    st.stop()

# --- LOGIKA IZRAČUNA ---
def calculate_metrics(selected_malts, selected_hops, batch_size, efficiency):
    total_points = 0
    total_ebc = 0
    for m in selected_malts:
        potential = m['info'].get('yield', 75.0) * 0.01 * 384 
        points = (m['weight'] * 2.204) * potential * (efficiency / 100)
        total_points += points
        total_ebc += (m['weight'] * m['info'].get('color', 0) * 4.25) / batch_size
    
    og = 1 + (total_points / (batch_size / 3.785) / 1000)
    
    total_ibu = 0
    for h in selected_hops:
        alpha = h['info'].get('alpha_acid', 5.0)
        utilization = 0.24 
        mg_l_alpha = (alpha / 100) * h['weight'] * 1000 / batch_size
        total_ibu += mg_l_alpha * utilization
        
    return og, total_ibu, total_ebc

# --- KORISNIČKO SUČELJE ---
st.title("🍺 BrewMaster Web Pro")

with st.sidebar:
    st.header("⚙️ Parametri sustava")
    batch_size = st.number_input("Batch Size (L)", value=20.0, step=1.0)
    efficiency = st.slider("Efikasnost (%)", 50, 95, 75)
    
    st.divider()
    style_names = [s.get('name', 'N/A') for s in styles_list]
    selected_style_name = st.selectbox("Ciljani BJCP Stil", style_names)
    style_info = next(s for s in styles_list if s.get('name') == selected_style_name)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🌾 Recept")
    malt_names = st.multiselect("Dodaj sladove:", [m['name'] for m in malts_list])
    active_malts = []
    for name in malt_names:
        m_data = next(m for m in malts_list if m['name'] == name)
        w = st.number_input(f"kg - {name}", value=1.0, step=0.1, key=f"w_{name}")
        active_malts.append({'info': m_data, 'weight': w})
    
    st.divider()
    hop_names = st.multiselect("Dodaj hmeljeve:", [h['name'] for h in hops_list])
    active_hops = []
    for name in hop_names:
        h_data = next(h for h in hops_list if h['name'] == name)
        g = st.number_input(f"g - {name}", value=20.0, step=1.0, key=f"g_{name}")
        active_hops.append({'info': h_data, 'weight': g})

# Izračun
og, ibu, ebc = calculate_metrics(active_malts, active_hops, batch_size, efficiency)

with col2:
    st.subheader("📊 Rezultati")
    st.metric("Original Gravity (OG)", f"{og:.3f}")
    
    stats = style_info.get('stats', {})
    if stats:
        og_min = float(stats.get('og', {}).get('low', 1.0))
        og_max = float(stats.get('og', {}).get('high', 1.1))
    else:
        og_min = float(style_info.get('og_min', 1.0))
        og_max = float(style_info.get('og_max', 1.1))
    
    st.progress(min(max((og - 1.030) / (1.080 - 1.030), 0.0), 1.0))
    st.caption(f"Stil: {og_min:.3f} - {og_max:.3f}")
    
    st.metric("Gorčina (IBU)", f"{int(ibu)}")
    st.metric("Boja (EBC)", f"{int(ebc)}")

    if og_min <= og <= og_max:
        st.success("U stilu! ✅")
    else:
        st.warning("Izvan stila! ⚠️")
