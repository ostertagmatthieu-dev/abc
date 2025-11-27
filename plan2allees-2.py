import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Simulateur Entrepôt Expert", layout="wide")

st.title("Plan de Masse : version à deux allées - Rebuts PAM & Fontes Groupés")

# ==========================================
# 1. BARRE LATÉRALE (CONTRÔLES)
# ==========================================

with st.sidebar:
    st.header("1. Bâtiment & Structure")
    bat_longueur = st.slider("Longueur Bâtiment (m)", 40, 200, 57, step=1)
    bat_largeur = st.slider("Largeur Bâtiment (m)", 30, 100, 75, step=1)
    
    # --- ALIGNEMENT ---
    alignement_mode = st.radio(
        "Référence d'alignement (si largeur réduite) :",
        ["Côté Allée (Vide vers le mur)", "Côté Mur (Vide vers l'allée)"],
        index=0
    )

    st.markdown("---")
    st.header("2. Zone Centrale (Fixe)")
    largeur_stock_central = st.slider("Largeur Stockage Central (m)", 4.0, 20.0, 16.0, step=0.5)
    largeur_allee = st.slider("Largeur d'une Allée (m)", 4.0, 15.0, 10.0, step=0.5)
    marge_securite = st.slider("Marge Allée / Piste (m)", 0.0, 2.0, 0.0, step=0.1)
    
    # Calcul Espace Dispo
    largeur_centrale_totale = largeur_stock_central + (2 * largeur_allee) + (2 * marge_securite)
    X_MAX_DISPO = (bat_largeur - largeur_centrale_totale) / 2
    
    if X_MAX_DISPO <= 1:
        st.error(f"⚠️ Zone centrale trop large ! Reste {X_MAX_DISPO:.2f}m sur les côtés.")
    else:
        st.success(f"Largeur MAX dispo par aile : **{X_MAX_DISPO:.2f} m**")

    st.markdown("---")
    st.header("3. Paramètres Opérationnels")
    
    largeur_passage = st.slider("Largeur Passage Engin (m)", 0.0, 4.0, 0.0, step=0.5)
    
    # --- GESTION DE LA FORME DU TAS (STOCKAGE UNIQUEMENT) ---
    st.markdown("### 📐 Géométrie (Stockage Uniquement)")
    st.info("Le coefficient ne s'applique qu'au Stockage. Le Séchage est calculé à plat (Vol = Surf x H).")
    coeff_forme = st.slider(
        "Coeff. de Remplissage (Stock)", 
        0.3, 1.0, 0.5, 
        step=0.05,
        help="Appliqué uniquement au stock central. 1.0 = Cube. 0.5 = Tas. Le séchage reste à 1.0."
    )
    # ---------------------------------------------
    
    col_sep1, col_sep2 = st.columns(2)
    espace_inter_matiere = col_sep1.slider("Esp. Matières", 0.0, 3.0, 0.3, step=0.1)
    espace_inter_lot = col_sep2.slider("Esp. Lots", 0.0, 2.0, 0.5, step=0.1)
    
    MIN_LONGUEUR_LOT_Y = 4.5 
    st.info(f"Sécurité : Longueur Lot (Y) ≥ {MIN_LONGUEUR_LOT_Y}m")

    st.markdown("---")
    st.header("4. Flux & Recette")
    scenario = st.radio("Volume mensuel", [6000, 3000], horizontal=True)
    jours_ouvres = st.number_input("Jours ouvrés", 15, 30, 20)
    tonnage_jour = scenario / jours_ouvres
    
    # AFFICHAGE TONNAGE
    st.metric("Flux Journalier", f"{tonnage_jour:.0f} t/jour", delta="Base de calcul")
    
    h_sechage = st.number_input("Hauteur Séchage (m)", 0.1, 2.0, 0.4)
    h_stock = st.number_input("Hauteur Stockage (pic) (m)", 0.1, 15.0, 7.0)
    duree_sechage = 3

    # --- RECETTE (INTERFACE COLONNES) ---
    st.markdown("### 🧪 Recette ")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Proportion**")
        p_pam = st.number_input("% Rebuts PAM", 0, 100, 18)
        p_fon = st.number_input("% Fontes Foug", 0, 100, 15)
        p_jet = st.number_input("% Jets", 0, 100, 37)
        p_gue = st.number_input("% Gueuset", 0, 100, 0)
        p_fer = st.number_input("% Ferraille", 0, 100, 30)
    
    with c2:
        st.markdown("**Densité**")
        d_pam = st.number_input("Rebuts PAM", 0.1, 5.0, 1.5)
        d_fon = st.number_input("Fontes Foug", 0.1, 5.0, 1.0)
        d_jet = st.number_input("Jets", 0.1, 5.0, 1.0)
        d_gue = st.number_input("Gueuset", 0.1, 5.0, 1.0)
        d_fer = st.number_input("Ferraille", 0.1, 5.0, 1.25)

    total_pct = p_pam + p_jet + p_gue + p_fon + p_fer
    if total_pct != 100:
        st.warning(f"⚠️ Total Recette = {total_pct}%")

