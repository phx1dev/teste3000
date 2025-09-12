import discord
from discord.ext import commands, tasks
import json
import os
import threading
from datetime import datetime
import asyncio
from api_utils import (
    get_user_badges_robust,
    get_users_presence_robust, 
    get_user_info_robust,
    get_user_avatar_robust,
    get_badge_info_robust,
    get_place_info_robust,
    get_group_info_robust,
    get_group_members_robust,
    print_api_stats
)
from config import (
    AUTHORIZED_DISCORD_IDS,
    NOTIFICATION_CHANNEL_ID,
    CHECK_INTERVAL,
    MESSAGES,
    COLORS,
    EMOJIS
)

# ====== CONFIGURAÇÕES DOS ARQUIVOS ======
GUILD_DATA_FILE = "guild_data.json"  # Dados por servidor Discord
BADGES_FILE = "known_badges.json"
PRESENCE_FILE = "last_presence.json"

# ====== VARIÁVEIS GLOBAIS ======
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
# Estrutura baseada em guild: {guild_id: {"tracked_users": {...}, "tracked_groups": {...}, "config": {...}}}
guild_data = {}
monitoring_active = False
monitoring_lock = threading.Lock()

# ====== FUNÇÕES DE ARQUIVO ======

def load_guild_data():
    """Carrega dados de todos os servidores"""
    global guild_data
    if os.path.exists(GUILD_DATA_FILE):
        try:
            with open(GUILD_DATA_FILE, 'r') as f:
                guild_data = json.load(f)
        except:
            guild_data = {}
    else:
        guild_data = {}

def save_guild_data():
    """Salva dados de todos os servidores"""
    with open(GUILD_DATA_FILE, 'w') as f:
        json.dump(guild_data, f, indent=2)

def get_guild_data(guild_id: int):
    """Obtém dados do servidor específico"""
    guild_str = str(guild_id)
    if guild_str not in guild_data:
        guild_data[guild_str] = {
            "tracked_users": {},
            "tracked_groups": {},
            "config": {"notification_channel_id": None}
        }
    return guild_data[guild_str]

def get_tracked_users(guild_id: int):
    """Obtém usuários monitorados do servidor"""
    return get_guild_data(guild_id)["tracked_users"]

def get_tracked_groups(guild_id: int):
    """Obtém grupos monitorados do servidor"""  
    return get_guild_data(guild_id)["tracked_groups"]

def get_guild_config(guild_id: int):
    """Obtém configurações do servidor"""
    return get_guild_data(guild_id)["config"]

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

# ====== FUNÇÕES AUXILIARES ======

def is_authorized(user_id):
    """Verifica se o usuário tem permissão para usar os comandos"""
    return user_id in AUTHORIZED_DISCORD_IDS

