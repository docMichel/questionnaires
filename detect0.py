#!/usr/bin/env python3
"""
Dépouille les questionnaires remplis
Usage: python depouiller_reponses.py template.json reponses.pdf output.json
"""
import cv2
import numpy as np
from pdf2image import convert_from_path
import json
import sys
import os

from detection_cases import detecter_cases_completes, regrouper_par_lignes
from reperage import (
    nettoyer_lignes_verticales_agressif,
    trouver_ligne_echelle,
    trouver_bords_ligne_echelle
)

# ============================================================
# CONSTANTES
# ============================================================

TOLERANCE_X = 200  # Tolérance pour matcher X (pixels)

# Critères de cochage
SEUIL_REMPLISSAGE = 0.5  # 50% de noir
MIN_COMPOSANTES = 1       # 2+ objets


# ============================================================
# ÉCHELLE
# ============================================================

def detecter_echelle_seule(image):
    """Détecte l'échelle"""
    clean = nettoyer_lignes_verticales_agressif(image)
    ligne = trouver_ligne_echelle(clean)
    if not ligne:
        return None
    
    y_echelle = ligne[1]
    bords = trouver_bords_ligne_echelle(clean, y_echelle)
    if not bords:
        return None
    
    x_gauche, x_droite = bords
    return {
        'gauche': {'x': x_gauche, 'y': y_echelle},
        'droite': {'x': x_droite, 'y': y_echelle}
    }


def calculer_dx(echelle_template, echelle_reponse):
    """Calcule décalage horizontal"""
    if not echelle_template or not echelle_reponse:
        return 0
    return echelle_reponse['gauche']['x'] - echelle_template['gauche']['x']

# === CONSTANTES À AJUSTER ===
MARGE_CROP = 250
MARGE_CROP_HAUT = MARGE_CROP // 2
MARGE_CROP_BAS = MARGE_CROP
EPAISSEUR_SUPPRESSION = 20
SEUIL_BINARISATION = 200
HAUTEUR_BANDE = 200
OFFSET_BANDE = 20
AIRE_MIN_BLOB = 200
TOLERANCE_REGULARITE = 0.3
LARGEUR_MAX_CHIFFRE = 45  # Largeur max d'un chiffre imprimé (en pixels)