# ==========================================
# 2. CALCULS MOTEUR (ALGORITHME INTELLIGENT)
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

# Largeur de base = Max dispo
width_base = max(0.1, X_MAX_DISPO)

# Définition des groupes spéciaux
groupe_special = ["Rebuts PAM", "Fontes Foug"]
is_groupe_actif = (p_pam > 0) and (p_fon > 0)

for nom, data in MATIERES.items():
    if data["r"] == 0: continue
    
    flux_jour = tonnage_jour * (data["r"]/100)
    
    # --- SÉCHAGE (ZONE PLATE) ---
    vol_sechage_total = (flux_jour * duree_sechage) / data["d"]
    surf_sechage_total = vol_sechage_total / h_sechage 
    
    # LOGIQUE SPÉCIALE PAM / FONTES
    # Si c'est l'un des deux et que les deux existent, on met TOUT le séchage d'un seul côté
    # Donc on divise par 3 (3 lots sur 1 côté) au lieu de 6 (3 lots sur 2 côtés)
    if is_groupe_actif and nom in groupe_special:
        nb_lots_par_cote = 3
        # On ne divise PAS par 2 ici car tout le volume est du même côté
        surf_un_lot = surf_sechage_total / nb_lots_par_cote
    else:
        # Cas Classique (Moitié Gauche / Moitié Droite)
        surf_un_lot = (surf_sechage_total / 2) / 3
    
    # ALGORITHME DE FORME
    Y_mat_theo = surf_un_lot / width_base
    Y_lot_theo = Y_mat_theo + largeur_passage
    
    if Y_lot_theo >= MIN_LONGUEUR_LOT_Y:
        final_X = width_base
        final_Y_lot = Y_lot_theo
        final_Y_mat = Y_mat_theo
        mode = "Plein"
    else:
        final_Y_lot = MIN_LONGUEUR_LOT_Y
        Y_mat_dispo = max(0.1, final_Y_lot - largeur_passage)
        final_X = surf_un_lot / Y_mat_dispo
        final_Y_mat = Y_mat_dispo
        mode = "Adapté"
    
    # --- STOCKAGE ---
    vol_stock = (flux_jour * (15 if scenario==3000 else 10)) / data["d"]
    surf_stock = vol_stock / (h_stock * coeff_forme)
    
    # Calcul Longueur Stock
    if is_groupe_actif and nom in groupe_special:
        # Stock divisé en 2 en largeur -> Longueur doublée (ou presque)
        longueur_stock = surf_stock / (largeur_stock_central / 2)
    else:
        # Stock pleine largeur
        longueur_stock = surf_stock / largeur_stock_central

    resultats[nom] = {
        "dim_x": final_X,
        "dim_y_lot": final_Y_lot,
        "dim_y_mat": final_Y_mat,
        "len_stock": longueur_stock,
        "surf_sech": surf_sechage_total,
        "surf_stk": surf_stock,
        "color": data["c"],
        "mode": mode
    }
    surf_sechage_tot += surf_sechage_total
    surf_stock_tot += surf_stock

