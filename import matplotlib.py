import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Simulateur Entrepôt Pro", layout="wide")

st.title("🏭 Plan de Masse Opérationnel")
st.markdown("Outil de dimensionnement dynamique pour le séchage rotatif (3 jours) et le stockage.")

# ==========================================
# 1. BARRE LATÉRALE (CONTRÔLES)
# ==========================================

with st.sidebar:
    st.header("1. Dimensions & Agencement")
    bat_longueur = st.slider("Longueur Bâtiment (m)", 40, 150, 60, step=1)
    bat_largeur = st.slider("Largeur Bâtiment (m)", 30, 100, 50, step=1)
    largeur_allee = st.slider("Largeur Allée (m)", 4.0, 12.0, 8.0, step=0.5)
    
    st.markdown("---")
    st.subheader("📐 Géométrie des Zones")
    largeur_dispo = bat_largeur - largeur_allee
    
    largeur_stock_droite = st.slider(
        "Largeur allouée au Stockage (Droite)", 
        min_value=2.0, 
        max_value=float(largeur_dispo - 5), 
        value=float(10.0), 
        step=0.5
    )
    largeur_sechage_gauche = largeur_dispo - largeur_stock_droite
    st.caption(f"Séchage (G) : {largeur_sechage_gauche:.1f}m | Stockage (D) : {largeur_stock_droite:.1f}m")
    st.markdown("---")

    st.header("2. Scénario & Flux")
    scenario = st.radio("Volume mensuel (Tonnes)", [3000, 6000], index=0, horizontal=True)
    jours_ouvres = st.number_input("Jours ouvrés/mois", 15, 30, 20)
    tonnage_jour = scenario / jours_ouvres
    st.info(f"Flux journalier : **{tonnage_jour:.0f} t/jour**")

    st.header("3. Paramètres Process")
    h_sechage = st.number_input("Hauteur Séchage (m)", 0.1, 2.0, 0.4, step=0.1)
    h_stock_sec = st.number_input("Hauteur Stock Sec (m)", 2.0, 12.0, 7.0, step=0.5)
    duree_sechage = 3  # Fixe

    # --- RECETTE ---
    st.header("4. Recette & Densités")
    
    st.subheader("🟢 Rebut Pam")
    pct_rebut_pam = st.slider("% Rebut Pam", 0, 100, 18, key="pct_rebut_pam")
    den_rebut_pam = st.number_input("Densité Rebut Pam", 0.1, 5.0, 1.5, step=0.1, key="den_rebut_pam")

    st.subheader("🔵 Jet et coulée Blénod")
    pct_jet_blenod = st.slider("% Jet et coulée Blénod", 0, 100, 37, key="pct_jet_blenod")
    den_jet_blenod = st.number_input("Densité Jet et coulée Blénod", 0.1, 5.0, 1.0, step=0.1, key="den_jet_blenod")

    st.subheader("⚪️ Gueuset")
    pct_gueuset = st.slider("% Gueuset", 0, 100, 0, key="pct_gueuset")
    den_gueuset = st.number_input("Densité Gueuset", 0.1, 5.0, 1.0, step=0.1, key="den_gueuset")

    st.subheader("🟠 Fontes Foug")
    pct_fontes_foug = st.slider("% Fontes Foug", 0, 100, 15, key="pct_fontes_foug")
    den_fontes_foug = st.number_input("Densité Fontes Foug", 0.1, 5.0, 1.0, step=0.1, key="den_fontes_foug")

    st.subheader("🟣 Ferraille")
    pct_ferraille = st.slider("% Ferraille", 0, 100, 30, key="pct_ferraille")
    den_ferraille = st.number_input("Densité Ferraille", 0.1, 5.0, 1.25, step=0.1, key="den_ferraille")

    total_pct = pct_rebut_pam + pct_jet_blenod + pct_gueuset + pct_fontes_foug + pct_ferraille
    if total_pct != 100:
        st.error(f"⚠️ Total Recette = {total_pct}%")

# ==========================================
# 2. CALCULS MOTEUR
# ==========================================

