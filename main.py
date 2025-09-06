import requests
import json
import time
import os
import threading
from datetime import datetime
from keep_alive import keep_alive
from api_utils import (
    get_user_badges_robust,
    get_users_presence_robust, 
    get_user_info_robust,
    get_user_avatar_robust,
    get_badge_info_robust,
    get_place_info_robust,
    print_api_stats
)

# ====== CONFIGURAÇÕES QUE O USUÁRIO PODE ALTERAR ======

# Configure seus grupos de monitoramento aqui
# Cada grupo pode ter seu próprio webhook Discord e lista de usuários
MONITOR_GROUPS = [
    {
        "name": "Nouvelle",
        "webhook_url": "https://discord.com/api/webhooks/1413656858383880233/v5vplQKyAeU0Uj7x7vgzmevE46e7uqLMH_2U58rZpy8-musK_ZP01It8LY9A5dfvVaYh",
        "user_ids": [1818113777,3925323630,1559981851,3679768182,1559307226]  # IDs dos usuários do Roblox para este grupo
    },
    {
        "name": "Comunidade Civil",
        "webhook_url": "https://discord.com/api/webhooks/1413663842767994980/gGaGf8szgsSrEQ2OytcSzhODmLu0X5blNcZNAlcWTh6c1z8fO1Ya0ZXEBukUuPDxrgx8",  # Cole aqui a URL do segundo webhook
        "user_ids": [1390165577,679520330]  # Adicione aqui os IDs dos usuários do segundo grupo
    }
    # Adicione mais grupos conforme necessário...
]

CHECK_INTERVAL = 30  # Intervalo de checagem em segundos (30 = 30 segundos)

# ====== NÃO ALTERE DAQUI PARA BAIXO ======

# Arquivos para armazenar dados
BADGES_FILE = "known_badges.json"
PRESENCE_FILE = "last_presence.json"

def load_known_badges():
    """Carrega as badges já conhecidas do arquivo"""
    if os.path.exists(BADGES_FILE):
        try:
            with open(BADGES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_known_badges(badges_data):
    """Salva as badges conhecidas no arquivo"""
    with open(BADGES_FILE, 'w') as f:
        json.dump(badges_data, f, indent=2)

def load_last_presence():
    """Carrega o último status de presença dos usuários"""
    if os.path.exists(PRESENCE_FILE):
        try:
            with open(PRESENCE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_last_presence(presence_data):
    """Salva o último status de presença dos usuários"""
    with open(PRESENCE_FILE, 'w') as f:
        json.dump(presence_data, f, indent=2)

def get_user_badges(user_id):
    """Obtém todas as badges de um usuário (versão robusta)"""
    badges, success, error = get_user_badges_robust(user_id)
    
    if not success:
        print(f"❌ Erro ao obter badges do usuário {user_id}: {error}")
        return []
    
    if not badges:
        print(f"    ⚠️  Nenhuma badge retornada pela API para usuário {user_id}")
    
    return badges

def get_badge_info(badge_id):
    """Obtém informações detalhadas de uma badge (versão robusta)"""
    info, success, error = get_badge_info_robust(badge_id)
    
    if not success:
        print(f"❌ Erro ao obter info da badge {badge_id}: {error}")
        return None
        
    return info

def get_badge_url(badge_id):
    """Retorna a URL da badge no Roblox"""
    return f"https://www.roblox.com/badges/{badge_id}"

def get_user_info(user_id):
    """Obtém informações do usuário (versão robusta)"""
    info, success, error = get_user_info_robust(user_id)
    
    if not success:
        print(f"❌ Erro ao obter info do usuário {user_id}: {error}")
        return None
        
    return info

def get_user_avatar(user_id):
    """Obtém o avatar/headshot do usuário (versão robusta)"""
    avatar_url, success, error = get_user_avatar_robust(user_id)
    
    if not success:
        print(f"❌ Erro ao obter avatar do usuário {user_id}: {error}")
        return None
        
    return avatar_url

def get_users_presence(user_ids):
    """Obtém o status de presença de múltiplos usuários (versão robusta)"""
    presences, success, error = get_users_presence_robust(user_ids)
    
    if not success:
        print(f"❌ Erro ao obter presença dos usuários: {error}")
        return []
        
    return presences

def get_place_info(place_id):
    """Obtém informações do jogo/place (versão robusta)"""
    if not place_id:
        return None
        
    info, success, error = get_place_info_robust(place_id)
    
    if not success:
        print(f"    ⚠️  Erro ao obter info do place {place_id}: {error}")
        return None
        
    return info

def presence_type_to_text(presence_type):
    """Converte o código de presença para texto legível"""
    presence_map = {
        0: "Offline",
        1: "Online", 
        2: "Em Jogo",
        3: "No Studio"
    }
    return presence_map.get(presence_type, "Desconhecido")

def send_presence_notification(user_info, status_text, game_name, avatar_url, webhook_url, group_name):
    """Envia notificação de mudança de presença para o Discord"""
    if not webhook_url:
        print(f"⚠️  Webhook do {group_name} não configurado!")
        return
    
    try:
        # Definir cor baseada no status
        colors = {
            "Online": 0x00FF00,      # Verde
            "Em Jogo": 0x0099FF,     # Azul
            "No Studio": 0xFF9900    # Laranja
        }
        color = colors.get(status_text, 0x00FF00)
        
        # Criar embed do Discord
        embed = {
            "title": "📶 Mudança de Status!",
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "👤 Usuário",
                    "value": user_info.get('displayName', 'Usuário Desconhecido'),
                    "inline": True
                },
                {
                    "name": "📶 Status",
                    "value": status_text,
                    "inline": True
                }
            ]
        }
        
        # Adicionar jogo se estiver jogando
        if game_name and status_text == "Em Jogo":
            embed["fields"].append({
                "name": "🎮 Jogo",
                "value": game_name,
                "inline": True
            })
        
        # Adicionar avatar do usuário se disponível
        if avatar_url:
            embed["thumbnail"] = {"url": avatar_url}
        
        # Payload do webhook
        payload = {
            "embeds": [embed]
        }
        
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            print(f"✅ Notificação de presença enviada para {group_name}!")
        else:
            print(f"❌ Erro ao enviar notificação de presença para {group_name}: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro ao enviar notificação de presença para {group_name}: {e}")