# ==========================================
# 3. DESSIN
# ==========================================

fig, ax = plt.subplots(figsize=(14, 18))

clip_box = patches.Rectangle((0, 0), bat_largeur, bat_longueur, transform=ax.transData)
ax.add_patch(patches.Rectangle((0, 0), bat_largeur, bat_longueur, edgecolor='black', facecolor='white', lw=2))

# --- STRUCTURE CENTRALE ---
largeur_structure_centrale = (largeur_allee * 2) + largeur_stock_central + (marge_securite * 2)
x_start_central = (bat_largeur - largeur_structure_centrale) / 2

x_allee_1_start = x_start_central + marge_securite
x_stock_start = x_allee_1_start + largeur_allee
x_allee_2_start = x_stock_start + largeur_stock_central

anchor_G = x_start_central 
anchor_D = x_allee_2_start + largeur_allee + marge_securite

# Dessin Allées & Fond Stock (Clippés)
r1 = patches.Rectangle((x_allee_1_start, 0), largeur_allee, bat_longueur, color='#e0e0e0', alpha=0.5, hatch='//')
r1.set_clip_path(clip_box)
ax.add_patch(r1)
ax.text(x_allee_1_start + largeur_allee/2, bat_longueur/2, "ALLÉE 1", ha='center', rotation=90, color='#666')

r2 = patches.Rectangle((x_stock_start, 0), largeur_stock_central, bat_longueur, color='#f8f8f8', alpha=0.3)
r2.set_clip_path(clip_box)
ax.add_patch(r2)

r3 = patches.Rectangle((x_allee_2_start, 0), largeur_allee, bat_longueur, color='#e0e0e0', alpha=0.5, hatch='//')
r3.set_clip_path(clip_box)
ax.add_patch(r3)
ax.text(x_allee_2_start + largeur_allee/2, bat_longueur/2, "ALLÉE 2", ha='center', rotation=90, color='#666')

# --- AJOUT CAMIONS (NOUVEAU) ---
# Fonction helper pour dessiner un camion
def draw_truck(ax, x_pos, y_pos, width, length=12, color='white', direction='up'):
    # Dimensions standard semi-remorque (approximatif)
    cab_len = 2.5
    trailer_len = length - cab_len
    
    if direction == 'up':
        y_trailer = y_pos
        y_cab = y_pos + trailer_len + 0.5 # 0.5 espace
        # Remorque
        ax.add_patch(patches.Rectangle((x_pos, y_trailer), width, trailer_len, facecolor='white', edgecolor='black'))
        # Cabine
        ax.add_patch(patches.Rectangle((x_pos, y_cab), width, cab_len, facecolor=color, edgecolor='black'))
        # Roues (visuel)
        ax.add_patch(patches.Circle((x_pos, y_trailer+1), 0.3, color='black'))
        ax.add_patch(patches.Circle((x_pos+width, y_trailer+1), 0.3, color='black'))
        ax.add_patch(patches.Circle((x_pos, y_trailer+trailer_len-1), 0.3, color='black'))
        ax.add_patch(patches.Circle((x_pos+width, y_trailer+trailer_len-1), 0.3, color='black'))
        
    else: # down
        y_cab = y_pos
        y_trailer = y_pos + cab_len + 0.5
        # Cabine
        ax.add_patch(patches.Rectangle((x_pos, y_cab), width, cab_len, facecolor=color, edgecolor='black'))
        # Remorque
        ax.add_patch(patches.Rectangle((x_pos, y_trailer), width, trailer_len, facecolor='white', edgecolor='black'))
        # Roues
        ax.add_patch(patches.Circle((x_pos, y_trailer+1), 0.3, color='black'))
        ax.add_patch(patches.Circle((x_pos+width, y_trailer+1), 0.3, color='black'))
        ax.add_patch(patches.Circle((x_pos, y_trailer+trailer_len-1), 0.3, color='black'))
        ax.add_patch(patches.Circle((x_pos+width, y_trailer+trailer_len-1), 0.3, color='black'))

