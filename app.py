import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Générateur Badges Pro", layout="wide")
st.title("🛡️ Générateur de Badges (PDF Unique)")

# --- BARRE LATÉRALE (RÉGLAGES) ---
st.sidebar.header("1. Source des données")
mode = st.sidebar.radio("Choisir :", ["Fichier Excel/CSV", "Saisie Manuelle"])

st.sidebar.header("2. Positionnement (Cache)")
st.sidebar.info("Ajustez le carré blanc pour cacher 'Richard Oliva'")
c_x = st.sidebar.slider("X (Horizontal)", 0, 500, 135)
c_y = st.sidebar.slider("Y (Vertical)", 0, 300, 40)
c_w = st.sidebar.slider("Largeur", 10, 300, 250)
c_h = st.sidebar.slider("Hauteur", 10, 100, 60)

# --- ZONE DE CHARGEMENT DU MODÈLE ---
col_main, col_preview = st.columns([2, 1])
with col_main:
    pdf_template = st.file_uploader("📂 Chargez le Modèle PDF (celui avec Richard Oliva)", type="pdf")

# --- FONCTION DE GÉNÉRATION D'UNE PAGE ---
def create_page(template_bytes, nom, prenom, titre):
    # 1. Lire le template
    reader = PdfReader(io.BytesIO(template_bytes))
    page = reader.pages[0]
    
    # 2. Créer le calque (Overlay) avec ReportLab
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page.mediabox.width, page.mediabox.height))
    
    # DESSIN DU CACHE BLANC
    can.setFillColorRGB(1, 1, 1) 
    can.rect(c_x, c_y, c_w, c_h, fill=1, stroke=0)
    
    # NETTOYAGE DES DONNÉES (Eviter les "nan" ou vides)
    t_nom = str(nom).strip() if pd.notna(nom) and str(nom).lower() != 'nan' else ""
    t_pre = str(prenom).strip() if pd.notna(prenom) and str(prenom).lower() != 'nan' else ""
    t_titre = str(titre).strip() if pd.notna(titre) and str(titre).lower() != 'nan' else ""

    # LOGIQUE INTELLIGENTE DE POSITIONNEMENT
    can.setFillColorRGB(0, 0, 0) # Texte Noir
    
    if t_nom and t_titre:
        # Cas complet : Nom + Titre
        can.setFont("Helvetica-Bold", 18)
        can.drawString(c_x + 5, c_y + 35, f"{t_pre} {t_nom}")
        can.setFont("Helvetica", 12)
        can.drawString(c_x + 5, c_y + 15, t_titre)
    else:
        # Cas Nom seul (centré verticalement pour faire joli)
        can.setFont("Helvetica-Bold", 20)
        can.drawString(c_x + 5, c_y + 25, f"{t_pre} {t_nom}".strip())

    can.save()
    packet.seek(0)
    
    # 3. Fusionner le calque avec la page originale
    overlay_pdf = PdfReader(packet)
    page.merge_page(overlay_pdf.pages[0])
    return page

# --- TRAITEMENT DES DONNÉES ---
df = pd.DataFrame()
data_ready = False

if mode == "Saisie Manuelle":
    txt = st.text_area("Entrez les noms (Format: Nom, Prénom, Titre)", 
                       placeholder="Exemple:\nDUPONT, Jean, Directeur\nMARTIN, Sophie\nDURAND", height=150)
    if txt:
        lines = [line.split(',') for line in txt.split('\n') if line.strip()]
        df = pd.DataFrame(lines)
        # Gestion flexible des colonnes manquantes
        cols = ['Nom', 'Prénom', 'Titre']
        for i, col in enumerate(cols):
            if i < len(df.columns):
                df = df.rename(columns={i: col})
            else:
                df[col] = "" # Colonne vide si absente
        data_ready = True

else:
    csv_file = st.file_uploader("📂 Chargez la liste Excel/CSV", type=["csv", "xlsx"])
    if csv_file:
        try:
            # Lecture robuste (CSV ou Excel)
            if csv_file.name.endswith('.csv'):
                df = pd.read_csv(csv_file, encoding='latin-1', sep=None, engine='python')
            else:
                df = pd.read_excel(csv_file)
            
            # Nettoyage des colonnes
            df.columns = [str(c).strip().title() for c in df.columns]
            
            # Recherche flexible des colonnes
            mapping = {}
            for col in df.columns:
                if "nom" in col.lower() and "pré" not in col.lower(): mapping['Nom'] = col
                if "pré" in col.lower() or "pre" in col.lower(): mapping['Prénom'] = col
                if "titre" in col.lower() or "poste" in col.lower(): mapping['Titre'] = col
            
            # Création du dataframe standardisé
            final_df = pd.DataFrame()
            final_df['Nom'] = df[mapping['Nom']] if 'Nom' in mapping else ""
            final_df['Prénom'] = df[mapping['Prénom']] if 'Prénom' in mapping else ""
            final_df['Titre'] = df[mapping['Titre']] if 'Titre' in mapping else ""
            
            # On remplit le 'Nom' avec la première colonne si rien trouvé (secours)
            if final_df['Nom'].isnull().all() and len(df.columns) > 0:
                final_df['Nom'] = df.iloc[:, 0]
                
            df = final_df
            data_ready = True
        except Exception as e:
            st.error(f"Erreur de lecture du fichier : {e}")

# --- AFFICHAGE ET GÉNÉRATION ---
if data_ready and pdf_template:
    st.write("---")
    st.subheader("📋 Vérification avant génération")
    
    # Filtre optionnel
    search = st.text_input("Filtrer (ex: Tapez 'A' pour les noms commençant par A)", "")
    if search:
        df = df[df['Nom'].str.contains(search, case=False, na=False) | df['Prénom'].str.contains(search, case=False, na=False)]
    
    st.info(f"{len(df)} badges prêts à être générés.")
    st.dataframe(df.head())

    # --- LE BOUTON MAGIQUE ---
    # On prépare le PDF en mémoire
    if st.checkbox("Je confirme les réglages, préparer le fichier final"):
        with st.spinner("Création du PDF unique en cours..."):
            output_pdf = PdfWriter()
            
            # On boucle sur chaque personne pour ajouter une page
            for i, row in df.iterrows():
                try:
                    page = create_page(pdf_template.getvalue(), row.get('Nom', ''), row.get('Prénom', ''), row.get('Titre', ''))
                    output_pdf.add_page(page)
                except Exception as e:
                    st.warning(f"Problème avec la ligne {i}: {e}")

            # Sauvegarde en mémoire
            final_buffer = io.BytesIO()
            output_pdf.write(final_buffer)
            final_buffer.seek(0)
            
            st.success("✅ Fichier PDF fusionné prêt !")
            
            # BOUTON TÉLÉCHARGEMENT DIRECT
            st.download_button(
                label="📥 TÉLÉCHARGER LE PDF UNIQUE (Tous les badges)",
                data=final_buffer,
                file_name="Tous_Les_Badges_Prets.pdf",
                mime="application/pdf"
            )
