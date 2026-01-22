import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, TextStringObject, NameObject
import io

st.set_page_config(page_title="Nametag Master Engine", layout="wide")

GAP = 0.5 * inch # Décalage 0.5 inch

def remove_text_from_pdf(page, text_to_remove):
    """ Supprime le texte spécifique du flux binaire du PDF sans laisser de trace """
    content = page.get_contents()
    if not content:
        return
    
    content_stream = ContentStream(content, page.pdf)
    for operands, operator in content_stream.operations:
        if operator == b"Tj" or operator == b"TJ":
            # On vérifie si le texte cible est dans l'opérande
            for i, op in enumerate(operands):
                if isinstance(op, TextStringObject) and text_to_remove.lower() in op.lower():
                    operands[i] = TextStringObject("") # On vide le texte
    page.set_contents(content_stream)

def get_text_metrics(template_bytes, search_term):
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        for w in words:
            if search_term.lower() in w['text'].lower():
                return {
                    "cx": (w['x0'] + w['x1']) / 2,
                    "y": page.height - w['bottom'],
                    "w": w['x1'] - w['x0'],
                    "page_w": page.width,
                    "page_h": page.height
                }
    return None

st.title("🛡️ Nametag Master Engine (Zéro Cache)")

with st.sidebar:
    st.header("Paramètres")
    target = st.text_input("Texte à supprimer (ex: Scott)", "Scott")
    nb_total = st.number_input("Nombre de badges", min_value=1, value=6)
    cols = st.slider("Colonnes", 1, 4, 2)
    font_size = st.number_input("Taille police", value=18)
    st.divider()
    upload_data = st.file_uploader("Data (CSV/Excel)", type=["csv", "xlsx"])

# --- DATA ---
people = []
if upload_data:
    df = pd.read_csv(upload_data) if upload_data.name.endswith('.csv') else pd.read_excel(upload_data)
    df.columns = [c.strip().capitalize() for c in df.columns]
    people = df.to_dict('records')

# --- GENERATION ---
template_file = st.file_uploader("📁 Gabarit PDF avec Scott", type="pdf")

if template_file and st.button("🚀 Générer la Planche"):
    metrics = get_text_metrics(template_file.getvalue(), target)
    
    if not metrics:
        st.error(f"Impossible de localiser '{target}' pour le remplacement.")
    else:
        tpl_w, tpl_h = metrics['page_w'], metrics['page_h']
        rows = (nb_total + cols - 1) // cols
        
        # Dimensions de la planche
        page_w = (tpl_w * cols) + (GAP * (cols - 1)) + 60
        page_h = (tpl_h * rows) + (GAP * (rows - 1)) + 60
        
        # 1. Nettoyage du gabarit original (on enlève Scott du code PDF)
        tpl_reader = PdfReader(io.BytesIO(template_file.getvalue()))
        tpl_page = tpl_reader.pages[0]
        remove_text_from_pdf(tpl_page, target)
        
        # 2. Création de la planche
        writer = PdfWriter()
        output_page = writer.add_blank_page(width=page_w, height=page_h)
        
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_w, page_h))
        
        for i in range(nb_total):
            col = i % cols
            row = i // cols
            
            x_offset = 30 + col * (tpl_w + GAP)
            y_offset = page_h - 30 - (row + 1) * tpl_h - (row * GAP)
            
            # On fusionne le gabarit NETTOYÉ
            output_page.merge_transformed_page(tpl_page, [1, 0, 0, 1, x_offset, y_offset])
            
            # Ajout du nouveau texte
            p = people[i] if i < len(people) else {"Nom": "", "Prénom": ""}
            full_name = f"{p.get('Prénom', '')} {p.get('Nom', '')}".strip().upper()
            
            if full_name:
                can.setFont("Helvetica-Bold", font_size)
                can.drawCentredString(x_offset + metrics['cx'], y_offset + metrics['y'], full_name)

        can.save()
        packet.seek(0)
        
        # Superposition finale
        text_layer = PdfReader(packet).pages[0]
        output_page.merge_page(text_layer)
        
        final_out = io.BytesIO()
        writer.write(final_out)
        st.success("✅ Planche Pro Générée (Texte remplacé sans cache blanc) !")
        st.download_button("📥 Télécharger le PDF de Production", final_out.getvalue(), "planche_pro.pdf")