MATIERES = {
    "Rebut Pam": {"ratio": pct_rebut_pam/100, "densite": den_rebut_pam, "couleur": "#ff9933"},
    "Jet Blénod": {"ratio": pct_jet_blenod/100, "densite": den_jet_blenod, "couleur": "#33ccff"},
    "Gueuset": {"ratio": pct_gueuset/100, "densite": den_gueuset, "couleur": "#aaaaaa"},
    "Fontes Foug": {"ratio": pct_fontes_foug/100, "densite": den_fontes_foug, "couleur": "#ffcc66"},
    "Ferraille": {"ratio": pct_ferraille/100, "densite": den_ferraille, "couleur": "#da1884"},
}

surface_totale = bat_longueur * bat_largeur
surface_allee = bat_longueur * largeur_allee

resultats = {}
surface_sechage_totale = 0
surface_stock_totale = 0

for nom, props in MATIERES.items():
    flux_mat_jour = tonnage_jour * props["ratio"]
    
    # SÉCHAGE
    vol_sechage = (flux_mat_jour * duree_sechage) / props["densite"]
    surf_sechage = vol_sechage / h_sechage
    
    # STOCK SEC
    jours_stock = 15 if scenario == 3000 else 10
    vol_stock = (flux_mat_jour * jours_stock) / props["densite"]
    surf_stock = vol_stock / h_stock_sec
    
    resultats[nom] = {
        "sechage": surf_sechage,
        "stock": surf_stock,
        "longueur_sechage": surf_sechage / largeur_sechage_gauche,
        "longueur_stock": surf_stock / largeur_stock_droite,
        "props": props
    }
    surface_sechage_totale += surf_sechage
    surface_stock_totale += surf_stock

# ==========================================
# 3. GÉNÉRATION DU PLAN
# ==========================================

fig, ax = plt.subplots(figsize=(11.69, 16.53)) # A3 Portrait

# Fond Blanc
ax.add_patch(patches.Rectangle((0, 0), bat_largeur, bat_longueur, edgecolor='black', facecolor='white', lw=2))

# Allée Centrale
x_allee = largeur_sechage_gauche
ax.add_patch(patches.Rectangle((x_allee, 0), largeur_allee, bat_longueur, color='#e0e0e0', alpha=0.5, hatch='//'))
ax.text(x_allee + largeur_allee/2, bat_longueur/2, f"ALLÉE DE CIRCULATION\n{largeur_allee}m", 
        ha='center', va='center', color='#666', rotation=90, fontweight='bold', fontsize=10)

# --- CÔTÉ GAUCHE : SÉCHAGE ---
curseur_y = 0
depassement = False

for nom, res in resultats.items():
    if res["props"]["ratio"] == 0: continue
    
    l_totale = res["longueur_sechage"]
    l_jour = l_totale / 3
    coul = res["props"]["couleur"]
    
    # Centre du bloc matière
    y_center_block = curseur_y + l_totale / 2
    
    # Flèche de rotation (Décalée pour ne pas gêner)
    if l_totale > 2:
        ax.annotate(
            'Rotation 3j', 
            xy=(0, curseur_y + l_totale), 
            xytext=(-1.5, curseur_y), # Légèrement décalé
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=-0.1", color='#444', lw=1.5),
            fontsize=8, ha='center', va='center', rotation=90, color='#444'
        )

    for i in range(3): # 0=Lot 1, 1=Lot 2, 2=Lot 3
        y_pos = curseur_y + (i * l_jour)
        
        if y_pos + l_jour > bat_longueur:
            fill_col = '#ffcccc'
            edge_col = 'red'
            depassement = True
        else:
            fill_col = coul
            edge_col = 'black'
            
        ax.add_patch(patches.Rectangle((0, y_pos), largeur_sechage_gauche, l_jour, 
                                       facecolor=fill_col, edgecolor=edge_col, alpha=0.5, linewidth=1))
        
        # Etiquetage Lot (Discret)
        label_lot = f"Lot {i+1}"
        if l_jour > 0.5:
             ax.text(0.5, y_pos + l_jour/2, label_lot, 
                        ha='left', va='center', fontsize=7, color='#333', fontweight='normal')

    # ETIQUETTE PRINCIPALE SÉCHAGE (Sur fond blanc pour lisibilité)
    if l_totale > 1:
        label_text = f"{nom}\nSurface: {int(res['sechage'])} m²\n(H={h_sechage}m)"
        ax.text(largeur_sechage_gauche/2, y_center_block, label_text, 
                ha='center', va='center', fontsize=9, fontweight='bold', color='black',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))

    curseur_y += l_totale

