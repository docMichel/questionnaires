# Application Questionnaire PRISMES

## Installation rapide

```bash
tar -xzf questionnaire.tar.gz
cd questionnaire
./install.sh
```

## Fichiers à ajouter
- **detect0.py** (votre script de détection)
- **template.json** (votre template)

## Lancement
```bash
cd ~/Sites/questionnaire
./run.sh
```

## Accès
- http://localhost:8080

## Structure
```
~/Sites/questionnaire/
├── app.py                 # Application Flask
├── detect0.py            # (à copier)
├── template.json         # (à copier)
├── fusionner_resultats.py
├── json2excel.py
├── uploads/              # PDFs uploadés
├── results/              # Résultats
└── history.json          # Historique
```