def send_discord_notification(user_info, badge_info, badge_url, avatar_url, webhook_url, group_name):
    """Envia notificação para o Discord"""
    if not webhook_url:
        print(f"⚠️  Webhook do {group_name} não configurado!")
        return
    
    try:
        # Criar embed do Discord
        embed = {
            "title": "🏆 Nova Badge Conquistada!",
            "color": 0x00FF00,  # Verde
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "🏆 Badge",
                    "value": badge_info.get('displayName', 'Badge Desconhecida'),
                    "inline": True
                },
                {
                    "name": "👤 Usuário",
                    "value": user_info.get('displayName', 'Usuário Desconhecido'),
                    "inline": True
                },
                {
                    "name": "🔗 Badge",
                    "value": f"[Ver Badge]({badge_url})",
                    "inline": True
                }
            ]
        }
        
        # Adicionar descrição da badge se disponível
        if badge_info.get('description'):
            embed["description"] = badge_info['description']
        
        # Adicionar avatar do usuário se disponível
        if avatar_url:
            embed["thumbnail"] = {"url": avatar_url}
        
        # Payload do webhook
        payload = {
            "embeds": [embed]
        }
        
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            print(f"✅ Notificação enviada para {group_name}!")
        else:
            print(f"❌ Erro ao enviar notificação para {group_name}: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro ao enviar notificação para {group_name}: {e}")

def check_presence_changes():
    """Verifica mudanças de presença para todos os grupos monitorados"""
    last_presence = load_last_presence()
    
    for group in MONITOR_GROUPS:
        group_name = group["name"]
        webhook_url = group["webhook_url"]
        user_ids = group["user_ids"]
        
        if not user_ids:
            continue
            
        print(f"\n📶 Presença {group_name}:")
        
        # Obter presença atual de todos os usuários do grupo
        current_presences = get_users_presence(user_ids)
        if not current_presences:
            print(f"    ⚠️  Nenhuma presença retornada pela API")
            continue
        
        for presence in current_presences:
            user_id = presence.get('userId')
            if not user_id:
                continue
                
            current_status = presence.get('userPresenceType', 0)
            last_status = last_presence.get(str(user_id), 0)
            
            print(f"    👤 Usuário {user_id}: {presence_type_to_text(last_status)} → {presence_type_to_text(current_status)}")
            
            # Verificar se houve mudança de Offline para Online/Jogo/Studio
            if last_status == 0 and current_status > 0:
                print(f"  📶 Usuário {user_id} ficou {presence_type_to_text(current_status)}!")
                
                # Obter informações do usuário
                user_info = get_user_info(user_id)
                avatar_url = get_user_avatar(user_id)
                
                # Obter nome do jogo se estiver jogando
                game_name = None
                if current_status == 2 and presence.get('placeId'):  # Em Jogo
                    place_info = get_place_info(presence.get('placeId'))
                    if place_info:
                        game_name = place_info.get('name', 'Jogo Desconhecido')
                
                # Enviar notificação
                status_text = presence_type_to_text(current_status)
                send_presence_notification(user_info, status_text, game_name, avatar_url, webhook_url, group_name)
                
                # Pequeno delay para evitar rate limiting
                time.sleep(2)
            
            # Atualizar último status conhecido
            last_presence[str(user_id)] = current_status
    
    # Salvar último status conhecido
    save_last_presence(last_presence)

