#!/usr/bin/env python3
"""
Module de repérage des questionnaires PRISMES
==============================================
Détecte 6 points de repère sur les questionnaires:
- 2 points sur la ligne d'échelle (bords gauche/droite)
- 2 points sur le haut du rectangle gris (bords gauche/droite)
- 2 points sur le bas du rectangle gris (bords gauche/droite)

Ces 6 points permettent un recalage précis des questionnaires remplis
sur les templates vierges pour le dépouillement automatique.
"""
import cv2
import numpy as np

# ============================================================
# PARAMÈTRES DE NETTOYAGE DES LIGNES VERTICALES
# ============================================================
# Ces paramètres permettent de supprimer les lignes verticales
# de scan/découpe qui perturbent la détection de la ligne d'échelle

# Morphologie: pour les lignes fines et continues
MORPH_LARGEUR_MAX = 2      # Largeur max d'une ligne à supprimer (pixels)
MORPH_HAUTEUR_MIN = 100    # Hauteur min pour être considérée comme ligne (pixels)

# Hough: pour les lignes longues, même si pointillées
HOUGH_ENABLE = True             # Activer/désactiver la détection Hough
HOUGH_THRESHOLD = 50            # Seuil de votes Hough (sensibilité)
HOUGH_MIN_LENGTH = 500          # Longueur minimale d'une ligne (pixels)
HOUGH_MAX_GAP = 100             # Gap max entre segments pour les reconnecter (pixels)
HOUGH_ANGLE_MIN = 85            # Angle min pour considérer comme verticale (degrés)
HOUGH_ANGLE_MAX = 95            # Angle max pour considérer comme verticale (degrés)
HOUGH_EPAISSEUR_SUP = 10        # Pixels à supprimer de chaque côté de la ligne


