# === Notwendige Bibliotheken einbinden ===
import streamlit as st
import pandas as pd
import os
import google.generativeai as genai
from dotenv import load_dotenv

# === Farben & Styles ===
THEME_COLOR = "#78BE20"
LIGHT_BG = "#F5F5F5"
TEXT_COLOR = "#333333"
CARD_COLOR = "#E8F5E9"

# === Dateipfade für Eingabedaten definieren ===
EXCEL_FILE = "KI_Projekt.xlsx"
THEMEN_FILE = "Sustainable Development in Economics Sciences 2024.xlsx"

# === Streamlit-Seiteneinstellungen ===
st.set_page_config(page_title="\U0001F4D8 Modulübersicht", layout="wide")

# === Benutzerdefiniertes CSS Styling ===
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

# === Titel der App anzeigen ===
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

# === Logout-Button in der Sidebar ===
with st.sidebar:
    if st.session_state.get("authenticated", False):
        if st.button("\U0001F6AA Logout"):
            st.session_state.authenticated = False
            st.rerun()

# === Gemini API Initialisierung ===
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# === WWF-Themenliste aus Excel laden und als Liste formatieren ===
@st.cache_data
def load_wwf_labels():
    df = pd.read_excel(THEMEN_FILE, sheet_name=0).dropna()
    return (df["Subject areas"] + ": " + df["Description"]).tolist()

wwf_labels = load_wwf_labels()

# === Session States initialisieren (für UI-Zustand) ===
if "selected_studienrichtungen" not in st.session_state:
    st.session_state.selected_studienrichtungen = []
if "suchbegriff" not in st.session_state:
    st.session_state.suchbegriff = ""
if "module_analyse_erfolgreich" not in st.session_state:
    st.session_state.module_analyse_erfolgreich = False
if "analysierte_module" not in st.session_state:
    st.session_state.analysierte_module = []

# === Modultext mit Gemini nach WWF-Themen klassifizieren ===
def classify_wwf_with_gemini(modultext, wwf_themen_liste):
    if pd.isna(modultext) or not str(modultext).strip():
        return "Kein Treffer"
    
    # Prompt erstellen: Liste aller Themen + Modultext
    prompt = (
        "Du bist ein KI-Modell zur Klassifikation nach Nachhaltigkeitsthemen.\n"
        "Ordne folgenden Modultext einem oder mehreren dieser WWF-Themen zu (wenn keine zutreffen, schreibe 'Kein Treffer'):\n\n"
    )
    for thema in wwf_themen_liste:
        prompt += f"- {thema}\n"
    prompt += f"\nModulbeschreibung:\n{modultext}\n\n"
    prompt += "Gib nur die zutreffenden Themen als Liste untereinander zurück, jedes Thema beginnend mit '- '."
    try:
        response = model.generate_content(prompt)
        # Extrahiere die Themen, zerlege sauber und mache Zeilenumbruch
        themen = [t.strip() for t in response.text.strip().split(",") if t.strip()]
        if not themen or themen[0].lower().startswith("keine") or themen[0].lower() == "kein treffer":
            return "Kein Treffer"
        return "\n".join(themen)
    except Exception as e:
        return f"Fehler: {e}"

# === Hauptlogik zur Verarbeitung der Modul-Excel ===
try:
    all_sheets = pd.read_excel(EXCEL_FILE, sheet_name=None, header=None)
    kategorien = {}

    # Kategorien & Studienrichtungen aus der Datei extrahieren
    for sheet_name, df in all_sheets.items():
        if df.shape[0] >= 2:
            kategorie = str(df.iloc[0, 0]).strip()
            studienrichtung = str(df.iloc[1, 0]).strip()
            if kategorie not in kategorien:
                kategorien[kategorie] = {}
            kategorien[kategorie][studienrichtung] = sheet_name

    # Suchbegriff aktualisieren, wenn Nutzer in Suchfeld tippt
    def update_search():
        st.session_state.suchbegriff = st.session_state.temp_suchbegriff.strip().lower()
    
    # UI: Suchfeld für Studienrichtungen   
    st.text_input("\U0001F50D Studienrichtung suchen ",
                 value=st.session_state.suchbegriff,
                 key="temp_suchbegriff",
                 on_change=update_search)

    # Checkbox-Auswahl für Studienrichtungen anzeigen
    suchbegriff = st.session_state.suchbegriff
    st.markdown("### ✅ Studienrichtungen zur Auswahl:")
    anzeigen_counter = 0

    for kategorie, richtungen in kategorien.items():
        gefiltert = {r: s for r, s in richtungen.items() if suchbegriff in r.lower()}
        if not gefiltert:
            continue
        anzeigen_counter += len(gefiltert)
        st.markdown(f"<div class='category-title'>{kategorie}</div>", unsafe_allow_html=True)
        for richtung, sheetname in gefiltert.items():
            key = f"{kategorie}_{richtung}"
            checked = st.checkbox(richtung, key=key)
            if checked and key not in st.session_state.selected_studienrichtungen:
                st.session_state.selected_studienrichtungen.append(key)
            elif not checked and key in st.session_state.selected_studienrichtungen:
                st.session_state.selected_studienrichtungen.remove(key)

    # Falls keine Übereinstimmungen mit Suchbegriff gefunden wurden
    if anzeigen_counter == 0:
        st.info("\U0001F50E Keine Studienrichtungen gefunden, die zum Suchbegriff passen.")

    # === Analyse starten ===
    if st.button("\U0001F50D Module analysieren"):
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

                # Modulbeschreibungen klassifizieren
                themen_liste = []
                for beschreibung in df_module["Modul Beschreibung"]:
                    themen = classify_wwf_with_gemini(beschreibung, wwf_labels)
                    themen_liste.append(themen)
                df_module["WWF Themen"] = themen_liste
                df_module.drop(columns=["Modul Beschreibung"], inplace=True)

                 # Ergebnisse anzeigen
                st.markdown(f"## \U0001F393 {richtung}")
                st.markdown(f"<div class='card'><strong>Kategorie:</strong> {kategorie}</div>", unsafe_allow_html=True)
                st.dataframe(df_module, use_container_width=True, hide_index=False)
                st.session_state.analysierte_module.extend(df_module["Modul Bezeichnung"].tolist())
        st.session_state.module_analyse_erfolgreich = True

# === Fehlerbehandlung für fehlende Dateien oder sonstige Probleme ===
except FileNotFoundError:
    st.error(f"❌ Die Datei '{EXCEL_FILE}' oder '{THEMEN_FILE}' wurde nicht gefunden.")
except Exception as e:
    st.error(f"❌ Fehler beim Einlesen oder Analysieren: {e}")
