#!/bin/bash
# Installation dans ~/Sites/questionnaire

echo "📦 Installation dans ~/Sites/questionnaire..."

# Déterminer le répertoire cible
TARGET_DIR="$HOME/Sites/questionnaire"

# Créer le répertoire
mkdir -p "$TARGET_DIR"

# Copier les fichiers
echo "📂 Copie des fichiers..."
cp app.py "$TARGET_DIR/"
cp fusionner_resultats.py "$TARGET_DIR/"
cp json2excel.py "$TARGET_DIR/"
cp run.sh "$TARGET_DIR/"
chmod +x "$TARGET_DIR/run.sh"

# Copier detect0.py et template.json s'ils existent
if [ -f "detect0.py" ]; then
    cp detect0.py "$TARGET_DIR/"
else
    echo "⚠️  detect0.py non trouvé - à copier manuellement"
fi

if [ -f "template.json" ]; then
    cp template.json "$TARGET_DIR/"
else
    echo "⚠️  template.json non trouvé - à copier manuellement"
fi

# Créer les dossiers
mkdir -p "$TARGET_DIR/uploads" "$TARGET_DIR/results"

# Créer un fichier .htaccess pour Apache
cat > "$TARGET_DIR/.htaccess" << 'EOF'
Options +ExecCGI
AddHandler cgi-script .py

# Proxy vers Flask si en cours d'exécution
RewriteEngine On
RewriteCond %{REQUEST_URI} !^/~[^/]+/questionnaire/uploads/
RewriteCond %{REQUEST_URI} !^/~[^/]+/questionnaire/results/
RewriteRule ^(.*)$ http://localhost:8080/$1 [P,L]
EOF

echo ""
echo "✅ Installation terminée!"
echo ""
echo "📍 Pour lancer l'application:"
echo "   cd ~/Sites/questionnaire"
echo "   ./run.sh"
echo ""
echo "📱 Accès:"
echo "   - Direct Flask: http://localhost:8080"
echo "   - Via Apache: http://localhost/~$USER/questionnaire"
echo ""
echo "⚠️  N'oubliez pas de copier:"
echo "   - detect0.py"
echo "   - template.json"
