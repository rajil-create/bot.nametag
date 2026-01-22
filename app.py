import streamlit as st
import pandas as pd
import pdfplumber
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io

st.set_page_config(page_title="Bot Remplacement Auto", layout="wide")
st.title("🤖 Remplacement de Nom Automatique")
st.info("Ce bot scanne le PDF pour trouver l'ancien nom et le remplacer exactement au même endroit.")

# --- SIDEBAR : DONNÉES ---
st.sidebar.header("1. Données")
mode = st.sidebar.radio("Mode de saisie :", ["Liste Excel/CSV", "Saisie Manuelle"])
ancien_nom_a_chercher = st.sidebar.text_input("Texte à remplacer (ex: Scott)", "Scott")

# --- CHARGEMENT PDF ---
pdf_template = st.file_uploader("2. Glissez votre modèle (avec l'ancien nom)", type="pdf")

def create_auto_badge(template_bytes, text_to_find, new_nom, new_prenom, new_titre):
    # 1. On utilise pdfplumber pour TROUVER les coordonnées du texte
    found_box = None
    
    with pdfplumber.open(io.BytesIO(template_bytes)) as pdf:
        first_page = pdf.pages[0]
        height = first_page.height
        
        # Recherche du mot exact
        words = first_page.extract_words()
        for word in words:
            if text_to_find.lower() in word['text'].lower():
                # On a trouvé le mot !
                # pdfplumber donne: x0 (gauche), top (haut), x1 (droite), bottom (bas)
                # Mais attention, l'origine Y est en HAUT pour plumber, et en BAS pour le PDF final
                
                # Conversion des coordonnées
                x = word['x0'] - 10 # On élargit un peu la zone à effacer
                y_reportlab = height - word['bottom'] - 5 # Inversion du Y + Marge
                w = (word['x1'] - word['x0']) + 40 # Largeur + marge
                h = (word['bottom'] - word['top']) + 20 # Hauteur + marge
                
                found_box = (x, y_reportlab, w, h)
                break # On s'arrête au premier trouvé
    
    # 2. On prépare la "Rustine" (Patch)
    reader = PdfReader(io.BytesIO(template_bytes))
    page_source = reader.pages[0]
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_source.mediabox.width, page_source.mediabox.height))
    
    if found_box:
        (x, y, w, h) = found_box
        # Carré blanc pour effacer l'ancien
        can.setFillColorRGB(1, 1, 1)
        can.rect(x, y, w, h, fill=1, stroke=0)
        
        # Nouveau Texte (Centré dans la zone trouvée)
        full_text = f"{new_prenom} {new_nom}".strip()
        if new_titre:
             # Si titre, on écrit plus petit sur deux lignes
            can.setFillColorRGB(0, 0, 0)
            can.setFont("Helvetica-Bold", 14)
            can.drawCentredString(x + w/2, y + h/2 + 5, full_text)
            can.setFont("Helvetica", 10)
            can.drawCentredString(x + w/2, y + h/2 - 10, str(new_titre))
        else:
            # Juste le nom, bien gros au milieu
            can.setFillColorRGB(0, 0, 0)
            can.setFont("Helvetica-Bold", 18)
            can.drawCentredString(x + w/2, y + h/2 - 5, full_text)
            
    else:
        # SI ON NE TROUVE PAS LE MOT (Sécurité)
        # On écrit quand même en bas au milieu par défaut
        can.setFont("Helvetica-Bold", 20)
        can.drawCentredString(float(page_source.mediabox.width)/2, 50, f"{new_prenom} {new_nom} (Auto-placé)")

    can.save()
    packet.seek(0)
    
    # 3. Fusion
    overlay = PdfReader(packet)
    page_source.merge_page(overlay.pages[0])
    
    out = PdfWriter()
    out.add_page(page_source)
    final_buffer = io.BytesIO()
    out.write(final_buffer)
    return final_buffer.getvalue()

# --- LOGIQUE PRINCIPALE ---
df = pd.DataFrame()
ready = False

if mode == "Saisie Manuelle":
    txt = st.text_area("Collez votre liste ici :", "OLIVA, Richard, Directeur\nRAJI, Larbi")
    if txt:
        df = pd.DataFrame([row.split(',') for row in txt.split('\n') if row.strip()])
        # Gestion colonnes dynamique
        cols = ['Nom', 'Prénom', 'Titre']
        for i, c in enumerate(cols):
            if i < len(df.columns): df = df.rename(columns={i: c})
            else: df[c] = ""
        ready = True
else:
    f = st.file_uploader("Fichier CSV/Excel", type=["csv", "xlsx"])
    if f:
        # Chargement simplifié
        if f.name.endswith('.csv'): df = pd.read_csv(f, encoding='latin-1', header=None, sep=None, engine='python')
        else: df = pd.read_excel(f, header=None)
        
        # On renomme arbitrairement 0->Nom, 1->Prenom, 2->Titre
        mapping = {0:'Nom', 1:'Prénom', 2:'Titre'}
        df = df.rename(columns=mapping)
        for c in ['Nom','Prénom','Titre']: 
            if c not in df.columns: df[c] = ""
        ready = True

# --- EXÉCUTION ---
if ready and pdf_template:
    st.success(f"Liste chargée : {len(df)} badges à faire.")
    if st.button("🚀 LANCER LA DÉTECTION ET GÉNÉRATION"):
        
        zip_buffer = io.BytesIO()
        # On utilise ZipFile cette fois car un PDF unique avec des formats différents mélangés est risqué
        # Mais si tous les PDFs font la même taille, on pourrait fusionner.
        # Restons sur le ZIP pour la sécurité si "plein de gabarits".
        import zipfile
        with zipfile.ZipFile(zip_buffer, "w") as z:
            
            progression = st.progress(0)
            for i, row in df.iterrows():
                try:
                    pdf_bytes = create_auto_badge(
                        pdf_template.getvalue(), 
                        ancien_nom_a_chercher, # Le bot cherche "Scott"
                        row['Nom'], row['Prénom'], row['Titre']
                    )
                    nom_fichier = f"Badge_{row['Nom']}.pdf"
                    z.writestr(nom_fichier, pdf_bytes)
                except Exception as e:
                    st.error(f"Erreur sur {row['Nom']}: {e}")
                progression.progress((i + 1) / len(df))
                
        st.download_button("📥 TÉLÉCHARGER LES BADGES (ZIP)", zip_buffer.getvalue(), "badges_auto.zip")
