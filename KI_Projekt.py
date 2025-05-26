# === Notwendige Bibliotheken einbinden ===
import streamlit as st
import pandas as pd
import re
import google.generativeai as genai
from dotenv import load_dotenv

# === Farben & Styles ===
THEME_COLOR = "#78BE20"
LIGHT_BG = "#F5F5F5"
TEXT_COLOR = "#333333"
CARD_COLOR = "#E8F5E9"

# === Dateipfade ===
EXCEL_FILE = "KI_Projekt.xlsx"
THEMEN_FILE = "Sustainable Development in Economics Sciences 2024.xlsx"

# === Streamlit-Seiteneinstellungen ===
st.set_page_config(page_title="\U0001F4D8 Modulübersicht", layout="wide")

# === CSS-Styling ===
st.markdown(f"""
    <style>
    body {{
        background-color: {LIGHT_BG};
        color: {TEXT_COLOR};
        font-family: "Segoe UI", sans-serif;
    }}
    .card {{
        background-color: {CARD_COLOR};
        padding: 1em;
        margin-bottom: 1em;
        border-radius: 10px;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
    }}
    .category-title {{
        color: {THEME_COLOR};
        font-size: 1.3em;
        margin-top: 1.5em;
        margin-bottom: 0.2em;
    }}
    .stDataFrame div[role="gridcell"] {{
        white-space: pre-wrap !important;
        overflow-wrap: break-word;
        word-wrap: break-word;
    }}
    </style>
""", unsafe_allow_html=True)

# === Titel anzeigen ===
st.title("\U0001F393 WWF Classification Tool")

# === Secrets sicher laden ===
load_dotenv()
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    APP_PASSWORD = st.secrets["APP_PASSWORD"]
except AttributeError:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    APP_PASSWORD = os.getenv("APP_PASSWORD")

# === Passwortschutz ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "login_attempted" not in st.session_state:
    st.session_state.login_attempted = False

if not st.session_state.authenticated:
    pw = st.text_input("\U0001F511 Passwort eingeben:", type="password")
    if st.button("Einloggen"):
        st.session_state.login_attempted = True
        if pw == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Das Passwort ist falsch.")

    if not st.session_state.authenticated:
        st.stop() # Stoppt App-Ausführung bis Login erfolgreich ist

# === Logout ===
with st.sidebar:
    if st.session_state.authenticated:
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()

# === Gemini initialisieren ===
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# === WWF-Themen laden ===
@st.cache_data
def load_wwf_labels():
    df = pd.read_excel(THEMEN_FILE, sheet_name=0).dropna()
    return (df["Subject areas"] + ": " + df["Description"]).tolist()

wwf_labels = load_wwf_labels()