# Paramètres camion
truck_width = 2.5
truck_length = 15.0

# Sécurité : on dessine seulement si l'allée est assez large
if largeur_allee >= truck_width + 0.5:
    # Camion Allée 1 (Montant) - Alignement dynamique
    pos_x_t1 = x_allee_1_start + (largeur_allee - truck_width)/2
    
    # Calcul position Y pour être au milieu d'un lot (le 2ème lot de la première matière)
    y_pos_t1 = 5 # default fallback
    if len(resultats) > 0:
        # On prend la première matière de la liste (qui est la première dessinée en Y=0)
        first_mat = list(resultats.values())[0]
        h_lot_ref = first_mat["dim_y_lot"]
        
        # On cible le centre du 2ème lot (index 1) pour être sûr qu'il ne sort pas du cadre
        # Y start lot 2 = h_lot_ref + espace_inter_lot
        # Y center lot 2 = Y start + (h_lot_ref / 2)
        y_center_lot = h_lot_ref + espace_inter_lot + (h_lot_ref / 2)
        
        # Le dessin du camion se fait depuis l'arrière, donc on retire la moitié de sa longueur
        y_pos_t1 = y_center_lot - (truck_length / 2)
    
    if bat_longueur > 20:
        draw_truck(ax, pos_x_t1, y_pos_t1, truck_width, truck_length, color='#d32f2f', direction='up')
    
    # Camion Allée 2 (Descendant, au fond) - Fixe
    pos_x_t2 = x_allee_2_start + (largeur_allee - truck_width)/2
    if bat_longueur > 30:
        draw_truck(ax, pos_x_t2, bat_longueur - 20, truck_width, truck_length, color='#1976d2', direction='down')
# -------------------------------

# Fonctions utilitaires
def safe_draw_rect(x, y, w, h, color, alpha=1.0, hatch=None, edge='black'):
    if y > bat_longueur: return True
    fc = '#ffcccc' if y + h > bat_longueur else color
    ec = 'red' if y + h > bat_longueur else edge
    rect = patches.Rectangle((x, y), w, h, facecolor=fc, alpha=alpha, hatch=hatch, edgecolor=ec)
    rect.set_clip_path(clip_box)
    ax.add_patch(rect)
    return y + h > bat_longueur

curseur_y = 0
depassement_longueur = False
processed_materials = []

