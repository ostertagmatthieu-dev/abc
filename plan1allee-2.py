import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Simulateur Foug - Séquentiel", layout="wide")

st.title("Plan de Masse Opérationnel : version à une allée - proposition Jean-Marc")

# ==========================================
# 1. BARRE LATÉRALE (CONTRÔLES)
# ==========================================

with st.sidebar:
    st.header("1. Bâtiment & Structure")
    bat_longueur = st.slider("Longueur Zone (m)", 40, 200, 84, step=1)
    bat_largeur = st.slider("Largeur Zone (m)", 20, 80, 36, step=1, help="Largeur totale disponible")
    
    st.markdown("---")
    st.header("2. Organisation")
    st.info("Flux : Allée Ext. > J1 > J2 > J3 > Stock (Empilés)")
    
    largeur_allee = st.slider("Largeur Allée Extérieure (m)", 4.0, 12.0, 10.0, step=0.5)
    
    # Nouveau paramètre pour gérer la forme des lots
    largeur_utile = st.slider("Largeur max disponible (m)", 5.0, float(bat_largeur), float(bat_largeur), step=1.0)
    
    marge_securite = st.slider("Marge Sécurité (m)", 0.0, 2.0, 0.0, step=0.1)
    
    # CONTRAINTE MINIMALE
    MIN_Y = 4.5
    st.error(f"⚠️ Contrainte active : Profondeur Lot ≥ {MIN_Y}m")

    st.markdown("---")
    st.header("3. Paramètres Opérationnels")
    
    # --- GESTION DE LA FORME DU TAS ---
    st.markdown("### 📐 Géométrie")
    coeff_forme = st.slider("Coeff. Remplissage Stock", 0.3, 1.0, 0.65)
    espace_inter_matiere = st.slider("Espace entre Matières (Y)", 0.0, 3.0, 0.3, step=0.1)
    espace_inter_phase = st.slider("Espace entre Jours/Stock (Y)", 0.0, 2.0, 0.5, step=0.1)

    st.markdown("---")
    st.header("4. Flux & Recette")
    scenario = st.radio("Volume mensuel", [6000, 3000], horizontal=True)
    jours_ouvres = st.number_input("Jours ouvrés", 15, 30, 20)
    tonnage_jour = scenario / jours_ouvres
    
    st.metric("Flux Journalier", f"{tonnage_jour:.0f} t/jour")
    
    h_sechage = st.number_input("Hauteur Séchage (m)", 0.1, 3.0, 0.4)
    h_stock = st.number_input("Hauteur Stockage (pic) (m)", 0.1, 15.0, 7.0)
    duree_sechage = 3

    # --- RECETTE ---
    st.markdown("### 🧪 Recette")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**% Recette**")
        p_pam = st.number_input("% Rebuts PAM", 0, 100, 18)
        p_fon = st.number_input("% Fontes", 0, 100, 15)
        p_jet = st.number_input("% Jets", 0, 100, 37)
        p_gue = st.number_input("% Gueuset", 0, 100, 0)
        p_fer = st.number_input("% Ferraille", 0, 100, 30)
    
    with c2:
        st.markdown("**Densité**")
        d_pam = st.number_input("Dens. PAM", 0.1, 5.0, 1.5)
        d_fon = st.number_input("Dens. Fontes", 0.1, 5.0, 1.0)
        d_jet = st.number_input("Dens. Jets", 0.1, 5.0, 1.0)
        d_gue = st.number_input("Dens. Gueuset", 0.1, 5.0, 1.0)
        d_fer = st.number_input("Dens. Ferraille", 0.1, 5.0, 1.25)

# ==========================================
# 2. CALCULS MOTEUR
# ==========================================

MATIERES = {
    "Rebuts PAM": {"r": p_pam, "d": d_pam, "c": "#ff9933"},
    "Fontes Foug": {"r": p_fon, "d": d_fon, "c": "#ffcc66"},
    "Jets Blénod": {"r": p_jet, "d": d_jet, "c": "#0a82d3"},
    "Gueuset": {"r": p_gue, "d": d_gue, "c": "#aaaaaa"},
    "Ferraille": {"r": p_fer, "d": d_fer, "c": "#da1884"},
}

resultats = {}
surf_sechage_tot = 0
surf_stock_tot = 0

# Largeur effective (max X dispo)
largeur_max_x = max(1.0, largeur_utile - (2 * marge_securite))

def calculer_dimensions_lot(surface, width_max, min_y):
    """Calcule h (Y) et w (X) en respectant min_y"""
    y_theorique = surface / width_max
    if y_theorique < min_y:
        # Contrainte active : on fixe Y à min_y et on réduit X
        return min_y, surface / min_y, True # h, w, is_adapted
    else:
        # Pas de contrainte : plein largeur
        return y_theorique, width_max, False

