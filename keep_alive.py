from flask import Flask, jsonify
import threading
import time
import requests
import os
import random
import atexit
import signal
import sys
from datetime import datetime, timedelta

app = Flask(__name__)

# Variáveis globais para controle
start_time = time.time()
railway_url = os.getenv('RAILWAY_PUBLIC_DOMAIN')
ping_stats = {
    'local': {'success': 0, 'failure': 0, 'last_ping': None},
    'external': {'success': 0, 'failure': 0, 'last_ping': None}
}

@app.route('/')
def home():
    """Endpoint principal - indica que o bot está ativo"""
    uptime = get_uptime_formatted()
    return f"""
    🤖 Discord Bot - Roblox Monitor Ativo! 🏆📶
    
    ⏰ Uptime: {uptime}
    🌐 Keep-Alive: Ativo  
    🤖 Discord Bot: Online
    🏆 Monitor Badges: Ativo
    📶 Monitor Presença: Ativo
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
        "railway_url": railway_url,
        "ping_stats": ping_stats,
        "services": {
            "flask_server": "online",
            "discord_bot": "running",
            "badge_monitor": "active",
            "presence_monitor": "active"
        }
    })

@app.route('/health')
def health():
    """Endpoint de saúde simples para Railway"""
    return jsonify({
        "status": "healthy", 
        "message": "Discord bot is running",
        "timestamp": datetime.now().isoformat(),
        "uptime": get_uptime_formatted()
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

def log_system_event(event_type, message):
    """Log de eventos do sistema (substitui notificações webhook)"""
    emoji_map = {
        'startup': '🟢',
        'shutdown': '🔴',
        'crash': '💥',
        'restart': '🔄'
    }
    emoji = emoji_map.get(event_type, '🔔')
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    print(f"{emoji} [{timestamp}] {event_type.upper()}: {message}")

def detect_public_url():
    """Detecta automaticamente o URL público (Railway ou outras plataformas)"""
    global public_url
    
    try:
        # Railway detection (primary)
        railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
        if railway_domain:
            public_url = f"https://{railway_domain}"
            print(f"🚀 Railway URL detectado: {public_url}")
            return
        
        # Generic cloud platform detection (fallback)
        repl_slug = os.getenv('REPL_SLUG')
        repl_owner = os.getenv('REPL_OWNER')
        if repl_slug and repl_owner:
            public_url = f"https://{repl_slug}--{repl_owner}.replit.app"
            print(f"🌐 Plataforma de nuvem detectada: {public_url}")
            return
        
        print("⚠️  URL público não detectado - ping externo desabilitado")
        print("   Isso é normal se executando localmente")
        public_url = None
            
    except Exception as e:
        print(f"❌ Erro ao detectar URL público: {e}")
        public_url = None

def ping_local():
    """Realiza ping local (localhost)"""
    try:
        port = os.getenv('PORT', '5000')
        response = requests.get(f"http://127.0.0.1:{port}/", timeout=10)
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
    """Realiza ping externo (URL público)"""
    if not public_url:
        print("⚠️  URL público não detectado, pulando ping externo")
        return False
    
    try:
        response = requests.get(public_url, timeout=15)
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
    if public_url:
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
            
            if public_url:
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

# Handlers de shutdown
def shutdown_handler(signum=None, frame=None):
    """Handler chamado quando o sistema vai ser desligado"""
    print("\n🔴 Sistema sendo desligado...")
    log_system_event('shutdown', 'Bot de monitoramento foi desligado')
    time.sleep(1)  # Tempo para log

def exit_handler():
    """Handler chamado na saída do programa"""
    print("🔴 Finalizando sistema...")
    log_system_event('shutdown', 'Bot de monitoramento foi finalizado')
    time.sleep(1)  # Tempo para log

def setup_shutdown_handlers():
    """Configura os handlers de shutdown"""
    # Registrar handler para saída normal
    atexit.register(exit_handler)
    
    # Registrar handlers para sinais do sistema
    try:
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, shutdown_handler)
        print("✅ Handlers de shutdown configurados")
    except Exception as e:
        print(f"⚠️  Erro ao configurar handlers de shutdown: {e}")

def run_flask():
    """Executa o servidor Flask em thread separada"""
    try:
        print("🚀 Iniciando servidor Flask...")
        # Usar configurações seguras para produção
        port = int(os.getenv('PORT', '5000'))
        app.run(
            host='0.0.0.0', 
            port=port, 
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
    
    # 0. Configurar handlers
    setup_shutdown_handlers()
    
    # 1. Detectar URL público
    detect_public_url()
    
    # 2. Iniciar servidor Flask em thread separada
    port = int(os.getenv('PORT', '5000'))
    print(f"🚀 Iniciando servidor Flask na porta {port}...")
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
    
    # 4. Enviar notificação de sistema inicializado
    startup_message = ("🟢 **Sistema Online**\n\n"
                      "O bot de monitoramento foi iniciado com sucesso!\n\n"
                      "**Serviços Ativos:**\n"
                      "🏆 Monitor de Badges\n"
                      "📶 Monitor de Presença\n"
                      "🌐 Servidor Keep-Alive\n"
                      "🔄 Auto-Ping Sistema")
    
    log_system_event('startup', 'Bot de monitoramento iniciado com sucesso')
    
    # 5. Exibir informações finais
    print("🌐 ========================================")
    print("✅ Keep-Alive Sistema ATIVO!")
    port = os.getenv('PORT', '5000')
    print(f"🌐 Servidor local: http://127.0.0.1:{port}")
    if public_url:
        print(f"🌐 URL público: {public_url}")
        print(f"🔗 Status: {public_url}/status")
        print(f"💚 Health: {public_url}/health")
    print("🔄 Auto-ping: Ativo (4.5-5.5 min)")
    print("📊 Logs: Pings e status serão mostrados automaticamente")
    print("📢 Notificações: Startup/Shutdown configuradas")
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