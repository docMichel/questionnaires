#!/bin/bash
# Lancer l'application questionnaire

echo "🚀 Démarrage de l'application Questionnaire..."

# Se placer dans le bon répertoire  
cd "$(dirname "$0")"

# Vérifier les dépendances
echo "📦 Vérification des dépendances..."
pip3 install -q flask werkzeug openpyxl

# Créer les dossiers
mkdir -p uploads results

# Vérifier les fichiers nécessaires
if [ ! -f "detect0.py" ]; then
    echo "⚠️  detect0.py manquant!"
fi
if [ ! -f "template.json" ]; then
    echo "⚠️  template.json manquant!"
fi

# Lancer Flask
echo "✅ Application disponible sur http://localhost:8080"
echo "📍 Ou via Apache sur http://localhost/~$USER/questionnaire"
echo ""
echo "Ctrl+C pour arrêter"
echo ""

python3 app.py