for nom, data in MATIERES.items():
    if data["r"] == 0: continue
    
    flux_jour = tonnage_jour * (data["r"]/100)
    
    # --- SÉCHAGE (1 JOUR) ---
    vol_jour = flux_jour / data["d"]
    surf_jour = vol_jour / h_sechage
    
    h_jour, w_jour, adapt_jour = calculer_dimensions_lot(surf_jour, largeur_max_x, MIN_Y)
    
    # --- STOCKAGE ---
    vol_stock = (flux_jour * (15 if scenario==3000 else 10)) / data["d"]
    surf_stock = vol_stock / (h_stock * coeff_forme)
    
    h_stock_calc, w_stock, adapt_stock = calculer_dimensions_lot(surf_stock, largeur_max_x, MIN_Y)
    
    # Longueur Totale du bloc matière (Y)
    len_totale = (h_jour * 3) + h_stock_calc + (3 * espace_inter_phase)
    
    # Mise à jour des totaux globaux
    surf_sechage_tot += (surf_jour * 3)
    surf_stock_tot += surf_stock

    resultats[nom] = {
        # Dims Jour
        "h_jour": h_jour,
        "w_jour": w_jour,
        "adapt_jour": adapt_jour,
        "surf_jour": surf_jour,
        # Dims Stock
        "h_stock": h_stock_calc,
        "w_stock": w_stock,
        "adapt_stock": adapt_stock,
        "surf_stock": surf_stock,
        # Meta
        "len_totale": len_totale,
        "color": data["c"]
    }

# ==========================================
# 3. DESSIN
# ==========================================

# Hauteur totale nécessaire
hauteur_contenu = sum([res["len_totale"] + espace_inter_matiere for res in resultats.values()])
max_y_plot = max(bat_longueur, hauteur_contenu) + 10

fig_height = max(10, max_y_plot / 3) 
fig, ax = plt.subplots(figsize=(12, fig_height))

# --- STRUCTURE BÂTIMENT ---
ax.add_patch(patches.Rectangle((0, 0), bat_largeur, bat_longueur, edgecolor='black', facecolor='white', lw=3))

# --- ALLÉE EXTÉRIEURE ---
rect_allee = patches.Rectangle((-largeur_allee, 0), largeur_allee, bat_longueur, color='#d1d1d1', hatch='//', alpha=0.5, edgecolor='black')
ax.add_patch(rect_allee)
for i in range(10, int(bat_longueur), 20):
    ax.text(-largeur_allee/2, i, "ALLÉE EXT.", ha='center', va='center', rotation=90, color='#666', fontsize=8, fontweight='bold')

# Ligne de séparation mur/allée (CORRECTION : Segment fini au lieu de ligne infinie)
ax.plot([0, 0], [0, bat_longueur], color='black', linewidth=2)

# --- DESSIN DES MATIÈRES SÉQUENTIELLES ---
curseur_y = 0
depassement_global = False
x_start_base = marge_securite

