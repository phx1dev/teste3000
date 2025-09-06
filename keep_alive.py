from flask import Flask, jsonify
import threading
import time
import requests
import os
import random
from datetime import datetime, timedelta

app = Flask(__name__)

# Variáveis globais para controle
start_time = time.time()
replit_url = None
ping_stats = {
    'local': {'success': 0, 'failure': 0, 'last_ping': None},
    'external': {'success': 0, 'failure': 0, 'last_ping': None}
}

@app.route('/')
def home():
    """Endpoint principal - indica que o bot está ativo"""
    uptime = get_uptime_formatted()
    return f"""
    🤖 Bot de Monitoramento Roblox Ativo! 🏆📶
    
    ⏰ Uptime: {uptime}
    🌐 Keep-Alive: Ativo
    🏆 Monitor Badges: Rodando
    📶 Monitor Presença: Rodando
    """

@app.route('/status')
def status():
    """Endpoint de status - retorna JSON com informações detalhadas"""
    uptime_seconds = time.time() - start_time
    
    return jsonify({
        "status": "online",
        "message": "Monitor de badges e presença rodando",
        "uptime_seconds": round(uptime_seconds, 2),
        "uptime_formatted": get_uptime_formatted(),
        "start_time": datetime.fromtimestamp(start_time).isoformat(),
        "current_time": datetime.now().isoformat(),
        "replit_url": replit_url,
        "ping_stats": ping_stats,
        "services": {
            "flask_server": "online",
            "badge_monitor": "running",
            "presence_monitor": "running",
            "auto_ping": "active"
        }
    })

def get_uptime_formatted():
    """Formata o tempo de atividade de forma legível"""
    uptime_seconds = int(time.time() - start_time)
    
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    if days > 0:
        return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
    elif hours > 0:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    elif minutes > 0:
        return f"{minutes:02d}m {seconds:02d}s"
    else:
        return f"{seconds:02d}s"

def detect_replit_url():
    """Detecta automaticamente o URL público do Replit"""
    global replit_url
    
    try:
        # Verificar variáveis de ambiente do Replit
        repl_slug = os.getenv('REPL_SLUG')
        repl_owner = os.getenv('REPL_OWNER')
        replit_db_url = os.getenv('REPLIT_DB_URL')
        
        if replit_db_url:
            # Extrair URL do REPLIT_DB_URL (formato: https://kv.replit.com/v0/...)
            # Modificar para o formato do app: https://repl-name--username.replit.app
            if repl_slug and repl_owner:
                replit_url = f"https://{repl_slug}--{repl_owner}.replit.app"
            else:
                print("⚠️  Não foi possível detectar REPL_SLUG ou REPL_OWNER")
        
        # Fallback: tentar outras variáveis do Replit
        if not replit_url:
            replit_domains = os.getenv('REPLIT_DOMAINS')
            if replit_domains:
                domains_list = replit_domains.split(',')
                if domains_list:
                    replit_url = f"https://{domains_list[0].strip()}"
        
        # Se ainda não encontrou, tentar construir baseado no hostname
        if not replit_url and repl_slug and repl_owner:
            replit_url = f"https://{repl_slug}.{repl_owner}.repl.co"
        
        if replit_url:
            print(f"🌐 URL público detectado: {replit_url}")
            print(f"📋 Use este link para monitoramento externo: {replit_url}")
        else:
            print("⚠️  Não foi possível detectar automaticamente o URL público do Replit")
            print("   O ping externo será desabilitado.")
            
    except Exception as e:
        print(f"❌ Erro ao detectar URL do Replit: {e}")

def ping_local():
    """Realiza ping local (localhost)"""
    try:
        response = requests.get("http://127.0.0.1:5000/", timeout=10)
        if response.status_code == 200:
            ping_stats['local']['success'] += 1
            ping_stats['local']['last_ping'] = datetime.now().isoformat()
            print(f"✅ Ping local realizado com sucesso ({response.status_code})")
            return True
        else:
            raise Exception(f"Status code: {response.status_code}")
    except Exception as e:
        ping_stats['local']['failure'] += 1
        print(f"❌ Ping local falhou: {e}")
        return False

