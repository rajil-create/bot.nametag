import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, TextStringObject
import io

st.set_page_config(page_title="Production Nametag Pro", layout="wide")

# Paramètre de décalage demandé : 0.5 inch
GAP = 0.5 * inch 

def clean_pdf_text(page, text_to_hide):
    """ Supprime techniquement le texte du flux binaire du PDF """
    if "/Contents" in page:
        contents = page.get_contents()
        if contents:
            content_stream = ContentStream(contents, page.pdf)
            for operands, operator in content_stream.operations:
                if operator in [b"Tj", b"TJ"]:
                    for i, op in enumerate(operands):
                        if isinstance(op, TextStringObject) and text_to_hide.lower() in op.lower():
                            operands[i] = TextStringObject("") 
            page.set_contents(content_stream)

def get_metrics(template_bytes, search_term):
    """ Détecte l'emplacement exact pour l'alignement """
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        for w in words:
            if search_term.lower() in w['text'].lower():
                return {
                    "cx": (w['x0'] + w['x1']) / 2,
                    "y": page.height - w['bottom'],
                    "w_orig": page.width,
                    "h_orig": page.height
                }
    return None

st.title("🛡️ Bot de Gravure Professionnel")

# --- INTERFACE DE SAISIE ---
with st.sidebar:
    st.header("1. Paramètres d'Impression")
    target_text = st.text_input("Texte à faire disparaître (ex: Scott)", "Scott")
    nb_badges = st.number_input("Nombre de badges sur la planche", min_value=1, value=4)
    cols = st.slider("Nombre de colonnes", 1, 3, 2)
    f_size = st.number_input("Taille de la police", value=18)
    
    st.divider()
    st.header("2. Source des Noms")
    mode = st.radio("Choisir la méthode :", ["Saisie Manuelle (Taper)", "Upload Fichier (Excel/CSV)"])

# --- PRÉPARATION DES DONNÉES ---
data_list = []
if mode == "Saisie Manuelle (Taper)":
    raw_input = st.text_area("Tapez ici : Prénom, Nom (un par ligne)", placeholder="Jean, Dupont\nMarie, Durand")
    if raw_input:
        for line in raw_input.split('\n'):
            if ',' in line:
                parts = line.split(',')
                data_list.append({"Prénom": parts[0].strip(), "Nom": parts[1].strip()})
else:
    file = st.file_uploader("Uploader votre Excel ou CSV", type=["xlsx", "csv"])
    if file:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file, engine='openpyxl')
        data_list = df.to_dict('records')

# --- MOTEUR DE GÉNÉRATION ---
template_pdf = st.file_uploader("Uploader le Gabarit PDF (celui avec Scott)", type="pdf")

if template_pdf and st.button("🚀 Générer la planche de badges"):
    m = get_metrics(template_pdf.getvalue(), target_text)
    
    if not m:
        st.error(f"Erreur : Le mot '{target_text}' n'est pas détecté dans le PDF.")
    else:
        # Calcul de la planche
        rows = (nb_badges + cols - 1) // cols
        p_width = (m['w_orig'] * cols) + (GAP * (cols - 1)) + 50
        p_height = (m['h_orig'] * rows) + (GAP * (rows - 1)) + 50
        
        # Préparation PDF
        reader = PdfReader(io.BytesIO(template_pdf.getvalue()))
        tpl_page = reader.pages[0]
        clean_pdf_text(tpl_page, target_text) # Nettoyage de "Scott"
        
        writer = PdfWriter()
        output_page = writer.add_blank_page(width=p_width, height=p_height)
        
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(p_width, p_height))
        
        for i in range(nb_badges):
            c = i % cols
            r = i // cols
            
            x_off = 25 + c * (m['w_orig'] + GAP)
            y_off = p_height - 25 - (r + 1) * m['h_orig'] - (r * GAP)
            
            # 1. Fusion du fond nettoyé
            output_page.merge_transformed_page(tpl_page, [1, 0, 0, 1, x_off, y_off])
            
            # 2. Ajout du nouveau texte au même endroit
            if i < len(data_list):
                p = data_list[i]
                # Gestion flexible des noms de colonnes
                nom = str(p.get('Nom', p.get('nom', ''))).upper()
                pre = str(p.get('Prénom', p.get('prenom', '')))
                txt = f"{pre} {nom}".strip()
                
                can.setFont("Helvetica-Bold", f_size)
                can.drawCentredString(x_off + m['cx'], y_off + m['y'], txt)
        
        can.save()
        packet.seek(0)
        output_page.merge_page(PdfReader(packet).pages[0])
        
        final_pdf = io.BytesIO()
        writer.write(final_pdf)
        
        st.success("Planche générée avec succès !")
        st.download_button("📥 Télécharger le PDF prêt à imprimer", final_pdf.getvalue(), "planche_badges_final.pdf")
