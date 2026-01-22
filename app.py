import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, TextStringObject
import io

st.set_page_config(page_title="Production Nametag PRO", layout="wide")
GAP = 0.5 * inch 

def full_clean_pdf(page, target):
    """ Supprime radicalement toute mention du texte cible dans le code du PDF """
    if "/Contents" in page:
        contents = page.get_contents()
        if contents:
            stream = ContentStream(contents, page.pdf)
            for operands, operator in stream.operations:
                if operator in [b"Tj", b"TJ"]:
                    for i, op in enumerate(operands):
                        if isinstance(op, TextStringObject) and target.lower() in op.lower():
                            operands[i] = TextStringObject("")
            page.set_contents(stream)

def load_data(file):
    """ Charge le CSV avec gestion robuste des accents français """
    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            file.seek(0)
            if file.name.endswith('.csv'):
                return pd.read_csv(file, encoding=enc)
            else:
                return pd.read_excel(file)
        except:
            continue
    return None

st.title("🛡️ Système de Production de Badges")

with st.sidebar:
    st.header("Configuration")
    target_to_fix = st.text_input("Texte à EFFACER (ex: Scott)", "Scott")
    nb_total = st.number_input("Nombre de badges", value=6)
    cols = st.slider("Colonnes", 1, 3, 2)
    font_size = st.number_input("Taille Nom", value=20)
    
    st.divider()
    mode = st.radio("Méthode d'entrée :", ["Taper les noms", "Uploader CSV/Excel"])

# --- GESTION DES DONNÉES ---
people = []
if mode == "Taper les noms":
    raw_text = st.text_area("Entrez: Prénom, Nom (un par ligne)", height=200, placeholder="Marc, Tremblay\nSophie, Gagnon")
    if raw_text:
        for line in raw_text.split('\n'):
            if ',' in line:
                p = line.split(',')
                people.append({"Prénom": p[0].strip(), "Nom": p[1].strip()})
else:
    f = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])
    if f:
        df = load_data(f)
        if df is not None:
            df.columns = [c.strip().capitalize() for c in df.columns]
            people = df.to_dict('records')
        else:
            st.error("Impossible de lire le fichier. Vérifiez le format.")

# --- GÉNÉRATION ---
tpl_file = st.file_uploader("Gabarit PDF (avec Scott)", type="pdf")

if tpl_file and st.button("🚀 Générer la Planche"):
    with pdfplumber.open(io.BytesIO(tpl_file.getvalue())) as pdf:
        p0 = pdf.pages[0]
        # Détection position Scott
        found = False
        for w in p0.extract_words():
            if target_to_fix.lower() in w['text'].lower():
                mx = {"cx": (w['x0']+w['x1'])/2, "y": p0.height-w['bottom'], "w": p0.width, "h": p0.height}
                found = True
                break
        
    if not found:
        st.error(f"Le mot '{target_to_fix}' n'a pas été trouvé. Vérifiez l'orthographe.")
    else:
        # Calcul page de sortie
        rows = (nb_total + cols - 1) // cols
        pw = (mx['w'] * cols) + (GAP * (cols - 1)) + 40
        ph = (mx['h'] * rows) + (GAP * (rows - 1)) + 40
        
        reader = PdfReader(io.BytesIO(tpl_file.getvalue()))
        tpl_page = reader.pages[0]
        full_clean_pdf(tpl_page, target_to_fix) # Suppression réelle de "Scott"
        
        writer = PdfWriter()
        out_page = writer.add_blank_page(width=pw, height=ph)
        
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(pw, ph))
        
        for i in range(nb_total):
            c, r = i % cols, i // cols
            dx = 20 + c * (mx['w'] + GAP)
            dy = ph - 20 - (r + 1) * mx['h'] - (r * GAP)
            
            # Fond nettoyé
            out_page.merge_transformed_page(tpl_page, [1, 0, 0, 1, dx, dy])
            
            # Nouveau texte
            if i < len(people):
                pers = people[i]
                nom = str(pers.get('Nom', '')).upper()
                pre = str(pers.get('Prénom', ''))
                can.setFont("Helvetica-Bold", font_size)
                can.drawCentredString(dx + mx['cx'], dy + mx['y'], f"{pre} {nom}")
        
        can.save()
        packet.seek(0)
        out_page.merge_page(PdfReader(packet).pages[0])
        
        final = io.BytesIO()
        writer.write(final)
        st.success("Planche prête !")
        st.download_button("📥 Télécharger PDF de Production", final.getvalue(), "badges_prod.pdf")
