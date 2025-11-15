#!/usr/bin/env python3
"""
Fusionne template et résultats
Usage: python fusionner_resultats.py template.json resultats.json output.json
"""
import json
import sys


def fusionner_resultats(template_json, resultats_json):
    """
    Fusionne template (titres) et résultats (cochée/vide)
    
    Returns:
        dict avec titres + états cochés + score globale
    """
    # Charger les fichiers
    with open(template_json, 'r', encoding='utf-8') as f:
        template = json.load(f)
    
    with open(resultats_json, 'r', encoding='utf-8') as f:
        resultats = json.load(f)
    
    # Structure finale
    output = {
        'fichier_template': resultats['fichier_template'],
        'fichier_reponses': resultats['fichier_reponses'],
        'pages': []
    }
    
    # Pour chaque page
    for page_result in resultats['pages']:
        page_num = page_result['page']
        
        # Trouver la page correspondante dans le template (toujours page 1)
        template_page = template['pages'][0]
        
        # === CALCULER SCORE GLOBALE (moyenne de score_echelle) ===
        score_echelle = page_result.get('score_echelle', [])
        if score_echelle:
            globale = sum(score_echelle) / len(score_echelle)
        else:
            globale = None
        
        page_output = {
            'page': page_num,
            'globale': globale,  # <-- NOUVELLE CLÉ
            'questions': {}
        }
        
        # Pour chaque question
        for q_id, q_result in page_result.get('questions', {}).items():
            
            # Récupérer les infos du template
            if q_id in template_page['contenu']:
                template_question = template_page['contenu'][q_id]
                
                question_output = {
                    'titre': template_question.get('titre', ''),
                    'reponses': []
                }
                
                # Pour chaque réponse
                for reponse in q_result.get('reponses', []):
                    idx = reponse['index']
                    
                    # Récupérer le titre de la case dans le template
                    if idx < len(template_question['cases']):
                        case_template = template_question['cases'][idx]
                        titre_case = case_template.get('titre', f'Option {idx+1}')
                    else:
                        titre_case = f'Option {idx+1}'
                    
                    # Convertir cochée/vide en 1/0
                    cochee = 1 if reponse['reponse'] == 'cochée' else 0
                    
                    question_output['reponses'].append({
                        'titre': titre_case,
                        'cochee': cochee
                    })
                
                page_output['questions'][q_id] = question_output
        
        output['pages'].append(page_output)
    
    return output


def main():
    if len(sys.argv) < 4:
        print("\nUsage: python fusionner_resultats.py template.json resultats.json output.json\n")
        sys.exit(1)
    
    template_json = sys.argv[1]
    resultats_json = sys.argv[2]
    output_json = sys.argv[3]
    
    print(f"\n{'='*60}")
    print(f"FUSION TEMPLATE + RÉSULTATS")
    print(f"{'='*60}\n")
    
    # Fusionner
    output = fusionner_resultats(template_json, resultats_json)
    
    # Sauver
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Template: {template_json}")
    print(f"✓ Résultats: {resultats_json}")
    print(f"✓ Fusion → {output_json}\n")
    
    # Stats
    total_questions = sum(len(p['questions']) for p in output['pages'])
    total_cochees = sum(
        sum(r['cochee'] for r in q['reponses'])
        for p in output['pages']
        for q in p['questions'].values()
    )
    
    # Stats scores globales
    scores_globales = [p['globale'] for p in output['pages'] if p['globale'] is not None]
    
    print(f"  {len(output['pages'])} pages")
    print(f"  {total_questions} questions")
    print(f"  {total_cochees} cases cochées")
    
    if scores_globales:
        print(f"  Scores globales: min={min(scores_globales):.1f}, max={max(scores_globales):.1f}, moy={sum(scores_globales)/len(scores_globales):.1f}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()