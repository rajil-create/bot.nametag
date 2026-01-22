import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pypdf import PdfReader, PdfWriter
import io

st.set_page_config(page_title="Nametag Final Pro", layout="wide")

# Paramètre de décalage industriel
GAP = 0.5 * inch 

def load_csv_safely(file):
    """ Règle l'erreur 'utf-8' codec can't decode """
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=encoding)
        except:
            continue
    return None

def get_placeholder_metrics(template_bytes, search_term):
    """ Trouve Scott pour savoir où nettoyer et où écrire """
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        page = pdf.pages[0]
        for w in page.extract_words():
            if search_term.lower() in w['text'].lower():
                return {
                    "cx": (w['x0'] + w['x1']) / 2,
                    "y": page.height - w['bottom'],
                    "rect": (w['x0'] - 2, page.height - w['top'] + 2, w['x1'] - w['x0'] + 4, w['top'] - w['bottom'] + 4),
                    "pw": page.width,
                    "ph": page.height
                }
    return None

st.title("🛡️ Bot de Production (Version Corrigée)")

with st.sidebar:
    st.header("1. Réglages")
    target = st.text_input("Texte à remplacer", "Scott")
    nb_total = st.number_input("Nombre de badges", value=6)
    cols = st.slider("Colonnes", 1, 3, 2)
    font_size = st.number_input("Taille police", value=18)
    st.divider()
    mode = st.radio("Entrée", ["Taper les noms", "Fichier CSV/Excel"])

# --- COLLECTE DES NOMS ---
people = []
if mode == "Taper les noms":
    txt = st.text_area("Prénom, Nom (un par ligne)")
    if txt:
        for line in txt.split('\n'):
            if ',' in line:
                p = line.split(',')
                people.append({"P": p[0].strip(), "N": p[1].strip()})
else:
    f = st.file_uploader("Upload CSV", type=["csv", "xlsx"])
    if f:
        df = load_csv_safely(f) if f.name.endswith('.csv') else pd.read_excel(f)
        if df is not None:
            people = df.to_dict('records')

# --- GÉNÉRATION ---
tpl_file = st.file_uploader("Gabarit PDF", type="pdf")

if tpl_file and st.button("🚀 Lancer la Production"):
    m = get_placeholder_metrics(tpl_file.getvalue(), target)
    
    if not m:
        st.error(f"Le mot '{target}' n'est pas détecté. Impossible de l'effacer.")
    else:
        rows = (nb_total + cols - 1) // cols
        page_w = (m['pw'] * cols) + (GAP * (cols - 1)) + 40
        page_h = (m['ph'] * rows) + (GAP * (rows - 1)) + 40
        
        # Création du calque de correction
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_w, page_h))
        
        writer = PdfWriter()
        out_page = writer.add_blank_page(width=page_w, height=page_h)
        tpl_page = PdfReader(io.BytesIO(tpl_file.getvalue())).pages[0]
        
        for i in range(nb_total):
            c, r = i % cols, i // cols
            dx = 20 + c * (m['pw'] + GAP)
            dy = page_h - 20 - (r + 1) * m['ph'] - (r * GAP)
            
            # 1. On pose le fond original
            out_page.merge_transformed_page(tpl_page, [1, 0, 0, 1, dx, dy])
            
            # 2. On dessine le "patch" blanc pour effacer Scott
            can.setFillColorRGB(1, 1, 1) # Blanc
            can.setStrokeColorRGB(1, 1, 1)
            rx, ry, rw, rh = m['rect']
            can.rect(dx + rx, dy + ry - rh, rw, rh, fill=1)
            
            # 3. On écrit le nouveau nom par-dessus le blanc
            if i < len(people):
                pers = people[i]
                # Gestion des noms de colonnes du CSV
                nom = str(pers.get('Nom', pers.get('nom', ''))).upper()
                pre = str(pers.get('Prénom', pers.get('prenom', '')))
                can.setFillColorRGB(0, 0, 0) # Noir
                can.setFont("Helvetica-Bold", font_size)
                can.drawCentredString(dx + m['cx'], dy + m['y'], f"{pre} {nom}")
        
        can.save()
        packet.seek(0)
        
        # Fusion finale
        correction_layer = PdfReader(packet).pages[0]
        out_page.merge_page(correction_layer)
        
        final_pdf = io.BytesIO()
        writer.write(final_pdf)
        st.success("✅ Planche de production prête !")
        st.download_button("📥 Télécharger le PDF", final_pdf.getvalue(), "badges_ok.pdf")