def coter_echelle(image, echelle, output_path):
    """Détecte les crayonnages en excluant les chiffres réguliers"""
    if not echelle:
        return []
    
    x_gauche = echelle['gauche']['x']
    x_droite = echelle['droite']['x']
    y_echelle = echelle['gauche']['y']
    
    largeur_totale = x_droite - x_gauche
    largeur_graduation = largeur_totale / 5
    
    # === 1. CROP ===
    x_crop_min = max(0, x_gauche - MARGE_CROP)
    x_crop_max = min(image.shape[1], x_droite + MARGE_CROP)
    y_crop_min = max(0, y_echelle - MARGE_CROP_HAUT)
    y_crop_max = min(image.shape[0], y_echelle + MARGE_CROP_BAS)
    
    image_crop = image[y_crop_min:y_crop_max, x_crop_min:x_crop_max].copy()
    
    x_gauche_crop = x_gauche - x_crop_min
    x_droite_crop = x_droite - x_crop_min
    y_echelle_crop = y_echelle - y_crop_min
    
    # === 2. BINARISER ===
    gray = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
    _, binaire = cv2.threshold(gray, SEUIL_BINARISATION, 255, cv2.THRESH_BINARY_INV)
    
    # === 3. SUPPRIMER LA LIGNE D'ÉCHELLE ===
    y_suppr_min = max(0, y_echelle_crop - EPAISSEUR_SUPPRESSION)
    y_suppr_max = min(binaire.shape[0], y_echelle_crop + EPAISSEUR_SUPPRESSION)
    binaire[y_suppr_min:y_suppr_max, x_gauche_crop:x_droite_crop] = 0
    
    # === 4. DÉFINIR LA BANDE ===
    y_bande_min = y_suppr_max + OFFSET_BANDE
    y_bande_max = min(binaire.shape[0], y_bande_min + HAUTEUR_BANDE)
    
    bande = binaire[y_bande_min:y_bande_max, :].copy()
    
    # === 5. DÉTECTER BLOBS ===
    nb_composantes, labels, stats, centroids = cv2.connectedComponentsWithStats(bande)
    
    blobs_info = []
    
    for i in range(1, nb_composantes):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        
        if area > AIRE_MIN_BLOB:
            cx = int(centroids[i][0])
            cy = int(centroids[i][1])
            
            blobs_info.append({
                'x': x,
                'y': y,
                'w': w,
                'h': h,
                'area': area,
                'cx': cx,
                'cy': cy
            })
    
    print(f"    ✓ {len(blobs_info)} blobs significatifs")
    
    # === 6. FILTRER PAR LARGEUR ===
    # Séparer petits (chiffres) et gros (crayonnages)
    blobs_chiffres = [b for b in blobs_info if b['w'] <= LARGEUR_MAX_CHIFFRE]
    blobs_crayonnages = [b for b in blobs_info if b['w'] > LARGEUR_MAX_CHIFFRE]
    
    print(f"    ✓ {len(blobs_chiffres)} chiffres (w<={LARGEUR_MAX_CHIFFRE})")
    print(f"    ✓ {len(blobs_crayonnages)} crayonnages (w>{LARGEUR_MAX_CHIFFRE})")
    
    # === 7. ASSOCIER AUX GRADUATIONS ===
    scores_detectes = []
    
    for blob in blobs_crayonnages:
        cx_absolu = blob['cx']
        
        distances = []
        for score in range(6):
            x_grad = x_gauche_crop + int(score * largeur_graduation)
            distance = abs(cx_absolu - x_grad)
            distances.append(distance)
        
        score_proche = distances.index(min(distances))
        
        if score_proche not in scores_detectes:
            scores_detectes.append(score_proche)
            print(f"        ✓ Score {score_proche} (x={cx_absolu}, w={blob['w']})")
    
    # === 8. VISUALISATION ===
    vis = cv2.cvtColor(binaire, cv2.COLOR_GRAY2BGR)
    
    # Bande en CYAN
    cv2.rectangle(vis, (0, y_bande_min), (vis.shape[1], y_bande_max), (255, 255, 0), 2)
    
    # Chiffres en JAUNE
    for blob in blobs_chiffres:
        cv2.rectangle(vis, 
                     (blob['x'], y_bande_min + blob['y']), 
                     (blob['x'] + blob['w'], y_bande_min + blob['y'] + blob['h']), 
                     (0, 255, 255), 2)
        cv2.putText(vis, f"{blob['w']}", 
                   (blob['x'], y_bande_min + blob['y'] - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    # Crayonnages en ROUGE
    for blob in blobs_crayonnages:
        cv2.rectangle(vis, 
                     (blob['x'], y_bande_min + blob['y']), 
                     (blob['x'] + blob['w'], y_bande_min + blob['y'] + blob['h']), 
                     (0, 0, 255), 3)
        cv2.putText(vis, f"{blob['w']}", 
                   (blob['x'], y_bande_min + blob['y'] - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    # Scores - gros points rouges
    for score in scores_detectes:
        x_grad = x_gauche_crop + int(score * largeur_graduation)
        cv2.circle(vis, (x_grad, y_echelle_crop), 30, (0, 0, 255), -1)
        cv2.putText(vis, str(score), (x_grad-15, y_echelle_crop+15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    
    if scores_detectes:
        texte = f"Scores: {sorted(scores_detectes)}"
        cv2.putText(vis, texte, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
    
    cv2.putText(vis, f"JAUNE=chiffres(w<={LARGEUR_MAX_CHIFFRE})  ROUGE=crayonnages(w>{LARGEUR_MAX_CHIFFRE})", 
               (10, vis.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    cv2.imwrite(output_path, vis)
    
    return sorted(scores_detectes)

# ============================================================
# DÉTECTION DE COCHAGE
# ============================================================
def analyser_case(image, case):
    """
    Analyse une case cochée vs écriture manuscrite
    """
    x, y, w, h = case['x'], case['y'], case['w'], case['h']
    
    # Marge 25%
    marge_x = int(w * 0.25)
    marge_y = int(h * 0.25)
    
    x_int = x + marge_x
    y_int = y + marge_y
    w_int = w - 2 * marge_x
    h_int = h - 2 * marge_y
    
    roi = image[y_int:y_int+h_int, x_int:x_int+w_int]
    
    _, binaire = cv2.threshold(roi, 180, 255, cv2.THRESH_BINARY_INV)
    
    # === CRITÈRE 1: Remplissage ===
    ratio_noir = np.count_nonzero(binaire) / (w_int * h_int)
    if ratio_noir > SEUIL_REMPLISSAGE:
        return ('noire', ratio_noir)
    
    # === CRITÈRE 2: Composantes SIGNIFICATIVES ===
    nb_composantes, labels, stats, _ = cv2.connectedComponentsWithStats(binaire)
    
    # Taille minimale = 10% de la case (une croix fait au moins ça)
    taille_min = (w_int * h_int) * 0.1
    
    nb_grosses_composantes = 0
    for i in range(1, nb_composantes):
        area = stats[i, cv2.CC_STAT_AREA]
        
        # Composante grosse = croix/coche
        if area > taille_min:
            nb_grosses_composantes += 1
    
    if nb_grosses_composantes >= MIN_COMPOSANTES:
        return ('traits', nb_grosses_composantes)
    
    return ('vide', None)
def Xanalyser_case(image, case):
    """
    Analyse une case pour déterminer si elle est cochée
    
    Returns:
        tuple (type, info):
        - ('vide', None) si vide
        - ('noire', ratio) si trop noire
        - ('traits', nb_comp) si objets détectés
    """
    x, y, w, h = case['x'], case['y'], case['w'], case['h']
    
    # Réduire pour ignorer les bords (marge 25%)
    marge_x = int(w * 0.25)
    marge_y = int(h * 0.25)
    
    x_int = x + marge_x
    y_int = y + marge_y
    w_int = w - 2 * marge_x
    h_int = h - 2 * marge_y
    
    # Extraire l'intérieur
    roi = image[y_int:y_int+h_int, x_int:x_int+w_int]
    
    # Binariser
    _, binaire = cv2.threshold(roi, 180, 255, cv2.THRESH_BINARY_INV)
    
    # === CRITÈRE 1: Remplissage ===
    ratio_noir = np.count_nonzero(binaire) / (w_int * h_int)
    
    if ratio_noir > SEUIL_REMPLISSAGE:
        return ('noire', ratio_noir)
    
    # === CRITÈRE 2: Composantes connexes ===
    nb_composantes, _ = cv2.connectedComponents(binaire)
    nb_objets = nb_composantes - 1  # Ignorer le fond
    
    if nb_objets >= MIN_COMPOSANTES:
        return ('traits', nb_objets)
    
    return ('vide', None)


# ============================================================
# MATCHING
# ============================================================

def trouver_cases_template_manquantes(ligne_vides, cases_template, dx):
    """Trouve les cases du template qui manquent"""
    if not ligne_vides:
        return list(range(len(cases_template)))
    
    indices_manquants = []
    
    for idx, case_tmpl in enumerate(cases_template):
        x_attendu = case_tmpl['x'] + dx
        
        trouve = False
        for case_det in ligne_vides:
            if abs(case_det['x'] - x_attendu) < TOLERANCE_X:
                trouve = True
                break
        
        if not trouve:
            indices_manquants.append(idx)
    
    return indices_manquants


# ============================================================
# VISUALISATION
# ============================================================

def visualiser_cases(image, cases_vides, cases_manquantes, cases_noires, cases_traits, output_path):
    """
    Dessine avec 4 couleurs:
    - VERT = vides
    - ROUGE = manquantes
    - ORANGE = cochées par noirceur
    - BLEU = cochées par traits
    """
    vis = image.copy()
    
    # VERT = vides
    for case in cases_vides:
        overlay = vis.copy()
        cv2.rectangle(overlay,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (0, 255, 0), -1)
        cv2.addWeighted(overlay, 0.3, vis, 0.7, 0, vis)
        
        cv2.rectangle(vis,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (0, 255, 0), 3)
    
    # ROUGE = manquantes
    for case in cases_manquantes:
        overlay = vis.copy()
        cv2.rectangle(overlay,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.3, vis, 0.7, 0, vis)
        
        cv2.rectangle(vis,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (0, 0, 255), 3)
    
    # ORANGE = noires
    for case in cases_noires:
        overlay = vis.copy()
        cv2.rectangle(overlay,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (0, 165, 255), -1)  # BGR: orange
        cv2.addWeighted(overlay, 0.3, vis, 0.7, 0, vis)
        
        cv2.rectangle(vis,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (0, 165, 255), 3)
    
    # BLEU = traits
    for case in cases_traits:
        overlay = vis.copy()
        cv2.rectangle(overlay,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (255, 0, 0), -1)
        cv2.addWeighted(overlay, 0.3, vis, 0.7, 0, vis)
        
        cv2.rectangle(vis,
                     (case['x'], case['y']),
                     (case['x'] + case['w'], case['y'] + case['h']),
                     (255, 0, 0), 3)
    
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    small = cv2.resize(vis, None, fx=0.2, fy=0.2)
    cv2.imwrite(output_path, small)


# ============================================================
# ANALYSE
# ============================================================

def analyser_page(image, page_num, template_page):
    """Analyse avec détection fine du cochage"""
    print(f"  Page {page_num}...")
    
    # ÉCHELLE
    echelle_reponse = detecter_echelle_seule(image)
    echelle_template = template_page.get('echelle')
    
    if not echelle_reponse:
        print(f"    ⚠ Échelle non détectée")
        return {'page': page_num, 'erreur': 'Échelle non détectée'}
    
    dx = calculer_dx(echelle_template, echelle_reponse)
    print(f"    ✓ Décalage dX={dx}")
    

    # === COTER L'ÉCHELLE ===
    scores_echelle = coter_echelle(image, echelle_reponse, f"out/echelle_page{page_num}.png")
    print(f"    ✓ Échelle cotée: {scores_echelle}")

    # DÉTECTER CASES
    cases_detectees = detecter_cases_completes(image)
    print(f"    ✓ {len(cases_detectees)} cases détectées")
    
    # ANALYSER CHAQUE CASE
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    cases_vides = []
    cases_noires = []
    cases_traits = []
    
    for case in cases_detectees:
        type_case, info = analyser_case(gray, case)
        
        if type_case == 'vide':
            cases_vides.append(case)
        elif type_case == 'noire':
            case_avec_info = case.copy()
            case_avec_info['ratio_noir'] = info
            cases_noires.append(case_avec_info)
        elif type_case == 'traits':
            case_avec_info = case.copy()
            case_avec_info['nb_objets'] = info
            cases_traits.append(case_avec_info)
    
    print(f"    ✓ {len(cases_vides)} vides, {len(cases_noires)} noires, {len(cases_traits)} traits")
    
    # GROUPER PAR LIGNES (vides seulement)
    lignes_vides = regrouper_par_lignes(cases_vides)
    
    # ANALYSE PAR QUESTION
    questions_json = {}
    toutes_cases_manquantes = []
    
    nb_questions = min(len(lignes_vides), len(template_page['contenu']))
    
    for num_question in range(1, nb_questions + 1):
        q_id = f"question_{num_question}"
        
        if q_id not in template_page['contenu']:
            continue
        
        ligne_vides = lignes_vides[num_question - 1] if num_question <= len(lignes_vides) else []
        
        if ligne_vides:
            y_ligne = int(sum(c['y'] for c in ligne_vides) / len(ligne_vides))
        else:
            cases_template = template_page['contenu'][q_id]['cases']
            y_ligne = cases_template[0]['y'] if cases_template else 0
        
        cases_template = template_page['contenu'][q_id]['cases']
        
        # Trouver indices manquants (= cochés)
        indices_manquants = trouver_cases_template_manquantes(
            ligne_vides, cases_template, dx
        )
        
        # === CRÉER LISTE ORDONNÉE DES RÉPONSES ===
        reponses_ordonnees = []
        for idx in range(len(cases_template)):
            if idx in indices_manquants:
                # Case cochée
                case_tmpl = cases_template[idx]
                reponses_ordonnees.append({
                    'index': idx,
                    'reponse': 'cochée',
                    'x': case_tmpl['x'] + dx,
                    'y': y_ligne,
                    'w': case_tmpl['w'],
                    'h': case_tmpl['h']
                })
            else:
                # Case vide (trouvée dans ligne_vides)
                # Trouver la case correspondante
                case_vide = None
                for case in ligne_vides:
                    x_attendu = cases_template[idx]['x'] + dx
                    if abs(case['x'] - x_attendu) < TOLERANCE_X:
                        case_vide = case
                        break
                
                if case_vide:
                    reponses_ordonnees.append({
                        'index': idx,
                        'reponse': 'vide',
                        'x': case_vide['x'],
                        'y': case_vide['y'],
                        'w': case_vide['w'],
                        'h': case_vide['h']
                    })
                else:
                    # Normalement ne devrait pas arriver
                    case_tmpl = cases_template[idx]
                    reponses_ordonnees.append({
                        'index': idx,
                        'reponse': 'vide',
                        'x': case_tmpl['x'] + dx,
                        'y': y_ligne,
                        'w': case_tmpl['w'],
                        'h': case_tmpl['h']
                    })
        
        print(f"    Question {num_question}: {len([r for r in reponses_ordonnees if r['reponse']=='vide'])} vides, "
              f"{len([r for r in reponses_ordonnees if r['reponse']=='cochée'])} cochées")
        
        # Pour visualisation : cases manquantes
        cases_manquantes_q = []
        for idx in indices_manquants:
            case_tmpl = cases_template[idx]
            cases_manquantes_q.append({
                'x': case_tmpl['x'] + dx,
                'y': y_ligne,
                'w': case_tmpl['w'],
                'h': case_tmpl['h']
            })
        toutes_cases_manquantes.extend(cases_manquantes_q)
        
        questions_json[q_id] = {
            'reponses': reponses_ordonnees
        }
    
    # VISUALISATION
    visualiser_cases(
        image, cases_vides, toutes_cases_manquantes, cases_noires, cases_traits,
        f"out/reponse_page{page_num}.png"
    )
    print(f"    ✓ Visualisation → out/reponse_page{page_num}.png")
    
    return {
        'page': page_num,
        'decalage_x': dx,        
        'score_echelle': scores_echelle,  # Ajouter ici
        'questions': questions_json
    }
# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) < 4:
        print("\nUsage: python depouiller_reponses.py template.json reponses.pdf output.json\n")
        sys.exit(1)
    
    template_json = sys.argv[1]
    reponses_pdf = sys.argv[2]
    output_json = sys.argv[3]
    
    print(f"\n{'='*60}")
    print(f"DÉPOUILLEMENT")
    print(f"{'='*60}\n")
    
    os.makedirs("out", exist_ok=True)
    
    with open(template_json, 'r', encoding='utf-8') as f:
        template = json.load(f)
    print(f"✓ Template: {len(template['pages'])} page(s)")
    
    template_page = template['pages'][0]
    print(f"✓ Utilisation page 1\n")
    
    pages = convert_from_path(reponses_pdf, dpi=600)
    print(f"✓ {len(pages)} page(s)\n")
    
    resultats = {
        'fichier_template': template_json,
        'fichier_reponses': reponses_pdf,
        'pages': []
    }
    
    for page_num, page_img in enumerate(pages, 1):
        img = cv2.cvtColor(np.array(page_img), cv2.COLOR_RGB2BGR)
        page_data = analyser_page(img, page_num, template_page)
        resultats['pages'].append(page_data)
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ {output_json}")
    print(f"✓ out/")
    print(f"  🟢 VERT   = Vides")
    print(f"  🔴 ROUGE  = Manquantes")
    print(f"  🟠 ORANGE = Cochées (noires)")
    print(f"  🔵 BLEU   = Cochées (traits)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()