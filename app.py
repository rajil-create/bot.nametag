import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter
import io
import re

st.set_page_config(page_title="Nametag Engine Pro", layout="wide")

# --- LOGIQUE DE CALCUL (Inspirée de ton code GPT 5.2) ---
def get_fitted_font_size(text, max_w, base_size, min_size=6):
    """ Réduit la police jusqu'à ce que le texte rentre dans la largeur max """
    # Estimation : Largeur = nombre de caractères * taille * facteur de correction
    k = 0.55 # Facteur pour Helvetica-Bold
    size = base_size
    while (len(text) * size * k) > max_w and size > min_size:
        size -= 0.5
    return size

def get_anchor_point(template_bytes, search_term):
    """ Détecte où se trouve le texte placeholder dans le PDF """
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        for w in words:
            if search_term.lower() in w['text'].lower():
                # On retourne le centre X, la base Y, et la largeur dispo
                return {
                    "cx": (w['x0'] + w['x1']) / 2,
                    "y": page.height - w['bottom'], 
                    "width": (w['x1'] - w['x0'])
                }
    return None

# --- UI STREAMLIT ---
st.title("🛡️ Nametag Professional Engine")
st.markdown("Structure de sortie : **Un seul PDF** contenant tous les badges demandés.")

with st.sidebar:
    st.header("Configuration")
    target = st.text_input("Texte à repérer (ex: NOM)", "NOM")
    total_wanted = st.number_input("Nombre de badges total à générer", min_value=1, value=6)
    base_font = st.slider("Taille de police de base", 10, 40, 20)
    
    st.divider()
    mode = st.radio("Source des données", ["Saisie Manuelle", "Fichier Excel/CSV"])

# --- DATA PREP ---
people = []
if mode == "Saisie Manuelle":
    raw_text = st.text_area("Collez ici (Nom, Prénom, Titre)")
    if raw_text:
        for line in raw_text.split('\n'):
            if ',' in line:
                parts = [p.strip() for p in line.split(',')]
                people.append({"Nom": parts[0], "Prénom": parts[1] if len(parts)>1 else "", "Titre": parts[2] if len(parts)>2 else ""})
else:
    f = st.file_uploader("Upload Excel/CSV", type=["csv", "xlsx"])
    if f:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        people = df.to_dict('records')

# --- GENERATION ---
template_file = st.file_uploader("📁 Upload ton Gabarit PDF (Propre de préférence)", type="pdf")

if template_file and st.button(f"🚀 Générer {total_wanted} Nametags"):
    # 1. Analyse du point d'ancrage
    anchor = get_anchor_point(template_file.getvalue(), target)
    
    if not anchor:
        st.error(f"❌ Impossible de trouver '{target}' dans le gabarit. Vérifie l'orthographe.")
    else:
        output_pdf = PdfWriter()
        template_reader = PdfReader(io.BytesIO(template_file.getvalue()))
        
        progress = st.progress(0)
        
        for i in range(total_wanted):
            # Prendre les infos si dispo, sinon badge vide
            person = people[i] if i < len(people) else None
            
            # Créer une couche de texte transparente (Overlay)
            packet = io.BytesIO()
            tpl_page = template_reader.pages[0]
            can = canvas.Canvas(packet, pagesize=(tpl_page.mediabox.width, tpl_page.mediabox.height))
            
            if person:
                # Logique de fusion Nom + Prénom
                nom = str(person.get('Nom', person.get('name', ''))).upper()
                prenom = str(person.get('Prénom', person.get('prenom', '')))
                full_text = f"{prenom} {nom}".strip()
                titre = str(person.get('Titre', person.get('title', '')))
                
                # Calcul de la taille auto-fit (Comme dans ton SVG)
                # On multiplie la largeur de l'ancre par 1.5 pour donner un peu de marge
                f_size = get_fitted_font_size(full_text, anchor['width'] * 1.5, base_font)
                
                # Dessin du texte centré sur l'ancre
                can.setFont("Helvetica-Bold", f_size)
                can.drawCentredString(anchor['cx'], anchor['y'] + 2, full_text)
                
                if titre and titre.lower() != "nan":
                    can.setFont("Helvetica", f_size * 0.6)
                    can.drawCentredString(anchor['cx'], anchor['y'] - (f_size * 0.7), titre)
            
            can.save()
            packet.seek(0)
            
            # Fusionner l'overlay avec le gabarit original
            new_overlay = PdfReader(packet).pages[0]
            final_page = PdfReader(io.BytesIO(template_file.getvalue())).pages[0]
            final_page.merge_page(new_overlay)
            output_pdf.add_page(final_page)
            
            progress.progress((i + 1) / total_wanted)

        # Export final
        final_buffer = io.BytesIO()
        output_pdf.write(final_buffer)
        st.success("✅ PDF Professionnel Généré !")
        st.download_button("📥 Télécharger le PDF (Format Impression)", final_buffer.getvalue(), "nametags_production.pdf")