for nom, res in resultats.items():
    color = res["color"]
    
    # --- SÉCHAGE J1, J2, J3 ---
    h_j = res["h_jour"]
    w_j = res["w_jour"]
    is_adapt_j = res["adapt_jour"]
    
    for j in range(3):
        is_overflow = (curseur_y + h_j > bat_longueur)
        if is_overflow: depassement_global = True
        
        fc = '#ffcccc' if is_overflow else color
        ec = 'red' if is_overflow else ('black' if not is_adapt_j else 'red')
        
        # Dessin Rectangle J(i)
        ax.add_patch(patches.Rectangle((x_start_base, curseur_y), w_j, h_j, facecolor=fc, edgecolor=ec, alpha=0.4))
        
        # Label J(i) COMPLET
        label = f"{nom} - J{j+1}"
        if is_adapt_j: label += f"\n(Min {MIN_Y}m)"
        # Ajout détails techniques
        label += f"\n{w_j:.1f}x{h_j:.1f}m\n{int(res['surf_jour'])} m²\n(H={h_sechage}m)"
        
        ax.text(x_start_base + w_j/2, curseur_y + h_j/2, label, 
                ha='center', va='center', fontsize=7, color='black', alpha=1.0, fontweight='normal',
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1))

        curseur_y += h_j + espace_inter_phase

    # --- STOCKAGE ---
    h_s = res["h_stock"]
    w_s = res["w_stock"]
    is_adapt_s = res["adapt_stock"]
    
    is_overflow = (curseur_y + h_s > bat_longueur)
    if is_overflow: depassement_global = True
    fc = '#ffcccc' if is_overflow else color
    ec = 'red' if is_overflow else ('black' if not is_adapt_s else 'red')
    
    ax.add_patch(patches.Rectangle((x_start_base, curseur_y), w_s, h_s, facecolor=fc, edgecolor=ec, alpha=0.8, hatch='..'))
    
    # Label Stock COMPLET
    label_s = f"STOCK {nom}\n{int(res['surf_stock'])}m²\n{w_s:.1f}x{h_s:.1f}m"
    if is_adapt_s: label_s += f"\n(Adapté Min {MIN_Y}m)"
    label_s += f"\n(H={h_stock}m)"
    
    ax.text(x_start_base + w_s/2, curseur_y + h_s/2, label_s, 
            ha='center', va='center', fontsize=8, fontweight='bold',
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
        
    curseur_y += h_s
    
    # Séparateur Matière
    ax.plot([0, bat_largeur], [curseur_y + espace_inter_matiere/2, curseur_y + espace_inter_matiere/2], 
            color='black', linestyle='-', linewidth=1.5)
    
    curseur_y += espace_inter_matiere

# --- CAMION (Démo) ---
def draw_truck(ax, x, y, col):
    w, l = 2.5, 15
    ax.add_patch(patches.Rectangle((x, y), w, l, facecolor='white', edgecolor='black'))
    ax.add_patch(patches.Rectangle((x, y + l - 3), w, 3, facecolor=col, edgecolor='black'))

if largeur_allee > 3:
    draw_truck(ax, -largeur_allee/2 - 1.25, 5, '#4CAF50')

# --- INFOS ET LIMITES ---
# Orientations
ax.text(-largeur_allee - 1, bat_longueur/2, "SNCF", rotation=90, va='center', fontweight='bold', color='#1a237e')
ax.text(bat_largeur + 2, bat_longueur/2, "CANAL", rotation=90, va='center', fontweight='bold', color='#1a237e')
ax.text(bat_largeur/2, -3, "FOUG", ha='center', fontsize=12, fontweight='bold', color='#1a237e')
ax.text(bat_largeur/2, bat_longueur + 3, "TOUL", ha='center', fontsize=12, fontweight='bold', color='#1a237e')

# Étiquettes de synthèse (En bas)
surf_tot = bat_largeur * bat_longueur
ax.text(bat_largeur/2, -6, f"ZONE : {bat_largeur}m x {bat_longueur}m", ha='center', fontsize=10, fontweight='bold')
ax.text(bat_largeur/2, -9, f"SURFACE TOTALE : {int(surf_tot)} m²", ha='center', fontsize=10, fontweight='bold', bbox=dict(facecolor='yellow', alpha=0.3))
ax.text(bat_largeur/2, -12, f"SÉCHAGE : {int(surf_sechage_tot)} m² | STOCK : {int(surf_stock_tot)} m²", ha='center', fontsize=9, fontweight='bold', bbox=dict(facecolor='orange', alpha=0.3))

if depassement_global:
    # CORRECTION : Segment fini pour la ligne de dépassement
    ax.plot([-largeur_allee, bat_largeur], [bat_longueur, bat_longueur], color='red', linewidth=3)
    ax.text(bat_largeur, bat_longueur, "LIMITE", color='red', fontweight='bold', va='bottom', ha='right')

ax.set_xlim(-largeur_allee - 8, bat_largeur + 8)
# On agrandit la zone en bas pour afficher les étiquettes (-18)
ax.set_ylim(-18, max_y_plot)
ax.set_aspect('equal')
ax.axis('off')

# ==========================================
# 4. EXPORT & KPI (DÉTAILLÉS)
# ==========================================

col1, col2 = st.columns([2, 1])

with col1:
    st.pyplot(fig)

with col2:
    st.subheader("📥 Export")
    c1, c2 = st.columns(2)
    buf = io.BytesIO()
    fig.savefig(buf, format='pdf', bbox_inches='tight')
    buf.seek(0)
    c1.download_button("PDF", buf, "plan_optimise.pdf", "application/pdf")

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=200, bbox_inches='tight')
    buf.seek(0)
    c2.download_button("PNG", buf, "plan_optimise.png", "image/png")
    
    st.markdown("---")
    st.subheader("📊 Bilan Surfaces")
    
    # Check longueur
    if depassement_global:
        st.error(f"❌ **MANQUE LONGUEUR**")
        st.write(f"Utilisé : {curseur_y:.1f}m / {bat_longueur}m")
        st.write(f"Dépassement : +{curseur_y - bat_longueur:.1f} m")
    else:
        st.success(f"✅ **LONGUEUR OK**")
        st.write(f"Utilisé : {curseur_y:.1f}m / {bat_longueur}m")
        st.write(f"Reste : {bat_longueur - curseur_y:.1f} m")
    
    st.markdown("---")

    c1, c2 = st.columns(2)
    c1.metric("Dimensions Zone", f"{bat_largeur}m x {bat_longueur}m")
    c2.metric("Surface Totale Zone", f"{int(bat_largeur*bat_longueur)} m²")

    c1, c2 = st.columns(2)
    c1.metric("Séchage (Plate)", f"{int(surf_sechage_tot)} m²")
    c2.metric("Stockage (Talutée)", f"{int(surf_stock_tot)} m²")
    
    surface_allees = bat_longueur * largeur_allee # Allée externe
    c1, c2 = st.columns(2)
    c1.metric("Allée Extérieure", f"{int(surface_allees)} m²")
    c2.metric("Surface Matière Totale", f"{int(surf_sechage_tot + surf_stock_tot)} m²")
    
    st.info(f"Largeur utile utilisée pour les tas : {largeur_max_x:.1f}m")