# Limite Batiment
ax.axhline(y=bat_longueur, color='red', linestyle='--', linewidth=1.5)
if depassement:
    ax.text(largeur_sechage_gauche/2, bat_longueur + 2, "⚠️ DÉPASSEMENT LIMITES", ha='center', color='red', fontweight='bold')

# --- CÔTÉ DROIT : STOCK SEC ---
curseur_y_droit = 0

for nom, res in resultats.items():
    if res["props"]["ratio"] == 0: continue

    l_stock = res["longueur_stock"]
    y_pos = curseur_y_droit
    coul = res["props"]["couleur"]
    
    x_stock = x_allee + largeur_allee
    ax.add_patch(patches.Rectangle((x_stock, y_pos), largeur_stock_droite, l_stock,
                                   facecolor=coul, edgecolor='black', alpha=0.3, hatch='..', linewidth=1))
    
    # ETIQUETTE PRINCIPALE STOCKAGE (AMÉLIORÉE avec fond blanc)
    if l_stock > 1:
        label_text = f"STOCK {nom}\n{int(res['stock'])} m²\n(H={h_stock_sec}m)"
        ax.text(x_stock + largeur_stock_droite/2, y_pos + l_stock/2, label_text, 
                ha='center', va='center', fontsize=9, color='black', fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))
    
    curseur_y_droit += l_stock

# Cotes globales (Décalées pour éviter chevauchement)
ax.text(bat_largeur / 2, -3, f"LARGEUR TOTALE : {bat_largeur} m", ha='center', fontweight='bold')
# Déplacement de la cote Longueur à gauche (-5 au lieu de -3)
ax.text(-5, bat_longueur / 2, f"LONGUEUR TOTALE : {bat_longueur} m", va='center', rotation=90, fontweight='bold')

# Configuration Axes
ax.set_xlim(-6, bat_largeur + 5) # Augmenté pour voir la cote à gauche
ax.set_ylim(-5, bat_longueur + 5)
ax.set_aspect('equal')
ax.axis('off')
ax.set_title(f"PLAN D'IMPLANTATION - {scenario} T/MOIS", fontsize=16, fontweight='bold', pad=20)

# ==========================================
# 4. TABLEAU DE BORD & EXPORT
# ==========================================

col_graph, col_stats = st.columns([2, 1])

with col_graph:
    st.pyplot(fig)

with col_stats:
    st.subheader("📥 Téléchargements")
    
    pdf_buffer = io.BytesIO()
    fig.savefig(pdf_buffer, format='pdf', bbox_inches='tight')
    pdf_buffer.seek(0)
    
    png_buffer = io.BytesIO()
    fig.savefig(png_buffer, format='png', dpi=300, bbox_inches='tight')
    png_buffer.seek(0)

    col_dl = st.columns(2)
    col_dl[0].download_button("📄 Plan PDF", pdf_buffer, f"plan_{scenario}.pdf", "application/pdf")
    col_dl[1].download_button("🖼️ Plan PNG", png_buffer, f"plan_{scenario}.png", "image/png")

    st.markdown("---")
    st.subheader("📊 Surfaces & Occupation")
    
    # Métriques Principales
    m1, m2 = st.columns(2)
    m1.metric("Bâtiment", f"{int(surface_totale)} m²")
    m2.metric("Allée", f"{int(surface_allee)} m²")
    
    m3, m4 = st.columns(2)
    m3.metric("Séchage Total", f"{int(surface_sechage_totale)} m²")
    m4.metric("Stockage Total", f"{int(surface_stock_totale)} m²")

    st.markdown("---")
    
    # Indicateurs de Longueur
    longueur_gauche = curseur_y
    if depassement:
        st.error(f"❌ **DÉPASSEMENT** : +{longueur_gauche - bat_longueur:.1f}m")
    else:
        st.success(f"✅ **LONGUEUR OK** : {longueur_gauche:.1f}m / {bat_longueur}m")

    # Espace Libre
    reste = surface_totale - surface_allee - surface_sechage_totale - surface_stock_totale
    st.metric("Espace Libre (Non alloué)", f"{int(reste)} m²")