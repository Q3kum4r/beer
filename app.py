import streamlit as st
import json
import os

# Postavke stranice
st.set_page_config(page_title="BrewMaster Web Pro", layout="wide", page_icon="🍺")

# --- FUNKCIJA ZA UČITAVANJE LOKALNIH DATOTEKA ---
@st.cache_data
def load_data():
    try:
        # Čitamo direktno iz foldera u kojem se nalazi app.py
        with open('brew_data.json', 'r', encoding='utf-8') as f:
            brew_db = json.load(f)
        with open('bjcp_data.json', 'r', encoding='utf-8') as f:
            bjcp_db = json.load(f)
        
        # Ekstrakcija lista prema BrewTarget strukturi
        # BrewTarget JSON obično ima 'hops', 'fermentables' i 'yeasts'
        hops_list = brew_db.get('hops', [])
        malts_list = brew_db.get('fermentables', [])
        
        # Ekstrakcija BJCP stilova
        if isinstance(bjcp_db, list):
            styles_list = bjcp_db
        else:
            styles_list = bjcp_db.get('styles', [])
            
        return hops_list, malts_list, styles_list
    except Exception as e:
        st.error(f"Kritična greška pri učitavanju lokalnih datoteka: {e}")
        return None, None, None

# Pokretanje učitavanja
hops_list, malts_list, styles_list = load_data()

if hops_list is not None:
    # --- LOGIKA IZRAČUNA ---
    def calculate_metrics(selected_malts, selected_hops, batch_size, efficiency):
        total_points = 0
        total_ebc = 0
        for m in selected_malts:
            # BrewTarget 'yield' je postotak (npr. 80.0), 'color' je u SRM/EBC
            potential = m['info'].get('yield', 75.0) * 0.01 * 384 
            points = (m['weight'] * 2.204) * potential * (efficiency / 100)
            total_points += points
            # Boja (Morey formula aproksimacija)
            total_ebc += (m['weight'] * m['info'].get('color', 0) * 4.25) / batch_size
        
        og = 1 + (total_points / (batch_size / 3.785) / 1000)
        
        total_ibu = 0
        for h in selected_hops:
            # Tinseth aproksimacija
            alpha = h['info'].get('alpha_acid', 5.0)
            utilization = 0.24 # Za 60 min kuhanja
            mg_l_alpha = (alpha / 100) * h['weight'] * 1000 / batch_size
            total_ibu += mg_l_alpha * utilization
            
        return og, total_ibu, total_ebc

    # --- KORISNIČKO SUČELJE ---
    st.title("🍺 BrewMaster Web Calculator")
    st.markdown("Korištenje baze: `brew_data.json` i `bjcp_data.json`")

    with st.sidebar:
        st.header("⚙️ Parametri sustava")
        batch_size = st.number_input("Količina šarže (L)", value=20.0, step=1.0)
        efficiency = st.slider("Efikasnost (%)", 50, 95, 75)
        
        st.divider()
        style_names = [s.get('name', 'Nepoznat stil') for s in styles_list]
        selected_style_name = st.selectbox("Ciljani BJCP Stil", style_names)
        style_info = next(s for s in styles_list if s.get('name') == selected_style_name)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🌾 Recept (Slad i Hmelj)")
        
        # Odabir sladova
        malt_names = st.multiselect("Dodaj sladove:", [m['name'] for m in malts_list])
        active_malts = []
        for name in malt_names:
            m_data = next(m for m in malts_list if m['name'] == name)
            col_m1, col_m2 = st.columns([3, 1])
            with col_m1:
                st.write(f"**{name}** ({m_data.get('color', 0)} EBC)")
            with col_m2:
                w = st.number_input(f"kg", value=1.0, step=0.1, key=f"w_{name}", label_visibility="collapsed")
            active_malts.append({'info': m_data, 'weight': w})
        
        st.divider()
        
        # Odabir hmelja
        hop_names = st.multiselect("Dodaj hmeljeve (Gorki):", [h['name'] for h in hops_list])
        active_hops = []
        for name in hop_names:
            h_data = next(h for h in hops_list if h['name'] == name)
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.write(f"**{name}** ({h_data.get('alpha_acid', 0)}% AA)")
            with col_h2:
                g = st.number_input(f"g", value=20.0, step=1.0, key=f"g_{name}", label_visibility="collapsed")
            active_hops.append({'info': h_data, 'weight': g})

    # Izračun rezultata
    og, ibu, ebc = calculate_metrics(active_malts, active_hops, batch_size, efficiency)

    with col2:
        st.subheader("📊 Procjena piva")
        
        # OG Metrika
        st.metric("Original Gravity (OG)", f"{og:.3f}")
        # Sigurno izvlačenje min/max vrijednosti iz BJCP-a
        stats = style_info.get('stats', {}) # Neki BJCP formati imaju stats objekt
        if stats:
            og_min = float(stats.get('og', {}).get('low', 1.0))
            og_max = float(stats.get('og', {}).get('high', 1.1))
        else:
            og_min = float(style_info.get('og_min', 1.0))
            og_max = float(style_info.get('og_max', 1.1))
        
        st.caption(f"Cilj stila: {og_min:.3f} - {og_max:.3f}")
        
        # IBU Metrika
        st.metric("Gorčina (IBU)", f"{int(ibu)}")
        if stats:
            ibu_min = float(stats.get('ibu', {}).get('low', 0))
            ibu_max = float(stats.get('ibu', {}).get('high', 100))
        else:
            ibu_min = float(style_info.get('ibu_min', 0))
            ibu_max = float(style_info.get('ibu_max', 100))
        st.caption(f"Cilj stila: {int(ibu_min)} - {int(ibu_max)}")

        # Vizualni feedback
        st.divider()
        if og_min <= og <= og_max:
            st.success("Gustoća je u stilu! ✅")
        else:
            st.warning("Gustoća odstupa od stila. ⚠️")
            
        if ibu_min <= ibu <= ibu_max:
            st.success("Gorčina je u stilu! ✅")
        else:
            st.warning("Gorčina odstupa od stila. ⚠️")

else:
    st.error("Aplikacija ne može raditi bez ispravnih JSON datoteka.")
