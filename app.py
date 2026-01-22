import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io

st.set_page_config(page_title="Nametag Bot Pro", layout="wide")
st.title("🛡️ Bot Nametag Pro (Auto-Fit & Multi-Pages)")

# --- CONFIGURATION ---
st.sidebar.header("1. Paramètres")
nb_badges_total = st.sidebar.number_input("Nombre total de nametags voulus", min_value=1, value=1)
text_to_replace = st.sidebar.text_input("Texte à repérer dans le PDF", "NOM")

st.sidebar.header("2. Source")
mode = st.sidebar.radio("Source des noms :", ["Saisie Manuelle", "Excel/CSV"])

# --- FONCTION DE CALCUL DE TAILLE (Comme le SVG) ---
def get_fitted_size(text, max_width, base_size):
    # Estimation conservatrice de la largeur
    estimated_width = len(text) * base_size * 0.6 
    size = base_size
    while estimated_width > max_width and size > 7:
        size -= 0.5
        estimated_width = len(text) * size * 0.6
    return size

def create_pro_page(template_bytes, search_text, nom="", prenom="", titre=""):
    # Trouver la position automatiquement
    found_box = None
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        page_plumb = pdf.pages[0]
        words = page_plumb.extract_words()
        for w in words:
            if search_text.lower() in w['text'].lower():
                # On convertit les coordonnées vers ReportLab
                found_box = (w['x0'], page_plumb.height - w['bottom'], w['x1'] - w['x0'], w['bottom'] - w['top'])
                break

    reader = PdfReader(io.BytesIO(template_bytes))
    page = reader.pages[0]
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page.mediabox.width, page.mediabox.height))

    if found_box and (nom or prenom):
        x, y, w, h = found_box
        # 1. Effacer l'ancien (Cache blanc)
        can.setFillColorRGB(1, 1, 1)
        can.rect(x - 5, y - 5, w + 10, h + 15, fill=1, stroke=0)
        
        # 2. Préparer le texte
        full_name = f"{prenom} {nom}".strip()
        can.setFillColorRGB(0, 0, 0)
        
        # Ajustement automatique de la taille
        f_size = get_fitted_size(full_name, w + 20, 18)
        can.setFont("Helvetica-Bold", f_size)
        
        # Centrage dans la zone détectée
        can.drawCentredString(x + w/2, y + 5, full_name)
        
        if titre:
            can.setFont("Helvetica", f_size * 0.7)
            can.drawCentredString(x + w/2, y - 10, str(titre))
            
    can.save()
    packet.seek(0)
    overlay = PdfReader(packet).pages[0]
    page.merge_page(overlay)
    return page

# --- LECTURE DES DONNÉES ---
people = []
if mode == "Saisie Manuelle":
    txt = st.text_area("Entrez: Nom, Prénom, Titre (un par ligne)")
    if txt:
        for line in txt.split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if parts[0]:
                people.append({
                    "Nom": parts[0], 
                    "Prénom": parts[1] if len(parts)>1 else "", 
                    "Titre": parts[2] if len(parts)>2 else ""
                })
else:
    f = st.file_uploader("Upload Excel/CSV", type=["csv", "xlsx"])
    if f:
        df = pd.read_csv(f, encoding='latin-1') if f.name.endswith('.csv') else pd.read_excel(f)
        people = df.to_dict('records')

# --- GÉNÉRATION ---
pdf_template = st.file_uploader("3. Upload ton Modèle PDF", type="pdf")

if pdf_template:
    if st.button(f"🔥 GÉNÉRER LE PDF ({nb_badges_total} PAGES)"):
        writer = PdfWriter()
        
        for i in range(nb_badges_total):
            if i < len(people):
                # Badge avec texte
                p = people[i]
                # On essaie de mapper les colonnes intelligemment
                n = p.get('Nom') or p.get('name') or list(p.values())[0]
                pr = p.get('Prénom') or p.get('prenom') or ""
                t = p.get('Titre') or p.get('titre') or ""
                new_page = create_pro_page(pdf_template.getvalue(), text_to_replace, n, pr, t)
            else:
                # Badge vide (juste le gabarit)
                reader = PdfReader(io.BytesIO(pdf_template.getvalue()))
                new_page = reader.pages[0]
            
            writer.add_page(new_page)
        
        final_pdf = io.BytesIO()
        writer.write(final_pdf)
        
        st.success("✅ Terminé !")
        st.download_button("📥 TÉLÉCHARGER LE PDF UNIQUE", final_pdf.getvalue(), "badges_complets.pdf")
