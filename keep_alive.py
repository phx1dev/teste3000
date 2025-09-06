from flask import Flask
import threading
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot de Monitoramento Roblox Ativo! 🏆📶"

@app.route('/status')
def status():
    return {
        "status": "online",
        "message": "Monitor de badges e presença rodando",
        "uptime": time.time()
    }

def run_flask():
    """Executa o servidor Flask em thread separada"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def keep_alive():
    """Inicia o servidor web para manter o Replit ativo"""
    print("🌐 Iniciando servidor keep-alive...")
    
    # Executar Flask em thread separada para não bloquear o programa principal
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("✅ Servidor keep-alive iniciado na porta 5000")