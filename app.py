#!/usr/bin/env python3
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Chemins relatifs
BASE_DIR = Path(__file__).parent
app.config['UPLOAD_FOLDER'] = BASE_DIR / 'uploads'
app.config['RESULTS_FOLDER'] = BASE_DIR / 'results'
HISTORY_FILE = BASE_DIR / 'history.json'

# Créer les dossiers
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
app.config['RESULTS_FOLDER'].mkdir(exist_ok=True)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Questionnaires PRISMES</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 50px auto; padding: 20px; }
        .upload-box { border: 2px dashed #999; padding: 40px; text-align: center; margin: 20px 0; background: #f9f9f9; }
        .btn { background: #007aff; color: white; border: none; padding: 12px 30px; border-radius: 6px; cursor: pointer; }
        .btn:disabled { background: #ccc; }
        .results { margin: 30px 0; padding: 20px; background: #e8f5e9; border-radius: 8px; display: none; }
        .results a { display: inline-block; margin: 10px; padding: 10px 20px; background: white; text-decoration: none; border-radius: 4px; }
        .history-item { padding: 10px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; }
        .status { margin: 20px 0; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>📋 Traitement Questionnaires</h1>
    
    <div class="upload-box">
        <input type="file" id="pdfFile" accept=".pdf">
        <br><br>
        <button class="btn" onclick="uploadPDF()">Traiter le PDF</button>
    </div>
    
    <div class="status" id="status"></div>
    <div class="results" id="results"></div>
    
    <div style="margin-top:40px">
        <h3>Historique</h3>
        <div id="historyList"></div>
    </div>

    <script>
        async function uploadPDF() {
            const fileInput = document.getElementById('pdfFile');
            const file = fileInput.files[0];
            if (!file) { alert('Sélectionnez un PDF'); return; }
            
            const status = document.getElementById('status');
            const button = document.querySelector('.btn');
            
            status.innerHTML = '⏳ Traitement en cours...';
            button.disabled = true;
            
            const formData = new FormData();
            formData.append('pdf', file);
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (data.success) {
                    status.innerHTML = '✅ Terminé!';
                    document.getElementById('results').innerHTML = 
                        '<h3>Résultats</h3>' +
                        '<a href="/download/' + data.json + '">📄 JSON</a>' +
                        '<a href="/download/' + data.excel + '">📊 Excel</a>';
                    document.getElementById('results').style.display = 'block';
                    loadHistory();
                } else {
                    status.innerHTML = '<span class="error">❌ ' + data.error + '</span>';
                }
            } catch (error) {
                status.innerHTML = '<span class="error">❌ Erreur: ' + error + '</span>';
            }
            button.disabled = false;
        }
        
        async function loadHistory() {
            const response = await fetch('/history');
            const history = await response.json();
            const list = document.getElementById('historyList');
            
            list.innerHTML = history.slice(-5).reverse().map(item => 
                '<div class="history-item">' +
                '<strong>' + item.filename + '</strong> - ' + new Date(item.date).toLocaleString('fr-FR') +
                '<br><a href="/download/' + item.json + '">JSON</a> | ' +
                '<a href="/download/' + item.excel + '">Excel</a></div>'
            ).join('');
        }
        loadHistory();
    </script>
</body>
</html>
'''

def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return []

def save_history(history):
    HISTORY_FILE.write_text(json.dumps(history, indent=2, default=str))

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('pdf')
    if not file:
        return jsonify({'error': 'Pas de fichier'}), 400
    
    # Sauver PDF
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = secure_filename(file.filename)
    base_name = Path(filename).stem
    
    pdf_path = app.config['UPLOAD_FOLDER'] / f"{timestamp}_{filename}"
    file.save(pdf_path)
    
    # Fichiers de sortie
    result_base = app.config['RESULTS_FOLDER'] / f"{timestamp}_{base_name}"
    json_result = f"{result_base}_resultats.json"
    json_fusion = f"{result_base}_fusion.json"  
    excel_result = f"{result_base}.xlsx"
    
    try:
        # Pipeline
        subprocess.run(['python3', 'detect0.py', 'template.json' , str(pdf_path),json_result], 
                      check=True, cwd=BASE_DIR, capture_output=True)
        subprocess.run(['python3', 'fusionner_resultats.py', 'template.json', json_result, json_fusion], 
                      check=True, cwd=BASE_DIR, capture_output=True)
        subprocess.run(['python3', 'json2excel.py', json_fusion, excel_result], 
                      check=True, cwd=BASE_DIR, capture_output=True)
        
        # Historique
        history = load_history()
        history.append({
            'timestamp': timestamp,
            'filename': filename,
            'json': Path(json_fusion).name,
            'excel': Path(excel_result).name,
            'date': datetime.now().isoformat()
        })
        save_history(history)
        
        return jsonify({
            'success': True,
            'json': Path(json_fusion).name,
            'excel': Path(excel_result).name.replace('.xlsx', '.bin')  # URL avec .bin        })
        
    except subprocess.CalledProcessError as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>')
def download(filename):
    # Accepter .bin mais servir le vrai fichier
    real_filename = filename.replace('.bin', '.xlsx').replace('.dat', '.xls')
    filepath = app.config['RESULTS_FOLDER'] / real_filename
    
    if filepath.exists():
        # Servir avec le BON nom pour l'utilisateur
        return send_file(
            str(filepath), 
            as_attachment=True,
            download_name=real_filename  # Le fichier sera bien .xlsx
        )
    return "Non trouvé", 404

@app.route('/history')
def history():
    return jsonify(load_history())

if __name__ == '__main__':
    app.run(port=8080, host='0.0.0.0')