# --- 1. DESSIN DU GROUPE PAM / FONTES (SI ACTIF) ---
if is_groupe_actif:
    pam_res = resultats.get("Rebuts PAM")
    fon_res = resultats.get("Fontes Foug")
    
    if pam_res and fon_res:
        # On détermine la hauteur max de ce "bloc combiné"
        h_bloc_pam = (3 * pam_res["dim_y_lot"]) + (2 * espace_inter_lot)
        h_bloc_fon = (3 * fon_res["dim_y_lot"]) + (2 * espace_inter_lot)
        
        # Le curseur avance du MAX des hauteurs (Séchage G, Séchage D, Stock G, Stock D)
        h_stock_pam = pam_res["len_stock"]
        h_stock_fon = fon_res["len_stock"]
        
        # Calcul de la hauteur nécessaire pour ce niveau
        max_h_needed = max(h_bloc_pam, h_bloc_fon, h_stock_pam, h_stock_fon)
        
        # --- DESSIN GAUCHE : PAM SEULEMENT ---
        w_lot_pam = pam_res["dim_x"]
        x_G_pam = anchor_G - w_lot_pam if alignement_mode == "Côté Allée (Vide vers le mur)" else 0
        col_alert_pam = 'red' if pam_res["mode"] == "Adapté" else 'black'
        
        for i in range(3):
            y = curseur_y + (i * pam_res["dim_y_lot"]) + (i * espace_inter_lot)
            safe_draw_rect(x_G_pam, y, w_lot_pam, pam_res["dim_y_mat"]/2, pam_res["color"], 0.6)
            y_p = y + pam_res["dim_y_mat"]/2
            safe_draw_rect(x_G_pam, y_p, w_lot_pam, largeur_passage, '#f0f0f0', 0.4, '--')
            y_m2 = y_p + largeur_passage
            safe_draw_rect(x_G_pam, y_m2, w_lot_pam, pam_res["dim_y_mat"]/2, pam_res["color"], 0.6)
            
        # Label complet PAM
        label_text_pam = f"Rebuts PAM\n{w_lot_pam:.1f}x{pam_res['dim_y_lot']:.1f}m\n{int(pam_res['surf_sech'])} m²\n(H={h_sechage}m)"
        ax.text(x_G_pam + w_lot_pam/2, curseur_y + h_bloc_pam/2, label_text_pam, 
                ha='center', va='center', fontsize=8, fontweight='bold', color=col_alert_pam,
                bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', pad=2))

        # --- DESSIN DROITE : FONTES SEULEMENT ---
        w_lot_fon = fon_res["dim_x"]
        x_D_fon = anchor_D if alignement_mode == "Côté Allée (Vide vers le mur)" else bat_largeur - w_lot_fon
        col_alert_fon = 'red' if fon_res["mode"] == "Adapté" else 'black'
        
        for i in range(3):
            y = curseur_y + (i * fon_res["dim_y_lot"]) + (i * espace_inter_lot)
            safe_draw_rect(x_D_fon, y, w_lot_fon, fon_res["dim_y_mat"]/2, fon_res["color"], 0.6)
            y_p = y + fon_res["dim_y_mat"]/2
            safe_draw_rect(x_D_fon, y_p, w_lot_fon, largeur_passage, '#f0f0f0', 0.4, '--')
            y_m2 = y_p + largeur_passage
            safe_draw_rect(x_D_fon, y_m2, w_lot_fon, fon_res["dim_y_mat"]/2, fon_res["color"], 0.6)

        # Label complet Fontes
        label_text_fon = f"Fontes Foug\n{w_lot_fon:.1f}x{fon_res['dim_y_lot']:.1f}m\n{int(fon_res['surf_sech'])} m²\n(H={h_sechage}m)"
        ax.text(x_D_fon + w_lot_fon/2, curseur_y + h_bloc_fon/2, label_text_fon, 
                ha='center', va='center', fontsize=8, fontweight='bold', color=col_alert_fon,
                bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', pad=2))

        # --- DESSIN CENTRAL SPLITTÉ ---
        # PAM (Gauche du centre)
        y_center_pam = curseur_y + max_h_needed/2 
        y_stk_pam_start = y_center_pam - (h_stock_pam/2)
        safe_draw_rect(x_stock_start, y_stk_pam_start, largeur_stock_central/2, h_stock_pam, pam_res["color"], 0.4, '..')
        
        label_stock_pam = (
            f"Stock R. PAM\n"
            f"{int(pam_res['surf_stk'])}m²\n"
            f"{largeur_stock_central/2:.1f}x{h_stock_pam:.1f}m\n"
            f"(H={h_stock}m)"
        )
        ax.text(x_stock_start + largeur_stock_central/4, y_center_pam, label_stock_pam, 
                ha='center', va='center', fontsize=7, color='black', fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))

        # FONTES (Droite du centre)
        y_stk_fon_start = y_center_pam - (h_stock_fon/2)
        safe_draw_rect(x_stock_start + largeur_stock_central/2, y_stk_fon_start, largeur_stock_central/2, h_stock_fon, fon_res["color"], 0.4, '..')
        
        label_stock_fon = (
            f"Stock F. Foug\n"
            f"{int(fon_res['surf_stk'])}m²\n"
            f"{largeur_stock_central/2:.1f}x{h_stock_fon:.1f}m\n"
            f"(H={h_stock}m)"
        )
        ax.text(x_stock_start + (largeur_stock_central*3/4), y_center_pam, label_stock_fon, 
                ha='center', va='center', fontsize=7, color='black', fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))
        
        # Ligne de séparation visuelle
        ax.plot([x_stock_start + largeur_stock_central/2, x_stock_start + largeur_stock_central/2], 
                [curseur_y, curseur_y + max_h_needed], color='black', linestyle=':', linewidth=1)

        # Mise à jour curseur
        curseur_y += max_h_needed + espace_inter_matiere
        processed_materials.extend(["Rebuts PAM", "Fontes Foug"])

