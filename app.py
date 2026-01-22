import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io
import zipfile

st.set_page_config(page_title="Bot Graveur Pro", layout="wide")
st.title("🛡️ Bot de Gravure Intelligent")

# --- RÉGLAGES ---
st.sidebar.header("⚙️ Configuration")
search_term = st.sidebar.text_input("🔍 Filtrer par nom (ex: A ou Martin)", "")

st.sidebar.subheader("Zone à effacer")
cache_x = st.sidebar.slider("Position X", 0, 500, 135)
cache_y = st.sidebar.slider("Position Y", 0, 300, 40)
cache_largeur = st.sidebar.slider("Largeur", 10, 300, 250)
cache_hauteur = st.sidebar.slider("Hauteur", 10, 100, 60)

# --- CHARGEMENT ---
col1, col2 = st.columns(2)
with col1:
    template_file = st.file_uploader("1. Modèle PDF", type="pdf")
with col2:
    csv_file = st.file_uploader("2. Liste CSV", type="csv")

def create_badge(template_bytes, nom, prenom, titre):
    reader = PdfReader(io.BytesIO(template_bytes))
    page = reader.pages[0]
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page.mediabox.width, page.mediabox.height))
    # On cache l'ancien texte
    can.setFillColorRGB(1, 1, 1)
    can.rect(cache_x, cache_y, cache_largeur, cache_hauteur, fill=1, stroke=0)
    # On écrit le nouveau
    can.setFillColorRGB(0, 0, 0)
    can.setFont("Helvetica-Bold", 18)
    can.drawString(cache_x + 5, cache_y + 35, f"{prenom} {nom}")
    can.setFont("Helvetica", 12)
    can.drawString(cache_x + 5, cache_y + 15, str(titre))
    can.save()
    packet.seek(0)
    overlay = PdfReader(packet).pages[0]
    output = PdfWriter()
    page.merge_page(overlay)
    output.add_page(page)
    out_io = io.BytesIO()
    output.write(out_io)
    return out_io.getvalue()

if template_file and csv_file:
    try:
        # Lecture flexible du CSV
        df = pd.read_csv(csv_file)
        # Nettoyage des noms de colonnes (enlève les espaces)
        df.columns = df.columns.str.strip()
        
        # Vérification des colonnes
        if not all(col in df.columns for col in ['Nom', 'Prénom', 'Titre']):
            st.error(f"Colonnes trouvées : {list(df.columns)}. Besoin de : 'Nom', 'Prénom', 'Titre'.")
        else:
            # FILTRE DE RECHERCHE
            if search_term:
                df = df[df['Nom'].str.startswith(search_term, na=False) | 
                        df['Prénom'].str.startswith(search_term, na=False)]
            
            st.write(f"✅ {len(df)} employés sélectionnés")
            st.dataframe(df.head()) # Affiche un aperçu

            if st.button("🚀 GÉNÉRER LES BADGES FILTRÉS"):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as z:
                    for _, row in df.iterrows():
                        pdf_content = create_badge(template_file.getvalue(), row['Nom'], row['Prénom'], row['Titre'])
                        z.writestr(f"Badge_{row['Nom']}.pdf", pdf_content)
                st.download_button("📥 TÉLÉCHARGER LE ZIP", zip_buffer.getvalue(), "badges.zip")
    except Exception as e:
        st.error(f"Erreur technique : {e}")
