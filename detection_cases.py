#!/usr/bin/env python3
"""
Module de détection des cases à cocher dans les questionnaires
"""
import cv2
import numpy as np


def detecter_cases(image, aire_min=1000, aire_max=2500, ratio_min=0.85, ratio_max=1.4):
    """
    Détecte toutes les cases à cocher dans une image
    
    Args:
        image: Image OpenCV (BGR ou grayscale)
        aire_min: Aire minimale en pixels²
        aire_max: Aire maximale en pixels²
        ratio_min: Ratio largeur/hauteur minimum
        ratio_max: Ratio largeur/hauteur maximum
    
    Returns:
        Liste de dicts avec clés: x, y, w, h, aire, ratio
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    cases = []
    
    for cnt in contours:
        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(cnt)
            aire = cv2.contourArea(cnt)
            ratio = w / h if h > 0 else 0
            
            if aire_min <= aire <= aire_max and ratio_min <= ratio <= ratio_max:
                cases.append({
                    'x': int(x),
                    'y': int(y),
                    'w': int(w),
                    'h': int(h),
                    'aire': int(aire),
                    'ratio': round(ratio, 2)
                })
    
    return cases


def dedupliquer_cases(cases, distance_min=10):
    """
    Élimine les doublons (cases à moins de distance_min pixels)
    Garde la case avec la plus grande aire en cas de doublon
    
    Args:
        cases: Liste de cases détectées
        distance_min: Distance minimale entre centres (pixels)
    
    Returns:
        Liste de cases uniques
    """
    if not cases:
        return []
    
    # Trier par aire décroissante (garder les plus grandes)
    cases_triees = sorted(cases, key=lambda c: c['aire'], reverse=True)
    
    cases_uniques = []
    
    for case in cases_triees:
        est_doublon = False
        
        for case_unique in cases_uniques:
            # Distance entre centres
            cx1 = case['x'] + case['w'] / 2
            cy1 = case['y'] + case['h'] / 2
            cx2 = case_unique['x'] + case_unique['w'] / 2
            cy2 = case_unique['y'] + case_unique['h'] / 2
            
            distance = ((cx1 - cx2)**2 + (cy1 - cy2)**2)**0.5
            
            if distance < distance_min:
                est_doublon = True
                break
        
        if not est_doublon:
            cases_uniques.append(case)
    
    return cases_uniques


def regrouper_par_lignes(cases, tolerance_y=50):
    """
    Regroupe les cases par ligne horizontale (même Y)
    
    Args:
        cases: Liste de cases
        tolerance_y: Tolérance verticale en pixels
    
    Returns:
        Liste de listes (chaque sous-liste = une ligne)
    """
    if not cases:
        return []
    
    # Trier par Y puis X
    cases_triees = sorted(cases, key=lambda c: (c['y'], c['x']))
    
    lignes = []
    ligne_courante = [cases_triees[0]]
    y_reference = cases_triees[0]['y']
    
    for case in cases_triees[1:]:
        if abs(case['y'] - y_reference) <= tolerance_y:
            ligne_courante.append(case)
        else:
            # Trier la ligne par X
            ligne_courante = sorted(ligne_courante, key=lambda c: c['x'])
            lignes.append(ligne_courante)
            ligne_courante = [case]
            y_reference = case['y']
    
    # Dernière ligne
    if ligne_courante:
        ligne_courante = sorted(ligne_courante, key=lambda c: c['x'])
        lignes.append(ligne_courante)
    
    return lignes


def detecter_cases_completes(image):
    """
    Pipeline complet: détection + déduplication + tri
    
    Args:
        image: Image OpenCV
    
    Returns:
        Liste de cases uniques triées par ordre naturel (haut→bas, gauche→droite)
    """
    cases_brutes = detecter_cases(image)
    cases_uniques = dedupliquer_cases(cases_brutes)
    cases_triees = sorted(cases_uniques, key=lambda c: (c['y'], c['x']))
    return cases_triees