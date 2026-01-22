import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pypdf import PdfReader, PdfWriter
import io

st.set_page_config(page_title="Nametag Single Page Pro", layout="wide")

# --- PARAMÈTRES TECHNIQUES ---
GAP = 0.5 * inch  # L'espacement de 0.5 inch demandé

def get_fitted_font_size(text, max_w, base_size):
    k = 0.55 # Facteur pour Helvetica-Bold
    size = base_size
    while (len(text) * size * k) > max_w and size > 7:
        size -= 0.5
    return size

def get_anchor_point(template_bytes, search_term):
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        for w in words:
            if search_term.lower() in w['text'].lower():
                return {
                    "cx": (w['x0'] + w['x1']) / 2,
                    "y": page.height - w['bottom'], 
                    "width": (w['x1'] - w['x0']),
                    "orig_h": page.height,
                    "orig_w": page.width
                }
    return None

st.title("🎯 Planche de Production (Une seule page)")

with st.sidebar:
    st.header("1. Réglages")
    target = st.text_input("Texte repère (ex: NOM)", "NOM")
    nb_total = st.number_input("Nombre de badges total", min_value=1, value=6)
    cols = st.slider("Nombre de colonnes", 1, 4, 2)
    base_font = st.number_input("Taille police", value=18)
    
    st.divider()
    mode = st.radio("Source", ["Manuel", "Excel/CSV"])

# --- PRÉPARATION DES DONNÉES ---
people = []
if mode == "Manuel":
    txt = st.text_area("Nom, Prénom, Titre (un par ligne)")
    if txt:
        for line in txt.split('\n'):
            p = [i.strip() for i in line.split(',')]
            if p[0]: people.append({"N": p[0], "P": p[1] if len(p)>1 else "", "T": p[2] if len(p)>2 else ""})
else:
    f = st.file_uploader("Fichier data", type=["csv", "xlsx"])
    if f:
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        people = df.to_dict('records')

# --- GÉNÉRATION ---
template_file = st.file_uploader("📁 Gabarit PDF", type="pdf")

if template_file and st.button("🚀 Générer la planche"):
    anchor = get_anchor_point(template_file.getvalue(), target)
    
    if not anchor:
        st.error(f"Texte '{target}' introuvable.")
    else:
        # 1. Calcul des dimensions de la planche
        tpl_w = anchor['orig_w']
        tpl_h = anchor['orig_h']
        rows = (nb_total + cols - 1) // cols
        
        page_w = (tpl_w * cols) + (GAP * (cols - 1)) + 40 # +40 marge
        page_h = (tpl_h * rows) + (GAP * (rows - 1)) + 40
        
        # 2. Création du calque de texte (transparent)
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_w, page_h))
        
        # 3. Placement des contenus
        for i in range(nb_total):
            col = i % cols
            row = i // cols
            
            # Coordonnées du coin bas-gauche de ce badge
            dx = 20 + col * (tpl_w + GAP)
            dy = page_h - 20 - (row + 1) * tpl_h - (row * GAP)
            
            p = people[i] if i < len(people) else None
            if p:
                nom = str(p.get('N', p.get('Nom', ''))).upper()
                pre = str(p.get('P', p.get('Prénom', '')))
                titre = str(p.get('T', p.get('Titre', '')))
                full_name = f"{pre} {nom}".strip()
                
                # Dessin du texte relatif au badge
                f_size = get_fitted_font_size(full_name, anchor['width'] * 1.5, base_font)
                can.setFont("Helvetica-Bold", f_size)
                # On ajoute dx/dy au point d'ancrage détecté
                can.drawCentredString(dx + anchor['cx'], dy + anchor['y'], full_name)
                
                if titre and titre.lower() != "nan":
                    can.setFont("Helvetica", f_size * 0.6)
                    can.drawCentredString(dx + anchor['cx'], dy + anchor['y'] - (f_size * 0.7), titre)
        
        can.save()
        packet.seek(0)
        
        # 4. Fusion finale (Gabarits + Texte)
        writer = PdfWriter()
        output_page = writer.add_blank_page(width=page_w, height=page_h)
        
        # On lit le gabarit original
        tpl_reader = PdfReader(io.BytesIO(template_file.getvalue()))
        tpl_page = tpl_reader.pages[0]
        
        # On place les fonds (un par badge)
        for i in range(nb_total):
            col = i % cols
            row = i // cols
            dx = 20 + col * (tpl_w + GAP)
            dy = page_h - 20 - (row + 1) * tpl_h - (row * GAP)
            # On fusionne le gabarit à la position dx, dy
            output_page.merge_transformed_page(tpl_page, [1, 0, 0, 1, dx, dy])
            
        # On fusionne le calque de texte par-dessus tout
        text_layer = PdfReader(packet).pages[0]
        output_page.merge_page(text_layer)
        
        final_out = io.BytesIO()
        writer.write(final_out)
        st.success("Planche générée !")
        st.download_button("📥 Télécharger le PDF de production", final_out.getvalue(), "planche_badges.pdf")
