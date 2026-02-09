import streamlit as st
import json
import re
import os
import sqlite3
import hashlib

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="BrewMaster SaaS", layout="wide", page_icon="🍺")

# --- DATABASE LOGIKA (SQLite) ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Tablica korisnika
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    # Tablica recepata
    c.execute('''CREATE TABLE IF NOT EXISTS recipes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT, 
                  recipe_name TEXT, 
                  og TEXT, 
                  ibu TEXT, 
                  ebc TEXT, 
                  abv TEXT,
                  FOREIGN KEY(username) REFERENCES users(username))''')
    conn.commit()
    conn.close()

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def add_userdata(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username, password) VALUES (?,?)', (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username =? AND password =?', (username, password))
    data = c.fetchall()
    conn.close()
    return data

def save_recipe(username, name, og, ibu, ebc, abv):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO recipes(username, recipe_name, og, ibu, ebc, abv) VALUES (?,?,?,?,?,?)', 
              (username, name, og, ibu, ebc, abv))
    conn.commit()
    conn.close()

def get_user_recipes(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT recipe_name, og, ibu, ebc, abv FROM recipes WHERE username = ?', (username,))
    data = c.fetchall()
    conn.close()
    return data

# --- UČITAVANJE PODATAKA ---
def clean_json_comments(text):
    text = re.sub(r'//.*', '', text)
    return text.strip()

@st.cache_data
def load_all_databases():
    hops, malts, styles, yeasts = [], [], [], []
    if os.path.exists('bjcp_data.json'):
        try:
            with open('bjcp_data.json', 'r', encoding='utf-8') as f:
                data = json.loads(clean_json_comments(f.read()))
                styles = data.get('beerjson', {}).get('styles', [])
        except: pass
    if os.path.exists('brew_data.json'):
        try:
            with open('brew_data.json', 'r', encoding='utf-8') as f:
                content = clean_json_comments(f.read())
                full_data = json.loads(content).get('beerjson', {})
                hops = full_data.get('hop_varieties', [])
                yeasts = full_data.get('cultures', [])
        except: pass
    if os.path.exists('fermentables_data.json'):
        try:
            with open('fermentables_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f).get('beerjson', {})
                malts = data.get('fermentables', [])
        except: pass
    return hops, malts, styles, yeasts

def ebc_to_hex(ebc):
    srm = ebc * 0.508
    if srm < 2: return "#FFE699"
    elif srm < 15: return "#FBB123"
    elif srm < 40: return "#BD5400"
    elif srm < 70: return "#420000"
    return "#000000"

# --- MAIN ---
def main():
    init_db()
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🍺 BrewMaster SaaS Login")
        auth_choice = st.sidebar.selectbox("Izbornik", ["Prijava", "Registracija"])
        
        if auth_choice == "Registracija":
            new_user = st.text_input("Korisničko ime")
            new_pass = st.text_input("Lozinka", type='password')
            if st.button("Kreiraj račun"):
                if add_userdata(new_user, make_hashes(new_pass)):
                    st.success("Registracija uspješna! Prijavi se.")
                else: st.error("Korisnik već postoji.")
        else:
            user = st.text_input("Korisničko ime")
            pw = st.text_input("Lozinka", type='password')
            if st.button("Prijavi se"):
                if login_user(user, make_hashes(pw)):
                    st.session_state.logged_in = True
                    st.session_state.username = user
                    st.rerun()
                else: st.error("Pogrešni podaci.")
    else:
        # APLIKACIJA ZA PRIJAVLJENE
        hops_db, malts_db, styles_db, yeasts_db = load_all_databases()
        
        with st.sidebar:
            st.title(f"Živjeli, {st.session_state.username}!")
            if st.button("Odjavi se"):
                st.session_state.logged_in = False
                st.rerun()
            st.divider()
            batch_size = st.number_input("Batch (L)", value=20.0)
            efficiency = st.slider("Efikasnost (%)", 40, 100, 75)
            style_name = st.selectbox("BJCP Stil", [s['name'] for s in styles_db])
            selected_style = next((s for s in styles_db if s['name'] == style_name), {})

        tab_recipe, tab_my_recipes = st.tabs(["🆕 Novi Recept", "📚 Moja Knjižnica"])

        with tab_recipe:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("🌾 Grain Bill & Hops")
                m_selection = st.multiselect("Sladovi (kg):", [m['name'] for m in malts_db])
                total_gravity_pts, total_mcu = 0, 0
                for nm in m_selection:
                    m_info = next(m for m in malts_db if m['name'] == nm)
                    w = st.number_input(f"kg: {nm}", value=1.0, min_value=0.0, step=0.1, key=f"m_{nm}")
                    yield_pct = float(m_info.get('yield', 75.0))
                    total_gravity_pts += (w * (yield_pct/100*384) * (100 if "Extract" in nm else efficiency)/100) / batch_size
                    total_mcu += (w * float(m_info.get('color', 0))) / batch_size

                h_selection = st.multiselect("Hmeljevi (g):", [h['name'] for h in hops_db])
                active_hops_list = []
                for nh in h_selection:
                    h_info = next(h for h in hops_db if h['name'] == nh)
                    aa = float(h_info.get('alpha_acid', {}).get('value', 5.0))
                    g = st.number_input(f"g: {nh}", value=20.0, min_value=0.0, step=1.0, key=f"h_{nh}")
                    active_hops_list.append((g, aa))

                if yeasts_db:
                    y_name = st.selectbox("Kvasac:", [y['name'] for y in yeasts_db])
                    selected_yeast = next(y for y in yeasts_db if y['name'] == y_name)
                    att_range = selected_yeast.get('attenuation_range', {})
                    attenuation = (float(att_range.get('minimum', {}).get('value', 70)) + float(att_range.get('maximum', {}).get('value', 80))) / 2
                else: attenuation = 75.0

            # IZRAČUN
            og = 1 + (total_gravity_pts / 1000)
            fg = 1 + ((og - 1) * (1 - (attenuation / 100.0)))
            abv = (og - fg) * 131.25
            ebc = int((1.4922 * ((total_mcu/1.97)**0.6859)) * 1.97) if total_mcu > 0 else 0
            
            total_ibu = 0
            for g, aa in active_hops_list:
                f_og = 1.65 * (0.000125**(og - 1))
                f_time = (1 - 2.718**(-0.04 * 60)) / 4.15
                total_ibu += (g * aa * (f_og * f_time) * 10) / batch_size

            with col2:
                st.subheader("📊 Analiza")
                st.metric("ABV", f"{abv:.1f} %")
                st.metric("OG", f"{og:.3f}")
                st.metric("IBU", f"{int(total_ibu)}")
                st.metric("EBC", f"{ebc}")
                st.markdown(f'<div style="width: 100%; height: 40px; background-color: {ebc_to_hex(ebc)}; border-radius: 5px; border: 1px solid #555;"></div>', unsafe_allow_html=True)
                
                st.divider()
                recipe_save_name = st.text_input("Naziv recepta za spremanje")
                if st.button("💾 Spremi Recept"):
                    if recipe_save_name:
                        save_recipe(st.session_state.username, recipe_save_name, f"{og:.3f}", str(int(total_ibu)), str(ebc), f"{abv:.1f}")
                        st.success(f"Recept '{recipe_save_name}' je spremljen!")
                    else: st.warning("Unesi naziv recepta.")

        with tab_my_recipes:
            st.subheader("📜 Moji spremljeni recepti")
            user_recipes = get_user_recipes(st.session_state.username)
            if user_recipes:
                for r in user_recipes:
                    with st.expander(f"🍺 {r[0]}"):
                        c1, c2, c3, c4 = st.columns(4)
                        c1.write(f"**OG:** {r[1]}")
                        c2.write(f"**IBU:** {r[2]}")
                        c3.write(f"**EBC:** {r[3]}")
                        c4.write(f"**ABV:** {r[4]}%")
            else: st.info("Još nemaš spremljenih recepata.")

if __name__ == '__main__':
    main()
