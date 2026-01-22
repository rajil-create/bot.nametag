import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io
import zipfile

st.set_page_config(page_title="Bot Graveur Pro", layout="wide")
st.title("🛡️ Bot de Gravure Intelligent")

# --- BARRE LATÉRALE (FILTRES ET RÉGLAGES) ---
st.sidebar.header("🔍 Recherche & Filtre")
# Cette case permet de taper "A" pour ne voir que les noms commençant par A
filtre_texte = st.sidebar.text_input("Taper un nom ou une lettre :", "")

st.sidebar.header("⚙️ Réglages du Cache")
c_x = st.sidebar.slider("Position X", 0, 500, 135)
c_y = st.sidebar.slider("Position Y", 0, 300, 40)
c_w = st.sidebar.slider("Largeur", 10, 300, 250)
c_h = st.sidebar.slider("Hauteur", 10, 100, 60)

# --- CHARGEMENT ---
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Modèle PDF", type="pdf")
with col2:
    csv_file = st.file_uploader("2. Liste CSV", type="csv")

def generer_un_pdf(template_bytes, n, p, t):
    reader = PdfReader(io.BytesIO(template_bytes))
    page = reader.pages[0]
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page.mediabox.width, page.mediabox.height))
    # Effacer Richard Oliva
    can.setFillColorRGB(1, 1, 1)
    can.rect(c_x, c_y, c_w, c_h, fill=1, stroke=0)
    # Écrire le nouveau nom
    can.setFillColorRGB(0, 0, 0)
    can.setFont("Helvetica-Bold", 18)
    can.drawString(c_x + 5, c_y + 35, f"{p} {n}")
    can.setFont("Helvetica", 12)
    can.drawString(c_x + 5, c_y + 15, str(t))
    can.save()
    packet.seek(0)
    overlay = PdfReader(packet).pages[0]
    out = PdfWriter()
    page.merge_page(overlay)
    out.add_page(page)
    final = io.BytesIO()
    out.write(final)
    return final.getvalue()

if pdf_file and csv_file:
    try:
        # Lecture automatique même si séparateur différent
        df = pd.read_csv(csv_file, sep=None, engine='python')
        # On nettoie les noms de colonnes (enlève espaces et met en minuscule pour comparer)
        df.columns = [c.strip() for c in df.columns]
        
        # On cherche les bonnes colonnes intelligemment
        col_nom = next((c for c in df.columns if "nom" in c.lower() and "pré" not in c.lower()), None)
        col_pre = next((c for c in df.columns if "pré" in c.lower() or "pre" in c.lower()), None)
        col_titre = next((c for c in df.columns if "titre" in c.lower()), None)

        if col_nom and col_pre and col_titre:
            # APPLICATION DU FILTRE (ex: "A")
            if filtre_texte:
                df = df[df[col_nom].str.contains(filtre_texte, case=False, na=False) | 
                        df[col_pre].str.contains(filtre_texte, case=False, na=False)]
            
            st.success(f"✅ {len(df)} employés trouvés")
            st.dataframe(df[[col_nom, col_pre, col_titre]].head())

            if st.button(f"🚀 GÉNÉRER {len(df)} BADGES"):
                zip_path = io.BytesIO()
                with zipfile.ZipFile(zip_path, "w") as z:
                    for _, row in df.iterrows():
                        p_content = generer_un_pdf(pdf_file.getvalue(), row[col_nom], row[col_pre], row[col_titre])
                        z.writestr(f"Badge_{row[col_nom]}.pdf", p_content)
                st.download_button("📥 TÉLÉCHARGER LE ZIP", zip_path.getvalue(), "production.zip")
        else:
            st.error(f"Colonnes détectées : {list(df.columns)}. Vérifiez qu'il y a 'Nom', 'Prénom' et 'Titre'.")
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