def ping_external():
    """Realiza ping externo (URL público do Replit)"""
    if not replit_url:
        print("⚠️  URL público não detectado, pulando ping externo")
        return False
    
    try:
        response = requests.get(replit_url, timeout=15)
        if response.status_code == 200:
            ping_stats['external']['success'] += 1
            ping_stats['external']['last_ping'] = datetime.now().isoformat()
            print(f"✅ Ping externo realizado com sucesso ({response.status_code})")
            return True
        else:
            raise Exception(f"Status code: {response.status_code}")
    except Exception as e:
        ping_stats['external']['failure'] += 1
        print(f"❌ Ping externo falhou: {e}")
        return False

def auto_ping_loop():
    """Loop de auto-ping com intervalos aleatórios"""
    print("🔄 Iniciando sistema de auto-ping...")
    
    # Delay inicial para garantir que o Flask esteja pronto
    initial_delay = 30  # 30 segundos
    print(f"⏳ Aguardando {initial_delay}s antes do primeiro ping...")
    time.sleep(initial_delay)
    
    # Primeiro ping para teste
    print("🔍 Realizando primeiro ping de teste...")
    ping_local()
    if replit_url:
        ping_external()
    
    # Loop principal
    ping_count = 1
    while True:
        try:
            # Intervalo aleatório entre 4.5 e 5.5 minutos (270-330 segundos)
            interval = random.uniform(270, 330)
            
            print(f"⏰ Próximo ping em {interval/60:.1f} minutos...")
            time.sleep(interval)
            
            ping_count += 1
            current_time = datetime.now().strftime('%H:%M:%S')
            print(f"\n🔄 [PING #{ping_count}] Executando pings... ({current_time})")
            
            # Realizar pings
            local_success = ping_local()
            external_success = False
            
            if replit_url:
                external_success = ping_external()
            
            # Log resumido
            local_total = ping_stats['local']['success'] + ping_stats['local']['failure']
            external_total = ping_stats['external']['success'] + ping_stats['external']['failure']
            
            print(f"📊 Stats - Local: {ping_stats['local']['success']}/{local_total} | " +
                  f"Externo: {ping_stats['external']['success']}/{external_total}")
            
        except Exception as e:
            print(f"❌ Erro no loop de auto-ping: {e}")
            # Continuar mesmo com erro
            time.sleep(60)  # Aguardar 1 minuto antes de tentar novamente

def run_flask():
    """Executa o servidor Flask em thread separada"""
    try:
        print("🚀 Iniciando servidor Flask...")
        # Usar configurações seguras para produção
        app.run(
            host='0.0.0.0', 
            port=5000, 
            debug=False, 
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        print(f"❌ Erro no servidor Flask: {e}")

def keep_alive():
    """Função principal - inicia todos os sistemas de keep-alive"""
    global start_time
    start_time = time.time()
    
    print("🌐 ========================================")
    print("🌐 Iniciando Sistema Keep-Alive Avançado")
    print("🌐 ========================================")
    
    # 1. Detectar URL público do Replit
    detect_replit_url()
    
    # 2. Iniciar servidor Flask em thread separada
    print("🚀 Iniciando servidor Flask na porta 5000...")
    flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskServer")
    flask_thread.start()
    
    # Aguardar um pouco para o Flask iniciar
    time.sleep(3)
    print("✅ Servidor Flask iniciado com sucesso!")
    
    # 3. Iniciar sistema de auto-ping em thread separada
    print("🔄 Iniciando sistema de auto-ping...")
    ping_thread = threading.Thread(target=auto_ping_loop, daemon=True, name="AutoPing")
    ping_thread.start()
    
    print("✅ Sistema de auto-ping iniciado!")
    
    # 4. Exibir informações finais
    print("🌐 ========================================")
    print("✅ Keep-Alive Sistema ATIVO!")
    print(f"🌐 Servidor local: http://127.0.0.1:5000")
    if replit_url:
        print(f"🌐 URL público: {replit_url}")
        print(f"🔗 Status: {replit_url}/status")
    print("🔄 Auto-ping: Ativo (4.5-5.5 min)")
    print("📊 Logs: Pings e status serão mostrados automaticamente")
    print("🌐 ========================================")
    
    return True

# Função auxiliar para debug (se executado diretamente)
if __name__ == "__main__":
    print("🧪 Testando keep_alive.py diretamente...")
    keep_alive()
    
    # Manter vivo se executado diretamente
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Keep-alive interrompido!")