import requests
import json
import time
import os
from datetime import datetime

# ====== CONFIGURAÇÕES QUE O USUÁRIO PODE ALTERAR ======
USER_IDS = [1818113777,
    # Adicione aqui os IDs dos usuários do Roblox que você quer monitorar
    # Exemplo: 1, 261, 156
]

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1413656858383880233/v5vplQKyAeU0Uj7x7vgzmevE46e7uqLMH_2U58rZpy8-musK_ZP01It8LY9A5dfvVaYh"  # Cole aqui a URL do seu webhook do Discord

CHECK_INTERVAL = 60  # Intervalo de checagem em segundos (60 = 1 minuto)

# ====== NÃO ALTERE DAQUI PARA BAIXO ======

# Arquivo para armazenar as badges já conhecidas
BADGES_FILE = "known_badges.json"

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

def get_user_badges(user_id):
    """Obtém todas as badges de um usuário"""
    try:
        url = f"https://badges.roblox.com/v1/users/{user_id}/badges"
        params = {
            'limit': 100,
            'sortOrder': 'Desc'
        }
        
        all_badges = []
        cursor = None
        
        while True:
            if cursor:
                params['cursor'] = cursor
            
            response = requests.get(url, params=params)
            if response.status_code != 200:
                print(f"❌ Erro ao obter badges do usuário {user_id}: {response.status_code}")
                break
                
            data = response.json()
            all_badges.extend(data.get('data', []))
            
            cursor = data.get('nextPageCursor')
            if not cursor:
                break
        
        return all_badges
    except Exception as e:
        print(f"❌ Erro ao consultar badges do usuário {user_id}: {e}")
        return []

def get_badge_info(badge_id):
    """Obtém informações detalhadas de uma badge"""
    try:
        url = f"https://badges.roblox.com/v1/badges/{badge_id}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Erro ao obter info da badge {badge_id}: {e}")
        return None

def get_badge_url(badge_id):
    """Retorna a URL da badge no Roblox"""
    return f"https://www.roblox.com/badges/{badge_id}"

def get_user_info(user_id):
    """Obtém informações do usuário"""
    try:
        url = f"https://users.roblox.com/v1/users/{user_id}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Erro ao obter info do usuário {user_id}: {e}")
        return None

def get_user_avatar(user_id):
    """Obtém o avatar/headshot do usuário"""
    try:
        url = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
        params = {
            'userIds': user_id,
            'size': '150x150',
            'format': 'Png',
            'isCircular': False
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                return data['data'][0].get('imageUrl')
        return None
    except Exception as e:
        print(f"❌ Erro ao obter avatar do usuário {user_id}: {e}")
        return None

def send_discord_notification(user_info, badge_info, badge_url, avatar_url):
    """Envia notificação para o Discord"""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️  Discord Webhook URL não configurada!")
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
        
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("✅ Notificação enviada para o Discord!")
        else:
            print(f"❌ Erro ao enviar notificação: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro ao enviar notificação para Discord: {e}")

def check_for_new_badges(send_notifications=True):
    """Verifica se há novas badges para todos os usuários monitorados"""
    known_badges = load_known_badges()
    
    for user_id in USER_IDS:
        print(f"🔍 Verificando usuário {user_id}...")
        
        # Obter badges atuais do usuário
        current_badges = get_user_badges(user_id)
        current_badge_ids = set(badge['id'] for badge in current_badges)
        
        # Obter badges conhecidas para este usuário
        user_known_badges = set(known_badges.get(str(user_id), []))
        
        # Encontrar novas badges
        new_badge_ids = current_badge_ids - user_known_badges
        
        if new_badge_ids and send_notifications:
            print(f"🎉 {len(new_badge_ids)} nova(s) badge(s) encontrada(s) para o usuário {user_id}!")
            
            # Obter informações do usuário uma vez
            user_info = get_user_info(user_id)
            avatar_url = get_user_avatar(user_id)
            
            for badge_id in new_badge_ids:
                print(f"  📋 Processando badge {badge_id}...")
                
                # Obter informações da badge
                badge_info = get_badge_info(badge_id)
                if not badge_info:
                    continue
                
                # Obter URL da badge
                badge_url = get_badge_url(badge_id)
                
                # Enviar notificação
                send_discord_notification(user_info, badge_info, badge_url, avatar_url)
                
                # Pequeno delay para evitar rate limiting
                time.sleep(2)
        elif new_badge_ids and not send_notifications:
            print(f"📋 {len(new_badge_ids)} badge(s) existente(s) carregada(s) para o usuário {user_id}")
        
        # Atualizar badges conhecidas para este usuário
        known_badges[str(user_id)] = list(current_badge_ids)
    
    # Salvar badges conhecidas
    save_known_badges(known_badges)

def main():
    """Função principal do programa"""
    print("🚀 Iniciando monitor de badges do Roblox...")
    print(f"👥 Monitorando {len(USER_IDS)} usuário(s)")
    print(f"⏰ Intervalo de checagem: {CHECK_INTERVAL} segundos")
    print(f"🔗 Discord Webhook: {'✅ Configurado' if DISCORD_WEBHOOK_URL else '❌ NÃO CONFIGURADO'}")
    print("─" * 50)
    
    if not USER_IDS:
        print("⚠️  AVISO: Nenhum ID de usuário configurado na lista USER_IDS!")
        print("   Adicione IDs de usuários do Roblox na variável USER_IDS no início do arquivo.")
        return
    
    if not DISCORD_WEBHOOK_URL:
        print("⚠️  AVISO: Discord Webhook URL não configurada!")
        print("   Configure a variável DISCORD_WEBHOOK_URL no início do arquivo.")
        print("   O programa irá funcionar, mas não enviará notificações.")
        print()
    
    # Primeira execução para popular badges conhecidas (sem enviar notificações)
    print("📊 Primeira verificação (carregando badges existentes)...")
    check_for_new_badges(send_notifications=False)
    print("✅ Badges existentes carregadas!")
    print()
    
    # Loop principal
    try:
        while True:
            print(f"🔄 Verificando badges... ({datetime.now().strftime('%H:%M:%S')})")
            check_for_new_badges()
            print(f"⏸️  Aguardando {CHECK_INTERVAL} segundos...")
            print()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n👋 Monitor interrompido pelo usuário. Até logo!")

if __name__ == "__main__":
    main()