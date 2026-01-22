import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io
import zipfile

st.set_page_config(page_title="Bot Graveur Pro", layout="wide")

st.title("🛡️ Bot de Gravure (Remplacement de texte)")

# --- RÉGLAGES DANS LA BARRE LATÉRALE ---
st.sidebar.header("⚙️ Ajustement du Cache & Texte")
st.sidebar.subheader("Zone à effacer (Rectangle blanc)")
cache_x = st.sidebar.slider("Position X du cache", 0, 500, 135)
cache_y = st.sidebar.slider("Position Y du cache", 0, 300, 40)
cache_largeur = st.sidebar.slider("Largeur du cache", 10, 300, 250)
cache_hauteur = st.sidebar.slider("Hauteur du cache", 10, 100, 60)

st.sidebar.subheader("Réglages Nouveau Texte")
taille_nom = st.sidebar.number_input("Taille Nom", value=18)
taille_titre = st.sidebar.number_input("Taille Titre", value=12)

# --- ZONE DE CHARGEMENT ---
col1, col2 = st.columns(2)
with col1:
    template_file = st.file_uploader("1. Modèle PDF (avec Richard Oliva)", type="pdf")
with col2:
    csv_file = st.file_uploader("2. Liste d'employés (CSV)", type="csv")

def create_badge(template_bytes, first_name, last_name, title):
    reader = PdfReader(io.BytesIO(template_bytes))
    page = reader.pages[0]
    width, height = float(page.mediabox.width), float(page.mediabox.height)

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))
    
    # 1. ON CACHE L'ANCIEN TEXTE
    can.setFillColorRGB(1, 1, 1) # Blanc
    can.rect(cache_x, cache_y, cache_largeur, cache_hauteur, fill=1, stroke=0)
    
    # 2. ON ÉCRIT LE NOUVEAU TEXTE
    can.setFillColorRGB(0, 0, 0) # Noir
    
    full_name = f"{first_name} {last_name}"
    can.setFont("Helvetica-Bold", taille_nom)
    can.drawString(cache_x + 5, cache_y + 35, full_name)
    
    can.setFont("Helvetica", taille_titre)
    can.drawString(cache_x + 5, cache_y + 15, str(title))
    
    can.save()
    packet.seek(0)
    
    overlay = PdfReader(packet).pages[0]
    output = PdfWriter()
    page.merge_page(overlay)
    output.add_page(page)
    
    out_io = io.BytesIO()
    output.write(out_io)
    return out_io.getvalue()

# --- GÉNÉRATION ---
if template_file and csv_file:
    try:
        df = pd.read_csv(csv_file)
        st.success(f"✅ Liste chargée : {len(df)} employés.")
        
        if st.button("🚀 GÉNÉRER LES BADGES"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as z:
                for _, row in df.iterrows():
                    pdf_content = create_badge(template_file.getvalue(), row['Prénom'], row['Nom'], row['Titre'])
                    z.writestr(f"Badge_{row['Prénom']}_{row['Nom']}.pdf", pdf_content)
            
            st.download_button("📥 TÉLÉCHARGER LE PACK ZIP", zip_buffer.getvalue(), "badges_production.zip")
    except Exception as e:
        st.error("Erreur : Vérifiez que votre CSV a bien les colonnes 'Nom', 'Prénom' et 'Titre'.")