async def find_roblox_user_by_name(username):
    """Encontra um usuário do Roblox pelo nome de usuário usando aiohttp"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # API para buscar usuário por nome
            async with session.post("https://users.roblox.com/v1/usernames/users", 
                                   json={"usernames": [username]}) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('data') and len(data['data']) > 0:
                        return data['data'][0]['id']
    except Exception as e:
        print(f"Erro ao buscar usuário {username}: {e}")
    return None

def presence_type_to_text(presence_type):
    """Converte o código de presença para texto legível"""
    presence_map = {
        0: "Offline",
        1: "Online", 
        2: "Em Jogo",
        3: "No Studio"
    }
    return presence_map.get(presence_type, "Desconhecido")

# ====== EVENTOS DO BOT ======

@bot.event
async def on_ready():
    """Executado quando o bot está online"""
    print(f'{bot.user} está online!')
    print(f'IDs autorizados: {AUTHORIZED_DISCORD_IDS}')
    
    # Carregar dados salvos
    load_guild_data()
    
    # Iniciar monitoramento automático 
    if not monitoring_badge_task.is_running():
        monitoring_badge_task.start()
    if not monitoring_presence_task.is_running():
        monitoring_presence_task.start()
    if not monitoring_groups_task.is_running():
        monitoring_groups_task.start()
        
    print("✅ Monitoramento automático iniciado para todos os servidores!")
    
    # Sincronizar slash commands
    try:
        synced = await bot.tree.sync()
        print(f'Sincronizados {len(synced)} comando(s) slash')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')

# ====== COMANDOS SLASH ======

@bot.tree.command(name="track", description="Adiciona um usuário à lista de monitoramento")
@discord.app_commands.describe(username="Nome do usuário do Roblox para monitorar")
async def track_user(interaction: discord.Interaction, username: str):
    """Comando /track - Adiciona usuário à lista de monitoramento"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Buscar ID do usuário Roblox
        roblox_id = await find_roblox_user_by_name(username)
        if not roblox_id or not isinstance(roblox_id, int):
            await interaction.followup.send(
                f"❌ Usuário '{username}' não encontrado no Roblox!"
            )
            return
        
        # Verificar se já está sendo monitorado
        if str(roblox_id) in tracked_users:
            await interaction.followup.send(
                f"⚠️ O usuário '{username}' já está sendo monitorado!"
            )
            return
        
        # Adicionar à lista
        tracked_users[str(roblox_id)] = {
            "name": username,
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat()
        }
        save_tracked_users()
        
        await interaction.followup.send(
            f"✅ Usuário '{username}' (ID: {roblox_id}) adicionado à lista de monitoramento!"
        )
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="removetrack", description="Remove um usuário da lista de monitoramento")
@discord.app_commands.describe(username="Nome do usuário do Roblox para remover")
async def removetrack_user(interaction: discord.Interaction, username: str):
    """Comando /removetrack - Remove usuário da lista de monitoramento"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Buscar usuário na lista de monitorados
        user_found = None
        for roblox_id, user_data in tracked_users.items():
            if user_data["name"].lower() == username.lower():
                user_found = roblox_id
                break
        
        if not user_found:
            await interaction.followup.send(
                f"❌ Usuário '{username}' não está na lista de monitoramento!"
            )
            return
        
        # Remover da lista
        removed_user = tracked_users.pop(user_found)
        save_tracked_users()
        
        await interaction.followup.send(
            f"✅ Usuário '{username}' removido da lista de monitoramento!"
        )
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="view", description="Mostra informações sobre um usuário monitorado")
@discord.app_commands.describe(username="Nome do usuário do Roblox para visualizar")
async def view_user(interaction: discord.Interaction, username: str):
    """Comando /view - Mostra última badge e informações do usuário"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Buscar usuário na lista de monitorados
        user_found = None
        roblox_id = None
        for rid, user_data in tracked_users.items():
            if user_data["name"].lower() == username.lower():
                user_found = user_data
                roblox_id = int(rid)
                break
        
        if not user_found:
            await interaction.followup.send(
                f"❌ Usuário '{username}' não está na lista de monitoramento!"
            )
            return
        
        # Garantir que roblox_id é válido
        if not isinstance(roblox_id, int):
            await interaction.followup.send(f"❌ ID do usuário inválido: {roblox_id}")
            return
            
        # Obter informações do usuário
        user_info, success, error = get_user_info_robust(roblox_id)
        if not success:
            await interaction.followup.send(f"❌ Erro ao obter informações: {error}")
            return
        
        # Obter badges do usuário
        badges, success, error = get_user_badges_robust(roblox_id)
        if not success:
            await interaction.followup.send(f"❌ Erro ao obter badges: {error}")
            return
        
        # Obter avatar
        avatar_url, _, _ = get_user_avatar_robust(roblox_id)
        
        # Criar embed
        display_name = user_info.get('displayName', username) if user_info and isinstance(user_info, dict) else username
        embed = discord.Embed(
            title=f"📊 Informações de {display_name}",
            color=0x00B4D8
        )
        
        # Adicionar informações básicas
        embed.add_field(name="👤 Nome", value=display_name, inline=True)
        embed.add_field(name="🆔 ID Roblox", value=str(roblox_id), inline=True)
        embed.add_field(name="🏆 Total de Badges", value=str(len(badges)), inline=True)
        
        # Última badge (mais recente)
        if badges:
            latest_badge = badges[0]  # Badges vêm ordenadas por data (desc)
            badge_info, _, _ = get_badge_info_robust(latest_badge['id'])
            if badge_info:
                badge_date = latest_badge.get('created', 'Data desconhecida')
                embed.add_field(
                    name="🏆 Última Badge", 
                    value=f"**{badge_info.get('displayName', 'Badge Desconhecida')}**\n"
                          f"📅 {badge_date[:10] if len(badge_date) > 10 else badge_date}", 
                    inline=False
                )
        else:
            embed.add_field(name="🏆 Última Badge", value="Nenhuma badge encontrada", inline=False)
        
        # Informações de monitoramento
        embed.add_field(
            name="📋 Monitoramento",
            value=f"Adicionado em: {user_found.get('added_at', 'N/A')[:10]}",
            inline=False
        )
        
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="list", description="Lista todos os usuários monitorados")
async def list_tracked(interaction: discord.Interaction):
    """Comando /list - Lista usuários monitorados"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    if not tracked_users:
        await interaction.response.send_message("📋 Nenhum usuário está sendo monitorado.")
        return
    
    embed = discord.Embed(
        title="📋 Usuários Monitorados",
        color=0x00B4D8,
        description=f"Total: {len(tracked_users)} usuário(s)"
    )
    
    for roblox_id, user_data in tracked_users.items():
        embed.add_field(
            name=f"👤 {user_data['name']}",
            value=f"ID: {roblox_id}\nAdicionado em: {user_data.get('added_at', 'N/A')[:10]}",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setchannel", description="Define o canal onde o bot enviará notificações")
@discord.app_commands.describe(channel="Canal onde as notificações serão enviadas")
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Comando /setchannel - Define canal de notificações"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    try:
        # Verificar se o bot tem permissão para enviar mensagens no canal
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"❌ Não tenho permissão para enviar mensagens em {channel.mention}!"
            )
            return
        
        # Salvar configuração
        bot_config["notification_channel_id"] = channel.id
        save_bot_config()
        
        await interaction.response.send_message(
            f"✅ Canal de notificações configurado para {channel.mention}!\n"
            f"📊 Agora receberei notificações de badges e presença neste canal."
        )
        
        # Reiniciar monitoramento se não estava ativo
        if not monitoring_badge_task.is_running():
            monitoring_badge_task.start()
        if not monitoring_presence_task.is_running():
            monitoring_presence_task.start()
        if not monitoring_groups_task.is_running():
            monitoring_groups_task.start()
            
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {e}")

@bot.tree.command(name="adicionargrupo", description="Adiciona um grupo do Roblox para monitoramento")
@discord.app_commands.describe(group_id="ID do grupo do Roblox para monitorar")
async def add_group(interaction: discord.Interaction, group_id: int):
    """Comando /adicionargrupo - Adiciona grupo ao monitoramento"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Verificar se já está sendo monitorado
        if str(group_id) in tracked_groups:
            await interaction.followup.send(
                f"⚠️ O grupo ID {group_id} já está sendo monitorado!"
            )
            return
        
        # Obter informações do grupo
        group_info, success, error = await asyncio.to_thread(get_group_info_robust, group_id)
        if not success:
            await interaction.followup.send(f"❌ Erro ao obter informações do grupo: {error}")
            return
        
        # Adicionar à lista de grupos monitorados
        tracked_groups[str(group_id)] = {
            "name": group_info.get('name', f'Grupo {group_id}'),
            "member_count": group_info.get('memberCount', 0),
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat()
        }
        save_tracked_groups()
        
        embed = discord.Embed(
            title="✅ Grupo Adicionado ao Monitoramento",
            color=COLORS["success"]
        )
        embed.add_field(name="📋 Nome", value=group_info.get('name'), inline=True)
        embed.add_field(name="🆔 ID", value=str(group_id), inline=True)
        embed.add_field(name="👥 Membros", value=str(group_info.get('memberCount', 0)), inline=True)
        embed.add_field(name="📝 Descrição", value=group_info.get('description', 'Sem descrição')[:100], inline=False)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="adicionarmembros", description="Adiciona todos os membros de um grupo à lista de monitoramento")
