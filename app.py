import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io

st.set_page_config(page_title="Nametag Precision Pro", layout="wide")

# --- INTERFACE ---
st.title("🎯 Nametag Precision Pro")
st.sidebar.header("Configuration")
target_text = st.sidebar.text_input("Texte exact à remplacer", "NOM")
nb_voulu = st.sidebar.number_input("Nombre de nametags total", min_value=1, value=4)
cols_grid = st.sidebar.slider("Nombre de colonnes sur la page", 1, 3, 2)

mode = st.sidebar.radio("Source", ["Saisie Manuelle", "Fichier Excel/CSV"])

# --- MOTEUR DE DÉTECTION ET POSITIONNEMENT ---
def get_text_anchor(template_bytes, search_term):
    """ Trouve le centre exact de l'ancien texte dans le PDF """
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        for w in words:
            if search_term.lower() in w['text'].lower():
                # On calcule le centre X et la base Y
                center_x = (w['x0'] + w['x1']) / 2
                base_y = page.height - w['bottom'] # Inversion pour ReportLab
                return center_x, base_y, (w['x1'] - w['x0'])
    return None

def draw_badge_content(can, x_anchor, y_anchor, max_w, nom, prenom, titre):
    """ Écrit le texte exactement sur l'ancre """
    full_name = f"{prenom} {nom}".strip()
    # Calcul de la taille de police auto-fit
    base_size = 18
    estimated_w = len(full_name) * base_size * 0.55
    font_size = base_size
    while estimated_w > (max_w + 20) and font_size > 6:
        font_size -= 0.5
        estimated_w = len(full_name) * font_size * 0.55

    # Écriture du Nom (Centré sur l'ancre)
    can.setFillColorRGB(0, 0, 0)
    can.setFont("Helvetica-Bold", font_size)
    can.drawCentredString(x_anchor, y_anchor + 5, full_name)
    
    # Écriture du Titre si présent
    if titre:
        can.setFont("Helvetica", font_size * 0.7)
        can.drawCentredString(x_anchor, y_anchor - 12, str(titre))

# --- GESTION DES DONNÉES ---
people = []
if mode == "Saisie Manuelle":
    txt = st.text_area("Format: Nom, Prénom, Titre")
    if txt:
        for line in txt.split('\n'):
            p = [i.strip() for i in line.split(',')]
            if p[0]: people.append({"N": p[0], "P": p[1] if len(p)>1 else "", "T": p[2] if len(p)>2 else ""})
else:
    f = st.file_uploader("Upload Data", type=["csv", "xlsx"])
    if f:
        df = pd.read_csv(f, encoding='latin-1') if f.name.endswith('.csv') else pd.read_excel(f)
        people = df.to_dict('records')

# --- GÉNÉRATION ---
template_pdf = st.file_uploader("Upload Gabarit PDF", type="pdf")

if template_pdf and st.button("🚀 Générer la planche de badges"):
    # 1. Analyse du gabarit
    anchor = get_text_anchor(template_pdf.getvalue(), target_text)
    if not anchor:
        st.error(f"Le texte '{target_text}' n'a pas été trouvé dans le PDF.")
    else:
        ax, ay, aw = anchor
        reader = PdfReader(io.BytesIO(template_pdf.getvalue()))
        tpl_page = reader.pages[0]
        w_page = float(tpl_page.mediabox.width)
        h_page = float(tpl_page.mediabox.height)
        
        # 2. Création de la page finale
        output_writer = PdfWriter()
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(w_page * cols_grid, h_page * ((nb_voulu // cols_grid) + 1)))
        
        # 3. Placement en grille
        for i in range(nb_voulu):
            col = i % cols_grid
            row = i // cols_grid
            
            # Décalage de la grille
            dx = col * w_page
            dy = row * h_page # On peut ajuster pour que ça monte ou descende
            
            # Dessiner le contenu du badge
            p = people[i] if i < len(people) else {"N": "", "P": "", "T": ""}
            # On simule le gabarit (Image ou Rect) - Ici on fusionnera après
            # Pour la précision, on écrit directement aux coordonnées relatives
            
            # Cache blanc sur l'ancien texte
            can.setFillColorRGB(1, 1, 1)
            can.rect(dx + ax - (aw/2) - 5, dy + ay - 5, aw + 10, 25, fill=1, stroke=0)
            
            # Nouveau texte
            draw_badge_content(can, dx + ax, dy + ay, aw, p.get('N',''), p.get('P',''), p.get('T',''))

        can.save()
        packet.seek(0)
        
        # 4. Fusion avec les fonds (Gabarits)
        overlay_reader = PdfReader(packet)
        new_page = output_writer.add_blank_page(width=w_page * cols_grid, height=h_page * ((nb_voulu // cols_grid) + 1))
        
        # On ajoute le fond pour chaque position
        for i in range(nb_voulu):
            col = i % cols_grid
            row = i // cols_grid
            new_page.merge_transformed_page(tpl_page, [1, 0, 0, 1, col * w_page, row * h_page])
            
        # On ajoute tout le texte d'un coup
        new_page.merge_page(overlay_reader.pages[0])
        
        final_out = io.BytesIO()
        output_writer.write(final_out)
        
        st.success("Planche générée !")
        st.download_button("📥 Télécharger le PDF Unique", final_out.getvalue(), "planche_badges.pdf")