def monitor_badges():
    """Loop de monitoramento de badges com melhorias de confiabilidade"""
    print("🏆 Iniciando monitoramento de badges...")
    
    # Primeira execução para popular badges conhecidas (sem enviar notificações)
    print("📊 Carregando badges existentes...")
    check_for_new_badges(send_notifications=False)
    print("✅ Badges existentes carregadas!")
    
    # Contador para estatísticas
    cycle_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    # Loop principal de badges
    while True:
        try:
            cycle_count += 1
            print(f"\n🔄 [BADGES] Verificando... ({datetime.now().strftime('%H:%M:%S')})")
            
            # Executar verificação
            check_for_new_badges()
            
            # Reset contador de erros em caso de sucesso
            consecutive_errors = 0
            
            # Mostrar estatísticas a cada 10 ciclos
            if cycle_count % 10 == 0:
                print(f"\n📊 [STATS BADGES] Ciclo {cycle_count} completado")
                print_api_stats()
            
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Erro no monitor de badges (#{consecutive_errors}): {e}")
            
            # Se muitos erros consecutivos, aumentar delay
            if consecutive_errors >= max_consecutive_errors:
                extended_sleep = CHECK_INTERVAL * 2
                print(f"⚠️  Muitos erros consecutivos, aguardando {extended_sleep}s...")
                time.sleep(extended_sleep)
                consecutive_errors = 0  # Reset após delay estendido
            else:
                time.sleep(CHECK_INTERVAL)

def show_initial_presence():
    """Mostra o status de presença atual de todos os usuários"""
    print("📊 Status atual dos usuários:")
    print("─" * 50)
    
    for group in MONITOR_GROUPS:
        group_name = group["name"]
        user_ids = group["user_ids"]
        
        if not user_ids:
            continue
            
        print(f"\n👥 {group_name}:")
        
        # Obter presença atual de todos os usuários do grupo
        current_presences = get_users_presence(user_ids)
        
        for presence in current_presences:
            user_id = presence.get('userId')
            if not user_id:
                continue
                
            current_status = presence.get('userPresenceType', 0)
            status_text = presence_type_to_text(current_status)
            
            # Obter nome do usuário
            user_info = get_user_info(user_id)
            user_name = user_info.get('displayName', f'Usuário {user_id}') if user_info else f'Usuário {user_id}'
            
            # Mostrar jogo se estiver jogando
            game_info = ""
            if current_status == 2 and presence.get('placeId'):  # Em Jogo
                place_info = get_place_info(presence.get('placeId'))
                if place_info:
                    game_name = place_info.get('name', 'Jogo Desconhecido')
                    game_info = f" - {game_name}"
            
            # Emoji baseado no status
            status_emoji = {
                0: "⭕",  # Offline
                1: "🟢",  # Online
                2: "🔵",  # Em Jogo  
                3: "🟠"   # No Studio
            }.get(current_status, "❓")
            
            print(f"  {status_emoji} {user_name}: {status_text}{game_info}")
    
    print("─" * 50)

def monitor_presence():
    """Loop de monitoramento de presença com melhorias de confiabilidade"""
    print("📶 Iniciando monitoramento de presença...")
    
    # Mostrar presença inicial
    show_initial_presence()
    
    # Primeira execução para popular presença conhecida (sem mostrar novamente)
    print("📊 Carregando presença conhecida...")
    check_presence_changes()
    print("✅ Presença atual carregada!")
    
    # Contador para estatísticas
    cycle_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    # Loop principal de presença
    while True:
        try:
            cycle_count += 1
            print(f"\n📶 [PRESENÇA] Verificando... ({datetime.now().strftime('%H:%M:%S')})")
            
            # Executar verificação
            check_presence_changes()
            
            # Reset contador de erros em caso de sucesso
            consecutive_errors = 0
            
            # Mostrar estatísticas a cada 15 ciclos
            if cycle_count % 15 == 0:
                print(f"\n📊 [STATS PRESENÇA] Ciclo {cycle_count} completado")
                print_api_stats()
            
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Erro no monitor de presença (#{consecutive_errors}): {e}")
            
            # Se muitos erros consecutivos, aumentar delay
            if consecutive_errors >= max_consecutive_errors:
                extended_sleep = CHECK_INTERVAL * 2
                print(f"⚠️  Muitos erros consecutivos, aguardando {extended_sleep}s...")
                time.sleep(extended_sleep)
                consecutive_errors = 0  # Reset após delay estendido
            else:
                time.sleep(CHECK_INTERVAL)

def check_for_new_badges(send_notifications=True):
    """Verifica se há novas badges para todos os grupos monitorados"""
    known_badges = load_known_badges()
    
    for group in MONITOR_GROUPS:
        group_name = group["name"]
        webhook_url = group["webhook_url"]
        user_ids = group["user_ids"]
        
        if not user_ids:
            continue
            
        print(f"\n👥 {group_name}:")
        
        for user_id in user_ids:
            print(f"  🔍 Verificando usuário {user_id}...")
            
            # Obter badges atuais do usuário
            current_badges = get_user_badges(user_id)
            if not current_badges:
                print(f"    ⚠️  Nenhuma badge retornada pela API para usuário {user_id}")
                continue
            current_badge_ids = set(badge['id'] for badge in current_badges)
            print(f"    📊 {len(current_badge_ids)} badges encontradas")
            
            # Obter badges conhecidas para este usuário
            user_known_badges = set(known_badges.get(str(user_id), []))
            
            # Encontrar novas badges
            new_badge_ids = current_badge_ids - user_known_badges
            
            if new_badge_ids and send_notifications:
                print(f"  🎉 {len(new_badge_ids)} nova(s) badge(s) encontrada(s) para o usuário {user_id}!")
                
                # Obter informações do usuário uma vez
                user_info = get_user_info(user_id)
                avatar_url = get_user_avatar(user_id)
                
                for badge_id in new_badge_ids:
                    print(f"    📋 Processando badge {badge_id}...")
                    
                    # Obter informações da badge
                    badge_info = get_badge_info(badge_id)
                    if not badge_info:
                        continue
                    
                    # Obter URL da badge
                    badge_url = get_badge_url(badge_id)
                    
                    # Enviar notificação
                    send_discord_notification(user_info, badge_info, badge_url, avatar_url, webhook_url, group_name)
                    
                    # Pequeno delay para evitar rate limiting
                    time.sleep(2)
            elif new_badge_ids and not send_notifications:
                print(f"  📋 {len(new_badge_ids)} badge(s) existente(s) carregada(s) para o usuário {user_id}")
            
            # Atualizar badges conhecidas para este usuário
            known_badges[str(user_id)] = list(current_badge_ids)
    
    # Salvar badges conhecidas
    save_known_badges(known_badges)

def main():
    """Função principal do programa"""
    print("🚀 Iniciando Monitor de Badges e Presença do Roblox...")
    
    # Contar total de usuários em todos os grupos
    total_users = sum(len(group["user_ids"]) for group in MONITOR_GROUPS)
    active_groups = sum(1 for group in MONITOR_GROUPS if group["user_ids"] and group["webhook_url"])
    
    print(f"👥 Monitorando {total_users} usuário(s) em {len(MONITOR_GROUPS)} grupo(s)")
    print(f"✅ {active_groups} grupo(s) ativo(s)")
    print(f"⏰ Intervalo de checagem: {CHECK_INTERVAL} segundos")
    print("🏆 Monitoramento: Badges + 📶 Presença Online")
    print("─" * 50)
    
    # Mostrar status de cada grupo
    for group in MONITOR_GROUPS:
        group_name = group["name"]
        webhook_configured = "✅" if group["webhook_url"] else "❌"
        user_count = len(group["user_ids"])
        print(f"📋 {group_name}: {webhook_configured} Webhook | {user_count} usuário(s)")
    
    print("─" * 50)
    
    if total_users == 0:
        print("⚠️  AVISO: Nenhum usuário configurado em nenhum grupo!")
        print("   Adicione IDs de usuários nas listas user_ids dos grupos.")
        return
    
    groups_without_webhook = [g["name"] for g in MONITOR_GROUPS if g["user_ids"] and not g["webhook_url"]]
    if groups_without_webhook:
        print(f"⚠️  AVISO: Grupos sem webhook configurado: {', '.join(groups_without_webhook)}")
        print("   Estes grupos não enviarão notificações.")
        print()
    
    # Iniciar servidor keep-alive primeiro
    keep_alive()
    
    # Criar e iniciar threads para monitoramento
    try:
        print("🚀 Iniciando sistemas de monitoramento em paralelo...")
        
        # Thread para monitoramento de badges
        badges_thread = threading.Thread(target=monitor_badges, daemon=True)
        badges_thread.start()
        
        # Thread para monitoramento de presença
        presence_thread = threading.Thread(target=monitor_presence, daemon=True)
        presence_thread.start()
        
        print("✅ Todos os sistemas iniciados!")
        print("🌐 Servidor Keep-Alive: Mantém o bot ativo 24/7")
        print("🏆 Monitor de Badges: Detecta novas badges conquistadas")
        print("📶 Monitor de Presença: Detecta quando usuários ficam online")
        print("─" * 50)
        
        # Manter o programa rodando
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Monitor interrompido pelo usuário. Até logo!")

if __name__ == "__main__":
    main()