# --- 2. DESSIN AUTRES MATIÈRES (Classique) ---
for nom, res in resultats.items():
    if nom in processed_materials: continue # Déjà fait
    if MATIERES[nom]["r"] == 0: continue
    
    h_bloc = (3 * res["dim_y_lot"]) + (2 * espace_inter_lot)
    w_lot = res["dim_x"]
    col_alert = 'red' if res["mode"] == "Adapté" else 'black'
    
    # Position X
    if alignement_mode == "Côté Allée (Vide vers le mur)":
        x_G = anchor_G - w_lot
        x_D = anchor_D
    else:
        x_G = 0
        x_D = bat_largeur - w_lot

    is_overflow = False

    # Dessin GAUCHE
    for i in range(3):
        y = curseur_y + (i * res["dim_y_lot"]) + (i * espace_inter_lot)
        ov1 = safe_draw_rect(x_G, y, w_lot, res["dim_y_mat"]/2, res["color"], 0.6)
        y_p = y + res["dim_y_mat"]/2
        ov2 = safe_draw_rect(x_G, y_p, w_lot, largeur_passage, '#f0f0f0', 0.4, '--')
        y_m2 = y_p + largeur_passage
        ov3 = safe_draw_rect(x_G, y_m2, w_lot, res["dim_y_mat"]/2, res["color"], 0.6)
        if ov1 or ov2 or ov3: is_overflow = True

    if h_bloc > 1 and curseur_y + h_bloc/2 < bat_longueur:
        label_text = f"{nom}\n{w_lot:.1f}x{res['dim_y_lot']:.1f}m\n{int(res['surf_sech']/2)} m²\n(H={h_sechage}m)"
        ax.text(x_G + w_lot/2, curseur_y + h_bloc/2, label_text, 
                ha='center', va='center', fontsize=8, fontweight='bold', color=col_alert,
                bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', pad=2))

    # Dessin DROITE
    for i in range(3):
        y = curseur_y + (i * res["dim_y_lot"]) + (i * espace_inter_lot)
        safe_draw_rect(x_D, y, w_lot, res["dim_y_mat"]/2, res["color"], 0.6)
        y_p = y + res["dim_y_mat"]/2
        safe_draw_rect(x_D, y_p, w_lot, largeur_passage, '#f0f0f0', 0.4, '--')
        y_m2 = y_p + largeur_passage
        safe_draw_rect(x_D, y_m2, w_lot, res["dim_y_mat"]/2, res["color"], 0.6)
    
    if h_bloc > 1 and curseur_y + h_bloc/2 < bat_longueur:
        ax.text(x_D + w_lot/2, curseur_y + h_bloc/2, label_text, 
                ha='center', va='center', fontsize=8, fontweight='bold', color=col_alert,
                bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', pad=2))

    # Dessin STOCK CENTRAL (Plein)
    y_center = curseur_y + h_bloc / 2
    y_stk_start = y_center - (res["len_stock"] / 2)
    ov = safe_draw_rect(x_stock_start, y_stk_start, largeur_stock_central, res["len_stock"], res["color"], 0.4, '..')
    
    if res["len_stock"] > 0.5 and y_center < bat_longueur:
        label_stock = f"Stock {nom}\n{int(res['surf_stk'])}m²\n{largeur_stock_central:.1f}x{res['len_stock']:.1f}m\n(H={h_stock}m)"
        ax.text(x_stock_start + largeur_stock_central/2, y_center, 
                label_stock, 
                ha='center', va='center', fontsize=7, color='black', fontweight='bold',
                bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))
    
    # Check overflow
    y_end = max(curseur_y + h_bloc, y_stk_start + res["len_stock"])
    if y_end > bat_longueur: depassement_longueur = True
    
    curseur_y = y_end + espace_inter_matiere

# --- ORIENTATION & COTES ---
ax.text(bat_largeur + 2, bat_longueur/2, "CANAL", va='center', rotation=90, fontsize=12, fontweight='bold', color='darkblue')
ax.text(-2, bat_longueur/2, "SNCF", va='center', rotation=90, fontsize=12, fontweight='bold', color='darkblue')
ax.text(bat_largeur/2, -3, "FOUG", ha='center', fontsize=12, fontweight='bold', color='darkblue')
ax.text(bat_largeur/2, bat_longueur + 3, "TOUL", ha='center', fontsize=12, fontweight='bold', color='darkblue')

# Surface Totale & Dimensions
surf_tot = bat_largeur * bat_longueur
ax.text(bat_largeur/2, -6, f"BÂTIMENT : {bat_largeur}m x {bat_longueur}m", ha='center', fontsize=12, fontweight='bold')
ax.text(bat_largeur/2, -8, f"SURFACE TOTALE : {int(surf_tot)} m²", ha='center', fontsize=12, fontweight='bold', 
        bbox=dict(facecolor='yellow', alpha=0.3))
ax.text(bat_largeur/2, -11, f"SURFACE SÉCHAGE : {int(surf_sechage_tot)} m² | SURFACE STOCKAGE : {int(surf_stock_tot)} m²", 
        ha='center', fontsize=12, fontweight='bold', 
        bbox=dict(facecolor='orange', alpha=0.3))

# Limites Graphique
ax.set_xlim(-10, bat_largeur + 10)
ax.set_ylim(-12, bat_longueur + 10)
ax.set_aspect('equal')
ax.axis('off')
ax.set_title(f"PLAN D'IMPLANTATION - {scenario} T/MOIS (Stock Taluté {coeff_forme})", fontsize=18, fontweight='bold', pad=20)

# ==========================================
# 4. EXPORT & KPI
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
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    c2.download_button("PNG", buf, "plan_optimise.png", "image/png")
    
    st.markdown("---")
    st.subheader("📊 Bilan Surfaces")
    c1, c2 = st.columns(2)
    c1.metric("Dimensions Totales", f"{bat_largeur}m x {bat_longueur}m")
    c2.metric("Surface Totale Bâtiment", f"{int(bat_largeur*bat_longueur)} m²")

    c1, c2 = st.columns(2)
    c1.metric("Séchage (Plate)", f"{int(surf_sechage_tot)} m²")
    c2.metric("Stockage (Talutée)", f"{int(surf_stock_tot)} m²")
    
    surface_allees = bat_longueur * largeur_allee * 2
    c1, c2 = st.columns(2)
    c1.metric("Allées de Circulation", f"{int(surface_allees)} m²")
    c2.metric("Surface Utile Totale", f"{int(surf_sechage_tot + surf_stock_tot + surface_allees)} m²")
    
    if depassement_longueur:
        st.error(f"❌ **MANQUE LONGUEUR**")
    else:
        st.success(f"✅ **LONGUEUR OK**")