@discord.app_commands.describe(group_id="ID do grupo do Roblox", limit="Limite de membros para adicionar (padrão: 100)")
async def add_group_members(interaction: discord.Interaction, group_id: int, limit: int = 100):
    """Comando /adicionarmembros - Adiciona membros do grupo à lista"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    if limit > 500:
        await interaction.followup.send("⚠️ Limite máximo é de 500 membros por vez.")
        return
    
    try:
        # Obter informações do grupo primeiro
        group_info, success, error = await asyncio.to_thread(get_group_info_robust, group_id)
        if not success:
            await interaction.followup.send(f"❌ Erro ao obter informações do grupo: {error}")
            return
        
        # Obter membros do grupo
        members, success, error = await asyncio.to_thread(get_group_members_robust, group_id, limit)
        if not success:
            await interaction.followup.send(f"❌ Erro ao obter membros do grupo: {error}")
            return
        
        if not members:
            await interaction.followup.send("❌ Nenhum membro encontrado no grupo!")
            return
        
        # Adicionar membros à lista de usuários monitorados
        added_count = 0
        already_tracked = 0
        
        for member in members:
            user_id = member.get('user', {}).get('userId')
            username = member.get('user', {}).get('username')
            
            if not user_id or not username:
                continue
            
            if str(user_id) not in tracked_users:
                tracked_users[str(user_id)] = {
                    "name": username,
                    "added_by": interaction.user.id,
                    "added_at": datetime.now().isoformat(),
                    "from_group": group_id,
                    "from_group_name": group_info.get('name', f'Grupo {group_id}')
                }
                added_count += 1
            else:
                already_tracked += 1
        
        save_tracked_users()
        
        embed = discord.Embed(
            title="✅ Membros do Grupo Adicionados",
            color=COLORS["success"]
        )
        embed.add_field(name="📋 Grupo", value=group_info.get('name'), inline=True)
        embed.add_field(name="🆔 ID do Grupo", value=str(group_id), inline=True)
        embed.add_field(name="➕ Adicionados", value=str(added_count), inline=True)
        embed.add_field(name="⚠️ Já Monitorados", value=str(already_tracked), inline=True)
        embed.add_field(name="📊 Total Analisados", value=str(len(members)), inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="grupos", description="Lista todos os grupos monitorados")
async def list_groups(interaction: discord.Interaction):
    """Comando /grupos - Lista grupos monitorados"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
    
    if not tracked_groups:
        await interaction.response.send_message("📋 Nenhum grupo está sendo monitorado.")
        return
    
    embed = discord.Embed(
        title="📋 Grupos Monitorados",
        color=COLORS["info"],
        description=f"Total: {len(tracked_groups)} grupo(s)"
    )
    
    for group_id, group_data in tracked_groups.items():
        embed.add_field(
            name=f"👥 {group_data['name']}",
            value=f"ID: {group_id}\nMembros: {group_data.get('member_count', 'N/A')}\nAdicionado em: {group_data.get('added_at', 'N/A')[:10]}",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

# ====== MONITORAMENTO AUTOMÁTICO ======

@tasks.loop(seconds=CHECK_INTERVAL)
async def monitoring_badge_task():
    """Task de monitoramento de badges"""
    if not tracked_users:
        return
    
    try:
        with monitoring_lock:
            known_badges = load_known_badges()
            
            for roblox_id_str, user_data in tracked_users.items():
                roblox_id = int(roblox_id_str)
                username = user_data['name']
                
                # Obter badges atuais
                current_badges, success, error = get_user_badges_robust(roblox_id)
                if not success:
                    continue
                
                current_badge_ids = set(badge['id'] for badge in current_badges)
                user_known_badges = set(known_badges.get(roblox_id_str, []))
                new_badge_ids = current_badge_ids - user_known_badges
                
                if new_badge_ids:
                    # Obter canal de notificações configurado
                    notification_channel_id = bot_config.get("notification_channel_id") or NOTIFICATION_CHANNEL_ID
                    if notification_channel_id:
                        channel = bot.get_channel(notification_channel_id)
                        if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                            # Obter info do usuário usando execução assíncrona
                            try:
                                user_info, _, _ = await asyncio.to_thread(get_user_info_robust, roblox_id)
                                avatar_url, _, _ = await asyncio.to_thread(get_user_avatar_robust, roblox_id)
                            
                            for badge_id in new_badge_ids:
                                badge_info, success, _ = await asyncio.to_thread(get_badge_info_robust, badge_id)
                            if success and badge_info:
                                embed = discord.Embed(
                                    title="🏆 Nova Badge Conquistada!",
                                    color=0x00FF00,
                                    timestamp=datetime.utcnow()
                                )
                                embed.add_field(name="🏆 Badge", value=badge_info.get('displayName'), inline=True)
                                embed.add_field(name="👤 Usuário", value=username, inline=True)
                                embed.add_field(name="🔗 Link", value=f"[Ver Badge](https://www.roblox.com/badges/{badge_id})", inline=True)
                                
                                if badge_info.get('description'):
                                    embed.description = badge_info['description']
                                if avatar_url:
                                    embed.set_thumbnail(url=avatar_url)
                                
                                await channel.send(embed=embed)
                
                # Atualizar badges conhecidas
                known_badges[roblox_id_str] = list(current_badge_ids)
            
            save_known_badges(known_badges)
            
    except Exception as e:
        print(f"❌ Erro no monitoramento de badges: {e}")

@tasks.loop(seconds=CHECK_INTERVAL)
async def monitoring_presence_task():
    """Task de monitoramento de presença"""
    if not tracked_users:
        return
    
    try:
        with monitoring_lock:
            last_presence = load_last_presence()
            user_ids = [int(uid) for uid in tracked_users.keys()]
            
            # Obter presença atual
            presences, success, error = get_users_presence_robust(user_ids)
            if not success:
                return
            
            for presence in presences:
                user_id = presence.get('userId')
                current_status = presence.get('userPresenceType', 0)
                last_status = last_presence.get(str(user_id), 0)
                
                # Verificar mudança de Offline para Online/Jogo/Studio
                if last_status == 0 and current_status > 0 and NOTIFICATION_CHANNEL_ID:
                    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
                    if channel and hasattr(channel, 'send'):
                        user_data = tracked_users.get(str(user_id))
                        if user_data and user_id:
                            user_info, _, _ = get_user_info_robust(user_id)
                            avatar_url, _, _ = get_user_avatar_robust(user_id)
                            
                            # Definir cor baseada no status
                            colors = {1: 0x00FF00, 2: 0x0099FF, 3: 0xFF9900}
                            color = colors.get(current_status, 0x00FF00)
                            
                            embed = discord.Embed(
                                title="📶 Mudança de Status!",
                                color=color,
                                timestamp=datetime.utcnow()
                            )
                            embed.add_field(name="👤 Usuário", value=user_data['name'], inline=True)
                            embed.add_field(name="📶 Status", value=presence_type_to_text(current_status), inline=True)
                            
                            # Adicionar jogo se estiver jogando
                            place_id = presence.get('placeId')
                            if current_status == 2 and place_id:
                                try:
                                    place_info, success, _ = get_place_info_robust(int(place_id))
                                    if success and place_info:
                                        embed.add_field(name="🎮 Jogo", value=place_info.get('name', 'Jogo Desconhecido'), inline=True)
                                except (ValueError, TypeError):
                                    pass  # Se place_id não for válido, ignora
                            
                            if avatar_url:
                                embed.set_thumbnail(url=avatar_url)
                            
                            await channel.send(embed=embed)
                
                # Atualizar último status conhecido
                last_presence[str(user_id)] = current_status
            
            save_last_presence(last_presence)
            
    except Exception as e:
        print(f"❌ Erro no monitoramento de presença: {e}")

@tasks.loop(seconds=CHECK_INTERVAL * 3)  # Grupos são verificados com menos frequência
async def monitoring_groups_task():
    """Task de monitoramento de grupos"""
    if not tracked_groups:
        return
    
    try:
        with monitoring_lock:
            # Obter canal de notificações
            notification_channel_id = bot_config.get("notification_channel_id") or NOTIFICATION_CHANNEL_ID
            if not notification_channel_id:
                return
            
            channel = bot.get_channel(notification_channel_id)
            if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
                return
            
            for group_id_str, group_data in tracked_groups.items():
                try:
                    group_id = int(group_id_str)
                    old_member_count = group_data.get('member_count', 0)
                    
                    # Obter informações atuais do grupo
                    group_info, success, error = await asyncio.to_thread(get_group_info_robust, group_id)
                    if not success:
                        continue
                    
                    current_member_count = group_info.get('memberCount', 0)
                    
                    # Verificar mudança na quantidade de membros
                    if current_member_count != old_member_count:
                        # Atualizar dados do grupo
                        tracked_groups[group_id_str]['member_count'] = current_member_count
                        
                        # Determinar se aumentou ou diminuiu
                        if current_member_count > old_member_count:
                            change_text = f"📈 +{current_member_count - old_member_count} novos membros"
                            color = COLORS["success"]
                        else:
                            change_text = f"📉 -{old_member_count - current_member_count} membros saíram"
                            color = COLORS["warning"]
                        
                        embed = discord.Embed(
                            title="👥 Mudança na Quantidade de Membros",
                            color=color,
                            timestamp=datetime.utcnow()
                        )
                        embed.add_field(name="📋 Grupo", value=group_data['name'], inline=True)
                        embed.add_field(name="🆔 ID", value=group_id_str, inline=True)
                        embed.add_field(name="📊 Mudança", value=change_text, inline=True)
                        embed.add_field(name="👥 Antes", value=str(old_member_count), inline=True)
                        embed.add_field(name="👥 Agora", value=str(current_member_count), inline=True)
                        
                        await channel.send(embed=embed)
                        
                        # Pequeno delay entre notificações
                        await asyncio.sleep(1)
                        
                except (ValueError, TypeError) as e:
                    print(f"Erro ao processar grupo {group_id_str}: {e}")
                    continue
            
            # Salvar mudanças
            save_tracked_groups()
            
    except Exception as e:
        print(f"❌ Erro no monitoramento de grupos: {e}")

# ====== EXECUÇÃO DO BOT ======

def run_bot(token):
    """Função para executar o bot"""
    try:
        print("🚀 Iniciando bot Discord...")
        bot.run(token)
    except discord.LoginFailure:
        print("❌ Token do bot inválido! Verifique se o token está correto.")
    except discord.HTTPException as e:
        print(f"❌ Erro HTTP ao conectar: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado ao executar o bot: {e}")

if __name__ == "__main__":
    # Você pode definir o token aqui ou usar variável de ambiente
    BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not BOT_TOKEN:
        print("❌ Token do bot não encontrado! Defina a variável DISCORD_BOT_TOKEN")
    else:
        run_bot(BOT_TOKEN)