import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io
import zipfile

st.set_page_config(page_title="Bot Graveur Pro", layout="wide")
st.title("🛡️ Bot de Gravure (Manuel ou CSV)")

# --- BARRE LATÉRALE ---
st.sidebar.header("🔍 Options")
mode = st.sidebar.radio("Choisir la source :", ["Fichier CSV", "Saisie Manuelle"])

st.sidebar.header("⚙️ Réglages Cache")
c_x = st.sidebar.slider("Position X", 0, 500, 135)
c_y = st.sidebar.slider("Position Y", 0, 300, 40)
c_w = st.sidebar.slider("Largeur", 10, 300, 250)
c_h = st.sidebar.slider("Hauteur", 10, 100, 60)

# --- ZONE DE CHARGEMENT MODÈLE ---
pdf_file = st.file_uploader("1. Charger le Modèle PDF", type="pdf")

def create_badge(template_bytes, n, p, t):
    reader = PdfReader(io.BytesIO(template_bytes))
    page = reader.pages[0]
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page.mediabox.width, page.mediabox.height))
    can.setFillColorRGB(1, 1, 1) # Cache blanc
    can.rect(c_x, c_y, c_w, c_h, fill=1, stroke=0)
    can.setFillColorRGB(0, 0, 0) # Texte noir
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

# --- TRAITEMENT DES DONNÉES ---
data_ready = False
df = pd.DataFrame()

if mode == "Saisie Manuelle":
    st.subheader("✍️ Saisie directe")
    txt_input = st.text_area("Entrez les noms (Format: Nom, Prénom, Titre)", 
                             placeholder="NOM, Prénom, Poste\nALEX, Jean, Directeur")
    if txt_input:
        lines = [line.split(',') for line in txt_input.split('\n') if ',' in line]
        df = pd.DataFrame(lines, columns=['Nom', 'Prénom', 'Titre'])
        data_ready = True

else:
    st.subheader("📂 Chargement CSV")
    csv_file = st.file_uploader("Charger votre liste d'employés", type="csv")
    if csv_file:
        try:
            # Correction de l'erreur d'accent (encoding latin-1)
            df = pd.read_csv(csv_file, encoding='latin-1', sep=None, engine='python')
            df.columns = [c.strip() for c in df.columns]
            # Mapping intelligent des colonnes
            col_nom = next((c for c in df.columns if "nom" in c.lower() and "pré" not in c.lower()), None)
            col_pre = next((c for c in df.columns if "pré" in c.lower() or "pre" in c.lower()), None)
            col_titre = next((c for c in df.columns if "titre" in c.lower()), None)
            
            if col_nom and col_pre and col_titre:
                df = df.rename(columns={col_nom: 'Nom', col_pre: 'Prénom', col_titre: 'Titre'})
                data_ready = True
            else:
                st.error("Colonnes introuvables. Vérifiez que votre CSV contient : Nom, Prénom, Titre")
        except Exception as e:
            st.error(f"Erreur : {e}")

# --- FILTRE ET GÉNÉRATION ---
if data_ready and pdf_file:
    # Option de filtrage rapide
    search = st.text_input("🔍 Filtrer la liste (ex: tapez 'A')")
    if search:
        df = df[df['Nom'].str.contains(search, case=False, na=False) | 
                df['Prénom'].str.contains(search, case=False, na=False)]
    
    st.write(f"### Liste à générer ({len(df)} badges)")
    st.dataframe(df)

    if st.button("🚀 GÉNÉRER TOUS LES PDF"):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as z:
            for _, row in df.iterrows():
                content = create_badge(pdf_file.getvalue(), row['Nom'], row['Prénom'], row['Titre'])
                z.writestr(f"Badge_{row['Nom']}_{row['Prénom']}.pdf", content)
        
        st.download_button("📥 TÉLÉCHARGER LE ZIP", zip_buffer.getvalue(), "badges_gravure.zip")