def nettoyer_image_base(image):
    """
    Nettoyage de base: supprime les lignes parasites fines du scan
    
    Cette fonction est utilisée pour le rectangle gris car elle ne touche
    pas aux bords de l'image (où se trouve le rectangle).
    
    Processus:
    1. Binarisation de l'image
    2. Détection lignes horizontales fines (h≤2px, w≥100px) → suppression
    3. Détection lignes verticales fines (w≤2px, h≥100px) → suppression
    
    Args:
        image: Image BGR ou grayscale
    
    Returns:
        Image nettoyée (BGR, 3 canaux)
    """
    # Conversion en niveaux de gris si nécessaire
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    
    # Binarisation automatique (Otsu trouve le meilleur seuil)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Inverser si nécessaire (on veut le texte en blanc)
    if np.mean(binary) > 127:
        binary = cv2.bitwise_not(binary)
    
    result = binary.copy()
    
    # === SUPPRESSION LIGNES HORIZONTALES FINES ===
    # Créer un élément structurant: ligne horizontale de 100x1
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (100, 1))
    # MORPH_OPEN détecte les structures qui "rentrent" dans le kernel
    detected_h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
    # Trouver les contours de ces lignes
    contours_h, _ = cv2.findContours(detected_h, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Supprimer les lignes horizontales fines
    for cnt in contours_h:
        x, y, w, h = cv2.boundingRect(cnt)
        if h <= 2 and w >= 100:  # Fine (≤2px) et longue (≥100px)
            cv2.rectangle(result, (x, y), (x+w, y+h), 0, -1)  # Remplir en noir
    
    # === SUPPRESSION LIGNES VERTICALES FINES ===
    # Créer un élément structurant: ligne verticale de 1x100
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 100))
    detected_v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)
    contours_v, _ = cv2.findContours(detected_v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Supprimer les lignes verticales fines
    for cnt in contours_v:
        x, y, w, h = cv2.boundingRect(cnt)
        if w <= 2 and h >= 100:  # Fine (≤2px) et longue (≥100px)
            cv2.rectangle(result, (x, y), (x+w, y+h), 0, -1)
    
    # Inverser et convertir en BGR pour uniformité
    image_nettoyee = cv2.bitwise_not(result)
    return cv2.cvtColor(image_nettoyee, cv2.COLOR_GRAY2BGR)


def nettoyer_lignes_verticales_agressif(image):
    """
    Nettoyage agressif: supprime TOUTES les lignes verticales longues
    
    Cette fonction est utilisée UNIQUEMENT pour détecter la ligne d'échelle,
    car elle supprime aussi les lignes de scan sur les bords.
    
    ATTENTION: Ne PAS utiliser pour le rectangle gris (ça couperait ses bords!)
    
    Utilise 2 méthodes complémentaires:
    1. Morphologie: lignes continues fines
    2. Hough: lignes longues, même si pointillées/discontinues
    
    Args:
        image: Image BGR ou grayscale
    
    Returns:
        Image nettoyée (BGR, 3 canaux)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.mean(binary) > 127:
        binary = cv2.bitwise_not(binary)
    
    result = binary.copy()
    
    # === MÉTHODE 1: MORPHOLOGIE (même logique que nettoyer_image_base) ===
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (100, 1))
    detected_h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
    contours_h, _ = cv2.findContours(detected_h, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_h:
        x, y, w, h = cv2.boundingRect(cnt)
        if h <= 2 and w >= 100:
            cv2.rectangle(result, (x, y), (x+w, y+h), 0, -1)
    
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, MORPH_HAUTEUR_MIN))
    detected_v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)
    contours_v, _ = cv2.findContours(detected_v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_v:
        x, y, w, h = cv2.boundingRect(cnt)
        if w <= MORPH_LARGEUR_MAX and h >= MORPH_HAUTEUR_MIN:
            cv2.rectangle(result, (x, y), (x+w, y+h), 0, -1)
    
    # === MÉTHODE 2: HOUGH (détecte lignes pointillées que morpho rate) ===
    if HOUGH_ENABLE:
        # Canny: détection de contours (préparation pour Hough)
        edges = cv2.Canny(binary, 50, 150)
        
        # HoughLinesP: détection de segments de lignes
        # - rho=1: résolution distance (pixels)
        # - theta=π/180: résolution angle (1 degré)
        # - threshold: nb min de votes pour accepter une ligne
        # - minLineLength: longueur min d'un segment
        # - maxLineGap: distance max pour relier 2 segments
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 
                               threshold=HOUGH_THRESHOLD,
                               minLineLength=HOUGH_MIN_LENGTH,
                               maxLineGap=HOUGH_MAX_GAP)
        
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                
                # Calculer l'angle de la ligne
                if x2 != x1:
                    angle = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
                else:
                    angle = 90  # Ligne parfaitement verticale
                
                # Vérifier si ligne quasi-verticale (85-95°)
                if HOUGH_ANGLE_MIN <= angle <= HOUGH_ANGLE_MAX:
                    longueur = abs(y2 - y1)
                    
                    # Vérifier si ligne assez longue
                    if longueur >= HOUGH_MIN_LENGTH:
                        # Supprimer une bande autour de la ligne
                        # (±HOUGH_EPAISSEUR_SUP pixels de part et d'autre)
                        x_moy = (x1 + x2) // 2
                        cv2.rectangle(result, 
                                    (x_moy - HOUGH_EPAISSEUR_SUP, min(y1, y2)),
                                    (x_moy + HOUGH_EPAISSEUR_SUP, max(y1, y2)),
                                    0, -1)
    
    image_nettoyee = cv2.bitwise_not(result)
    return cv2.cvtColor(image_nettoyee, cv2.COLOR_GRAY2BGR)


def trouver_ligne_echelle(image):
    """
    Trouve la ligne d'échelle de notation (la plus longue ligne horizontale)
    
    L'échelle de notation (0 nul ; 5 excellent) est matérialisée par une ligne
    horizontale continue qui est la plus longue de toute la page.
    
    Méthode:
    - Balayer ligne par ligne (chaque Y)
    - Pour chaque ligne: projeter verticalement (somme par colonne)
    - Trouver le segment horizontal continu le plus long
    - Retourner la ligne avec le segment le plus long de toute la page
    
    Args:
        image: Image nettoyée (BGR, sortie de nettoyer_lignes_verticales_agressif)
    
    Returns:
        tuple (x1, y, x2, y) ou None si pas trouvé
        - x1: début de la ligne (pixel X)
        - y: hauteur de la ligne (pixel Y)
        - x2: fin de la ligne (pixel X)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    # Binariser: texte en blanc (255), fond en noir (0)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    h, w = binary.shape
    
    best = None      # Meilleure ligne trouvée
    max_len = 0      # Longueur de la meilleure ligne
    
    # Balayer toutes les lignes de l'image
    for y in range(h):
        # Extraire bande de ±5 pixels autour de y
        # (pour être plus robuste aux petites variations)
        bande = binary[max(0, y-5):min(h, y+5), :]
        
        # Projection verticale: True si au moins 1 pixel blanc dans la colonne
        proj = np.sum(bande, axis=0) > 0
        
        # Chercher le segment horizontal continu le plus long sur cette ligne
        debut = None
        max_seg = 0      # Longueur max du segment sur cette ligne
        x1_max = 0       # Position X du début du segment max
        
        for x in range(w):
            if proj[x]:  # Pixel blanc (contenu)
                if debut is None:
                    debut = x  # Début d'un nouveau segment
            else:  # Pixel noir (pas de contenu)
                if debut is not None:
                    # Fin d'un segment: calculer sa longueur
                    longueur = x - debut
                    if longueur > max_seg:
                        max_seg = longueur
                        x1_max = debut
                debut = None
        
        # Si le segment va jusqu'au bord droit
        if debut is not None:
            longueur = w - debut
            if longueur > max_seg:
                x1_max = debut
                max_seg = longueur
        
        # Comparer avec la meilleure ligne trouvée jusqu'ici
        if max_seg > max_len:
            max_len = max_seg
            best = (x1_max, y, x1_max + max_seg, y)
    
    return best


def trouver_bords_ligne_echelle(image, y_ligne, hauteur_bande=40):
    """
    Trouve les bords gauche et droite de la ligne d'échelle
    
    Une fois la ligne d'échelle localisée en Y, on cherche précisément
    où elle commence (X gauche) et où elle finit (X droite).
    
    Méthode:
    - Extraire bande horizontale autour de y_ligne
    - Projeter verticalement (densité de pixels par colonne)
    - Chercher début/fin du contenu en testant des fenêtres glissantes
    
    Args:
        image: Image nettoyée
        y_ligne: Position Y de la ligne d'échelle
        hauteur_bande: Hauteur de la bande à analyser (pixels)
    
    Returns:
        tuple (x_gauche, x_droite) ou None si échec
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    
    # Extraire bande horizontale autour de y_ligne
    y_min = max(0, y_ligne - hauteur_bande//2)
    y_max = min(gray.shape[0], y_ligne + hauteur_bande//2)
    bande = gray[y_min:y_max, :]
    
    # Binariser la bande (texte en blanc)
    _, binary = cv2.threshold(bande, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Projection verticale: somme des pixels blancs par colonne
    projection = np.sum(binary, axis=0)
    
    # Normaliser entre 0 et 1
    if projection.max() > 0:
        projection = projection / projection.max()
    
    # Paramètres de détection
    seuil = 0.15          # Seuil de densité pour considérer qu'il y a du contenu
    largeur_min = 20      # Taille fenêtre glissante (robustesse)
    
    # === CHERCHER BORD GAUCHE ===
    # On teste des fenêtres de largeur_min pixels depuis la gauche
    x_gauche = None
    for x in range(len(projection) - largeur_min):
        # Calculer densité moyenne sur la fenêtre
        if np.mean(projection[x:x+largeur_min]) > seuil:
            x_gauche = x
            break
    
    # === CHERCHER BORD DROIT ===
    # On teste des fenêtres de largeur_min pixels depuis la droite
    x_droite = None
    for x in range(len(projection)-1, largeur_min, -1):
        # Calculer densité moyenne sur la fenêtre
        if np.mean(projection[x-largeur_min:x]) > seuil:
            x_droite = x
            break
    
    return (x_gauche, x_droite) if x_gauche and x_droite else None


def trouver_rectangle_gris(image):
    """
    Trouve le rectangle gris en bas de page (zone de commentaires)
    
    Le rectangle gris est un fond grisé qui contient les questions à cocher.
    On le détecte par analyse d'intensité lumineuse dans le bas de la page.
    
    Méthode:
    - Analyser seulement moitié basse + tiers droit (zone typique du rectangle)
    - Calculer intensité moyenne par ligne
    - Trouver la plus longue séquence de lignes "sombres"
    
    Args:
        image: Image nettoyée (nettoyage BASE, pas agressif!)
    
    Returns:
        tuple (x, y_haut, largeur, hauteur) ou None si pas trouvé
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    h, w = gray.shape
    
    # Analyser seulement moitié basse + tiers droit
    # (le rectangle gris est toujours dans cette zone)
    moitie_basse_y = int(h * 0.5)
    tiers_droit_x = int(w * 2/3)
    
    zone = gray[moitie_basse_y:, tiers_droit_x:]
    
    # Normaliser les intensités entre 0 et 255
    zone_norm = cv2.normalize(zone, None, 0, 255, cv2.NORM_MINMAX)
    
    # Calculer intensité moyenne par ligne
    intensites = np.mean(zone_norm, axis=1)
    
    # Calculer seuil: entre médiane et blanc
    # (le gris est plus sombre que le fond blanc mais plus clair que le texte)
    mediane = np.median(intensites)
    seuil = (mediane + 255) / 2
    
    # === CHERCHER LA PLUS LONGUE ZONE SOMBRE ===
    dans_zone = False
    y_debut = None
    longueur_max = 0
    meilleur_debut = None
    meilleur_fin = None
    
    for y, intensite in enumerate(intensites):
        if intensite < seuil:  # Ligne sombre (dans le rectangle)
            if not dans_zone:
                y_debut = y
                dans_zone = True
        else:  # Ligne claire (hors rectangle)
            if dans_zone:
                longueur = y - y_debut
                if longueur > longueur_max:
                    longueur_max = longueur
                    meilleur_debut = y_debut
                    meilleur_fin = y
                dans_zone = False
    
    # Si la zone va jusqu'en bas de page
    if dans_zone:
        longueur = len(intensites) - y_debut
        if longueur > longueur_max:
            meilleur_debut = y_debut
            meilleur_fin = len(intensites)
    
    # Vérifier qu'on a trouvé quelque chose d'assez grand
    if meilleur_debut is None or longueur_max < 200:
        return None
    
    # Reconvertir les coordonnées relatives en coordonnées absolues
    y_haut = meilleur_debut + moitie_basse_y
    h_rect = meilleur_fin - meilleur_debut
    
    # Retourner rectangle sur toute la largeur
    return (0, y_haut, w, h_rect)


def trouver_bords_verticaux_rectangle(image, rect):
    """
    Trouve les bords gauche et droite du rectangle gris
    
    Une fois le rectangle localisé verticalement (Y haut/bas), on cherche
    précisément ses bords latéraux (X gauche/droite).
    
    Méthode:
    - Analyser une bande horizontale au milieu du rectangle
    - Projeter horizontalement (intensité moyenne par colonne)
    - Chercher les transitions blanc→gris (bord gauche) et gris→blanc (bord droit)
    
    Args:
        image: Image nettoyée
        rect: tuple (x, y_haut, w, h_rect) du rectangle
    
    Returns:
        tuple (x_gauche, x_droite) ou None si échec
    """
    if rect is None:
        return None
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    x, y_haut, w, h_rect = rect
    
    # Analyser une bande au milieu du rectangle (1/4 de sa hauteur)
    y_mid = y_haut + h_rect // 2
    band_h = h_rect // 4
    bande = gray[y_mid - band_h//2:y_mid + band_h//2, :]
    
    # Normaliser
    bande_norm = cv2.normalize(bande, None, 0, 255, cv2.NORM_MINMAX)
    
    # Projection horizontale: intensité moyenne par colonne
    projection = np.mean(bande_norm, axis=0)
    
    # Seuil: entre médiane et blanc
    mediane = np.median(projection)
    seuil = (mediane + 255) / 2
    
    # Largeur minimum de zone grise continue pour être sûr
    min_gris = 200
    
    # === CHERCHER BORD GAUCHE ===
    # On teste des fenêtres de min_gris pixels depuis la gauche
    x_gauche = None
    for x in range(len(projection) - min_gris):
        if projection[x] < seuil:  # Début zone sombre
            # Vérifier que c'est bien une zone continue de gris
            if np.sum(projection[x:x+min_gris] < seuil) / min_gris > 0.8:
                x_gauche = x
                break
    
    # === CHERCHER BORD DROIT ===
    # On teste des fenêtres de min_gris pixels depuis la droite
    x_droite = None
    for x in range(len(projection)-1, min_gris, -1):
        if projection[x] < seuil:  # Encore dans zone sombre
            # Vérifier que c'est bien une zone continue de gris
            if np.sum(projection[x-min_gris:x] < seuil) / min_gris > 0.8:
                x_droite = x
                break
    
    return (x_gauche, x_droite) if x_gauche and x_droite else None


def detecter_reperes(image):
    """
    FONCTION PRINCIPALE: Détecte les 6 points de repère sur un questionnaire
    
    Stratégie:
    1. Nettoyer l'image (2 nettoyages: base + agressif)
    2. Trouver ligne d'échelle (Y) puis ses bords (X gauche/droite) → 2 points
    3. Trouver rectangle gris (Y haut/bas) puis ses bords (X gauche/droite) → 4 points
    
    IMPORTANT:
    - Utilise nettoyage AGRESSIF pour ligne échelle (supprime bords)
    - Utilise nettoyage BASE pour rectangle (garde les bords)
    
    Args:
        image: Image du questionnaire (BGR, 600 DPI)
    
    Returns:
        dict avec les 6 points et infos complémentaires, ou None si échec
        {
            'echelle_gauche': (x, y),
            'echelle_droite': (x, y),
            'rect_haut_gauche': (x, y),
            'rect_haut_droite': (x, y),
            'rect_bas_gauche': (x, y),
            'rect_bas_droite': (x, y),
            ... infos debug ...
        }
    """
    # === NETTOYAGE ===
    # Nettoyage BASE (pour rectangle gris)
    clean = nettoyer_image_base(image)
    
    # Nettoyage AGRESSIF (pour ligne échelle)
    # Supprime toutes les lignes verticales y compris sur les bords
    clean_echelle = nettoyer_lignes_verticales_agressif(image)
    
    # === LIGNE D'ÉCHELLE ===
    # Trouver la ligne d'échelle (avec nettoyage agressif)
    ligne_echelle = trouver_ligne_echelle(clean_echelle)
    if not ligne_echelle:
        return None  # Échec: pas de ligne d'échelle détectée
    
    y_echelle = ligne_echelle[1]  # Position Y de la ligne
    
    # Trouver les bords gauche/droite de la ligne d'échelle
    bords_echelle = trouver_bords_ligne_echelle(clean_echelle, y_echelle)
    if not bords_echelle:
        return None  # Échec: bords non détectés
    
    x_g_echelle, x_d_echelle = bords_echelle
    
    # === RECTANGLE GRIS ===
    # Trouver le rectangle gris (avec nettoyage normal, pas agressif!)
    rect_gris = trouver_rectangle_gris(clean)
    if not rect_gris:
        return None  # Échec: rectangle non détecté
    
    # Trouver les bords gauche/droite du rectangle
    bords_rect = trouver_bords_verticaux_rectangle(clean, rect_gris)
    if not bords_rect:
        return None  # Échec: bords du rectangle non détectés
    
    x_g_rect, x_d_rect = bords_rect
    y_rect_haut = rect_gris[1]           # Y du haut du rectangle
    y_rect_bas = rect_gris[1] + rect_gris[3]  # Y du bas du rectangle
    
    # === RETOURNER LES 6 POINTS ===
    return {
        # LES 6 POINTS DE REPÈRE (pour transformation)
        'echelle_gauche': (x_g_echelle, y_echelle),      # Point haut gauche
        'echelle_droite': (x_d_echelle, y_echelle),      # Point haut droit
        'rect_haut_gauche': (x_g_rect, y_rect_haut),     # Point milieu gauche
        'rect_haut_droite': (x_d_rect, y_rect_haut),     # Point milieu droit
        'rect_bas_gauche': (x_g_rect, y_rect_bas),       # Point bas gauche
        'rect_bas_droite': (x_d_rect, y_rect_bas),       # Point bas droit
        
        # INFOS COMPLÉMENTAIRES (pour debug/classification)
        'ligne_echelle_y': y_echelle,
        'echelle_x_gauche': x_g_echelle,
        'echelle_x_droite': x_d_echelle,
        'rect_y_haut': y_rect_haut,
        'rect_y_bas': y_rect_bas,
        'rect_x_gauche': x_g_rect,
        'rect_x_droite': x_d_rect
    }