# === Session States ===
for key, default in {
    "selected_studienrichtungen": [],
    "suchbegriff": "",
        "confidence_threshold": 60
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# === Confidence-Einstellung ===
st.session_state.confidence_threshold = st.number_input(
    label="📊 Minimale Confidence (%) zur Anzeige", 
    min_value=0, 
    max_value=100, 
    value=st.session_state.confidence_threshold, 
    step=1,
    help="Nur Themen mit dieser minimalen Wahrscheinlichkeit werden angezeigt."
)

# === Hilfsfunktionen ===
def parse_themen_mit_confidence(text):
    if "kein treffer" in text.lower():
        return ["Kein Treffer"]
    themen = []
    for line in text.strip().split("\n"):
        match = re.match(r"-\s*(.+?):\s*(\d+)%", line.strip())
        if match:
            thema = match.group(1).strip()
            confidence = int(match.group(2))
            if confidence >= st.session_state.confidence_threshold:
                themen.append(f"{thema} ({confidence}%)")
    return themen if themen else ["Kein Treffer"]

def extract_confidence(val):
    try:
        return int(val.split('%')[0].split('(')[-1])
    except:
        return 0

def classify_wwf_with_gemini(modultext, wwf_themen_liste):
    if pd.isna(modultext) or not str(modultext).strip():
        return "Kein Treffer"

    prompt = (
        "Du bist ein KI-Modell zur Klassifikation nach Nachhaltigkeitsthemen.\n"
        "Ordne folgenden Modultext einem oder mehreren dieser WWF-Themen zu. "
        "Gib eine geschätzte Zuversicht (Confidence) in Prozent an. Wenn kein Thema passt, gib 'Kein Treffer' zurück.\n\n"
    )
    for thema in wwf_themen_liste:
        prompt += f"- {thema}\n"
    prompt += (
        f"\nModulbeschreibung:\n{modultext}\n\n"
        "Antwortformat:\n- Thema A: 90%\n- Thema B: 70%\nOder:\nKein Treffer"
    )

    try:
        response = model.generate_content(prompt)
        themen = parse_themen_mit_confidence(response.text)
        return "\n".join(themen)
    except Exception as e:
        return f"Fehler: {e}"

# === Hauptlogik ===
try:
    all_sheets = pd.read_excel(EXCEL_FILE, sheet_name=None, header=None)
    kategorien = {}

    for sheet_name, df in all_sheets.items():
        if df.shape[0] >= 2:
            kategorie = str(df.iloc[0, 0]).strip()
            studienrichtung = str(df.iloc[1, 0]).strip()
            kategorien.setdefault(kategorie, {})[studienrichtung] = sheet_name

    def update_search():
        st.session_state.suchbegriff = st.session_state.temp_suchbegriff.strip().lower()

    st.text_input("🔎 Studienrichtung suchen", value=st.session_state.suchbegriff, key="temp_suchbegriff", on_change=update_search)
    st.markdown("### ✅ Studienrichtungen zur Auswahl:")

    anzeigen_counter = 0
    for kategorie, richtungen in kategorien.items():
        gefiltert = {r: s for r, s in richtungen.items() if st.session_state.suchbegriff in r.lower()}
        if not gefiltert:
            continue
        anzeigen_counter += len(gefiltert)
        st.markdown(f"<div class='category-title'>{kategorie}</div>", unsafe_allow_html=True)
        for richtung, sheetname in gefiltert.items():
            key = f"{kategorie}_{richtung}"
            checked = st.checkbox(richtung, key=key)
            if checked:
                if key not in st.session_state.selected_studienrichtungen:
                    st.session_state.selected_studienrichtungen.append(key)
            else:
                if key in st.session_state.selected_studienrichtungen:
                    st.session_state.selected_studienrichtungen.remove(key)

    if anzeigen_counter == 0:
        st.info("🔍 Keine passenden Studienrichtungen gefunden.")

    if st.button("🔍 Module analysieren"):
        st.session_state.analysierte_module = []
        for kategorie, richtungen in kategorien.items():
            for richtung, sheetname in richtungen.items():
                key = f"{kategorie}_{richtung}"
                if key not in st.session_state.selected_studienrichtungen:
                    continue
                df = all_sheets[sheetname]
                df.dropna(how="all", inplace=True)
                df_module = df.iloc[4:].reset_index(drop=True)
                df_module.columns = ["Modul Bezeichnung", "Modultyp", "Modul Beschreibung"]

                themen_liste = []
                for beschreibung in df_module["Modul Beschreibung"]:
                    themen = classify_wwf_with_gemini(beschreibung, wwf_labels)
                    themen_liste.append(themen)

                df_module["WWF Themen"] = themen_liste
                df_module.drop(columns=["Modul Beschreibung"], inplace=True)

                st.markdown(f"## 🎓 {richtung}")
                st.markdown(f"<div class='card'><strong>Kategorie:</strong> {kategorie}</div>", unsafe_allow_html=True)

                styled_df = df_module.style.applymap(
                    lambda val: (
                        'background-color: #d0f0c0' if isinstance(val, str) and '%' in val and extract_confidence(val) >= 80
                        else 'background-color: #fff3cd' if 60 <= extract_confidence(val) < 80
                        else 'background-color: #f8d7da' if extract_confidence(val) < 60
                        else ''
                    ),
                    subset=["WWF Themen"]
                )

                st.dataframe(styled_df, use_container_width=True, hide_index=False)
                                
        st.session_state.module_analyse_erfolgreich = True

except FileNotFoundError:
    st.error(f"❌ Die Datei '{EXCEL_FILE}' oder '{THEMEN_FILE}' wurde nicht gefunden.")
except Exception as e:
    st.error(f"❌ Fehler beim Einlesen oder Analysieren: {e}")
