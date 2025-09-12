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
    get_user_info_by_username,
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

def save_known_badges(badges):
    """Salva as badges conhecidas no arquivo"""
    with open(BADGES_FILE, 'w') as f:
        json.dump(badges, f, indent=2)

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

def is_authorized(user_id: int) -> bool:
    """Verifica se o usuário tem permissão para usar os comandos"""
    return user_id in AUTHORIZED_DISCORD_IDS

def presence_type_to_text(presence_type: int) -> str:
    """Converte código de presença para texto"""
    presence_map = {
        0: "📴 Offline",
        1: "🟢 Online", 
        2: "🎮 Jogando",
        3: "🛠️ Studio"
    }
    return presence_map.get(presence_type, "❓ Desconhecido")

def get_notification_channel(guild_id: int):
    """Obtém o canal de notificações para o servidor"""
    config = get_guild_config(guild_id)
    channel_id = config.get("notification_channel_id") or NOTIFICATION_CHANNEL_ID
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
            return channel
    return None

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
        print(f"✅ {len(synced)} slash commands sincronizados")
    except Exception as e:
        print(f"❌ Erro ao sincronizar commands: {e}")

# ====== COMANDOS SLASH ======

@bot.tree.command(name="monitorarmembros", description="Adiciona um usuário à lista de monitoramento individual deste servidor")
@discord.app_commands.describe(username="Nome do usuário do Roblox para monitorar")
async def monitor_user(interaction: discord.Interaction, username: str):
    """Comando /monitorarmembros - Adiciona usuário à lista de monitoramento individual do servidor"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
        
    # Verificar se está em um servidor
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Obter informações do usuário usando execução assíncrona
        user_info, success, error = await asyncio.to_thread(get_user_info_by_username, username)
        if not success or not user_info:
            await interaction.followup.send(f"❌ Usuário '{username}' não encontrado no Roblox: {error}")
            return
        
        user_id = user_info.get('id')
        if not user_id:
            await interaction.followup.send(f"❌ Não foi possível obter ID do usuário '{username}'")
            return
        
        # Verificar se já está sendo monitorado no servidor
        guild_users = get_tracked_users(interaction.guild.id)
        if str(user_id) in guild_users:
            await interaction.followup.send(
                f"⚠️ O usuário **{user_info.get('name')}** já está sendo monitorado neste servidor!"
            )
            return
        
        # Adicionar à lista de usuários monitorados do servidor
        guild_users[str(user_id)] = {
            "name": user_info.get('name'),
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat()
        }
        save_guild_data()
        
        embed = discord.Embed(
            title="✅ Usuário Adicionado ao Monitoramento",
            color=COLORS["success"]
        )
        embed.add_field(name="👤 Usuário", value=user_info.get('name'), inline=True)
        embed.add_field(name="🆔 ID", value=str(user_id), inline=True)
        embed.add_field(name="📊 Total monitorados neste servidor", value=str(len(guild_users)), inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="removermembro", description="Remove um usuário da lista de monitoramento individual deste servidor")
@discord.app_commands.describe(username="Nome do usuário do Roblox para remover")
async def remove_user(interaction: discord.Interaction, username: str):
    """Comando /removermembro - Remove usuário da lista de monitoramento individual do servidor"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
        
    # Verificar se está em um servidor
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Obter informações do usuário
        user_info, success, error = await asyncio.to_thread(get_user_info_by_username, username)
        if not success or not user_info:
            await interaction.followup.send(f"❌ Usuário '{username}' não encontrado no Roblox: {error}")
            return
        
        user_id = user_info.get('id')
        guild_users = get_tracked_users(interaction.guild.id)
        
        if str(user_id) not in guild_users:
            await interaction.followup.send(
                f"⚠️ O usuário **{user_info.get('name')}** não estava sendo monitorado neste servidor!"
            )
            return
        
        # Remover da lista
        del guild_users[str(user_id)]
        save_guild_data()
        
        embed = discord.Embed(
            title="✅ Usuário Removido do Monitoramento",
            color=COLORS["warning"]
        )
        embed.add_field(name="👤 Usuário", value=user_info.get('name'), inline=True)
        embed.add_field(name="🆔 ID", value=str(user_id), inline=True)
        embed.add_field(name="📊 Total monitorados neste servidor", value=str(len(guild_users)), inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="list", description="Lista todos os usuários monitorados neste servidor")
async def list_tracked(interaction: discord.Interaction):
    """Comando /list - Lista usuários monitorados no servidor"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
        
    # Verificar se está em um servidor
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
        )
        return
    
    guild_users = get_tracked_users(interaction.guild.id)
    
    if not guild_users:
        await interaction.response.send_message(
            f"📋 Nenhum usuário está sendo monitorado neste servidor.\n"
            f"Use `/monitorarmembros <username>` para adicionar usuários."
        )
        return
    
    embed = discord.Embed(
        title="📋 Usuários Monitorados",
        color=COLORS["info"],
        description=f"**Servidor:** {interaction.guild.name}\n**Total:** {len(guild_users)} usuário(s)"
    )
    
    for roblox_id, user_data in guild_users.items():
        embed.add_field(
            name=f"👤 {user_data['name']}",
            value=f"ID: {roblox_id}\nAdicionado: {user_data.get('added_at', 'N/A')[:10]}",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setchannel", description="Define o canal onde o bot enviará notificações")
@discord.app_commands.describe(channel="Canal onde as notificações serão enviadas")
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Comando /setchannel - Define canal de notificações para o servidor"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
        
    # Verificar se está em um servidor
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
        )
        return
    
    try:
        # Verificar se o bot tem permissão para enviar mensagens no canal
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"❌ Não tenho permissão para enviar mensagens em {channel.mention}!"
            )
            return
        
        # Salvar configuração para este servidor
        config = get_guild_config(interaction.guild.id)
        config["notification_channel_id"] = channel.id
        save_guild_data()
        
        embed = discord.Embed(
            title="✅ Canal Configurado",
            color=COLORS["success"]
        )
        embed.add_field(name="📢 Canal", value=channel.mention, inline=True)
        embed.add_field(name="🏠 Servidor", value=interaction.guild.name, inline=True)
        embed.description = "Agora receberei notificações de badges e presença neste canal."
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {e}")

@bot.tree.command(name="adicionargrupo", description="Adiciona um grupo do Roblox para monitorar mudanças de membros")
@discord.app_commands.describe(group_id="ID do grupo do Roblox para monitorar")
async def add_group(interaction: discord.Interaction, group_id: int):
    """Comando /adicionargrupo - Adiciona grupo ao monitoramento de membros"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
        
    # Verificar se está em um servidor
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        guild_groups = get_tracked_groups(interaction.guild.id)
        
        # Verificar se já está sendo monitorado
        if str(group_id) in guild_groups:
            await interaction.followup.send(
                f"⚠️ O grupo ID {group_id} já está sendo monitorado neste servidor!"
            )
            return
        
        # Obter informações do grupo
        group_info, success, error = await asyncio.to_thread(get_group_info_robust, group_id)
        if not success:
            await interaction.followup.send(f"❌ Erro ao obter informações do grupo: {error}")
            return
        
        # Adicionar à lista de grupos monitorados
        guild_groups[str(group_id)] = {
            "name": group_info.get('name', f'Grupo {group_id}'),
            "member_count": group_info.get('memberCount', 0),
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat()
        }
        save_guild_data()
        
        embed = discord.Embed(
            title="✅ Grupo Adicionado ao Monitoramento",
            color=COLORS["success"]
        )
        embed.add_field(name="📋 Nome", value=group_info.get('name'), inline=True)
        embed.add_field(name="🆔 ID", value=str(group_id), inline=True)
        embed.add_field(name="👥 Membros", value=str(group_info.get('memberCount', 0)), inline=True)
        embed.add_field(name="🏠 Servidor", value=interaction.guild.name, inline=False)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="adicionarmembrosgrupo", description="Adiciona membros de um grupo à lista de monitoramento individual")
@discord.app_commands.describe(group_id="ID do grupo do Roblox", limit="Limite de membros (padrão: 100, máximo: 500)")
async def add_group_members_to_monitoring(interaction: discord.Interaction, group_id: int, limit: int = 100):
    """Comando /adicionarmembrosgrupo - Adiciona membros do grupo à lista de usuários monitorados individualmente"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
        
    # Verificar se está em um servidor
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
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
        guild_users = get_tracked_users(interaction.guild.id)
        added_count = 0
        already_tracked = 0
        
        for member in members:
            user_id = member.get('user', {}).get('userId')
            username = member.get('user', {}).get('username')
            
            if not user_id or not username:
                continue
            
            if str(user_id) not in guild_users:
                guild_users[str(user_id)] = {
                    "name": username,
                    "added_by": interaction.user.id,
                    "added_at": datetime.now().isoformat(),
                    "from_group": group_id,
                    "from_group_name": group_info.get('name', f'Grupo {group_id}')
                }
                added_count += 1
            else:
                already_tracked += 1
        
        save_guild_data()
        
        embed = discord.Embed(
            title="✅ Membros Adicionados ao Monitoramento Individual",
            color=COLORS["success"]
        )
        embed.add_field(name="📋 Grupo", value=group_info.get('name'), inline=True)
        embed.add_field(name="🏠 Servidor", value=interaction.guild.name, inline=True)
        embed.add_field(name="➕ Adicionados", value=str(added_count), inline=True)
        embed.add_field(name="⚠️ Já Monitorados", value=str(already_tracked), inline=True)
        embed.add_field(name="📊 Total Analisados", value=str(len(members)), inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {e}")

@bot.tree.command(name="grupos", description="Lista todos os grupos monitorados neste servidor")
async def list_groups(interaction: discord.Interaction):
    """Comando /grupos - Lista grupos monitorados no servidor"""
    
    # Verificar autorização
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!", ephemeral=True
        )
        return
        
    # Verificar se está em um servidor
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
        )
        return
    
    guild_groups = get_tracked_groups(interaction.guild.id)
    
    if not guild_groups:
        await interaction.response.send_message(
            f"📋 Nenhum grupo está sendo monitorado neste servidor.\n"
            f"Use `/adicionargrupo <id>` para adicionar grupos."
        )
        return
    
    embed = discord.Embed(
        title="📋 Grupos Monitorados",
        color=COLORS["info"],
        description=f"**Servidor:** {interaction.guild.name}\n**Total:** {len(guild_groups)} grupo(s)"
    )
    
    for group_id, group_data in guild_groups.items():
        embed.add_field(
            name=f"👥 {group_data['name']}",
            value=f"ID: {group_id}\nMembros: {group_data.get('member_count', 'N/A')}\nAdicionado: {group_data.get('added_at', 'N/A')[:10]}",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

# ====== MONITORAMENTO AUTOMÁTICO ======

@tasks.loop(seconds=CHECK_INTERVAL)
async def monitoring_badge_task():
    """Task de monitoramento de badges para todos os servidores"""
    try:
        with monitoring_lock:
            known_badges = load_known_badges()
            
            # Iterar através de todos os servidores
            for guild_id, guild_info in guild_data.items():
                guild_users = guild_info.get("tracked_users", {})
                if not guild_users:
                    continue
                    
                # Verificar canal de notificações
                channel = get_notification_channel(int(guild_id))
                if not channel:
                    continue
                
                for roblox_id_str, user_data in guild_users.items():
                    try:
                        roblox_id = int(roblox_id_str)
                        
                        # Obter badges atuais do usuário
                        current_badges, success, _ = await asyncio.to_thread(get_user_badges_robust, roblox_id)
                        if not success or not current_badges:
                            continue
                        
                        # Comparar com badges conhecidas
                        current_badge_ids = set(badge['id'] for badge in current_badges)
                        user_known_badges = set(known_badges.get(roblox_id_str, []))
                        new_badge_ids = current_badge_ids - user_known_badges
                        
                        if new_badge_ids:
                            # Obter info do usuário
                            user_info, _, _ = await asyncio.to_thread(get_user_info_robust, int(roblox_id))
                            avatar_url, _, _ = await asyncio.to_thread(get_user_avatar_robust, int(roblox_id))
                            
                            for badge_id in new_badge_ids:
                                badge_info, success, _ = await asyncio.to_thread(get_badge_info_robust, badge_id)
                                if success and badge_info:
                                    embed = discord.Embed(
                                        title="🏆 Nova Badge Conquistada!",
                                        color=COLORS["badge"],
                                        timestamp=datetime.utcnow()
                                    )
                                    embed.add_field(name="👤 Usuário", value=user_data['name'], inline=True)
                                    embed.add_field(name="🏆 Badge", value=badge_info.get('name', 'Badge Desconhecida'), inline=True)
                                    embed.add_field(name="🏠 Servidor", value=channel.guild.name, inline=True)
                                    
                                    if badge_info.get('description'):
                                        embed.add_field(name="📝 Descrição", value=badge_info['description'][:100], inline=False)
                                    
                                    if avatar_url:
                                        embed.set_thumbnail(url=avatar_url)
                                    
                                    await channel.send(embed=embed)
                                    await asyncio.sleep(1)  # Delay entre notificações
                        
                        # Atualizar badges conhecidas
                        known_badges[roblox_id_str] = list(current_badge_ids)
                        
                    except (ValueError, TypeError):
                        continue
            
            # Salvar badges conhecidas
            save_known_badges(known_badges)
            
    except Exception as e:
        print(f"❌ Erro no monitoramento de badges: {e}")

@tasks.loop(seconds=CHECK_INTERVAL)
async def monitoring_presence_task():
    """Task de monitoramento de presença para todos os servidores"""
    try:
        with monitoring_lock:
            last_presence = load_last_presence()
            
            # Coletar todos os usuários únicos de todos os servidores
            all_user_ids = set()
            guild_user_map = {}  # {user_id: [guild_ids]}
            
            for guild_id, guild_info in guild_data.items():
                guild_users = guild_info.get("tracked_users", {})
                for user_id in guild_users.keys():
                    all_user_ids.add(int(user_id))
                    if user_id not in guild_user_map:
                        guild_user_map[user_id] = []
                    guild_user_map[user_id].append(guild_id)
            
            if not all_user_ids:
                return
            
            # Obter presença de todos os usuários de uma vez
            presence_data, success, _ = await asyncio.to_thread(get_users_presence_robust, list(all_user_ids))
            if not success or not presence_data:
                return
            
            # Processar mudanças de presença
            for presence in presence_data.get('userPresences', []):
                user_id = presence.get('userId')
                if not user_id:
                    continue
                
                current_status = presence.get('userPresenceType', 0)
                last_status = last_presence.get(str(user_id), 0)
                
                # Verificar mudança de Offline para Online/Jogo/Studio
                if last_status == 0 and current_status > 0:
                    # Notificar em todos os servidores que monitoram este usuário
                    for guild_id in guild_user_map.get(str(user_id), []):
                        try:
                            channel = get_notification_channel(int(guild_id))
                            if not channel:
                                continue
                                
                            guild_users = get_tracked_users(int(guild_id))
                            user_data = guild_users.get(str(user_id))
                            if not user_data:
                                continue
                            
                            # Obter avatar do usuário
                            avatar_url, _, _ = await asyncio.to_thread(get_user_avatar_robust, int(user_id))
                            
                            color = COLORS["online"] if current_status == 1 else COLORS["gaming"]
                            
                            embed = discord.Embed(
                                title="📶 Usuário Online!",
                                color=color,
                                timestamp=datetime.utcnow()
                            )
                            embed.add_field(name="👤 Usuário", value=user_data['name'], inline=True)
                            embed.add_field(name="📶 Status", value=presence_type_to_text(current_status), inline=True)
                            embed.add_field(name="🏠 Servidor", value=channel.guild.name, inline=True)
                            
                            # Adicionar jogo se estiver jogando
                            place_id = presence.get('placeId')
                            if current_status == 2 and place_id:
                                try:
                                    place_info, success, _ = await asyncio.to_thread(get_place_info_robust, int(place_id))
                                    if success and place_info:
                                        embed.add_field(name="🎮 Jogo", value=place_info.get('name', 'Jogo Desconhecido'), inline=True)
                                except (ValueError, TypeError):
                                    pass
                            
                            if avatar_url:
                                embed.set_thumbnail(url=avatar_url)
                            
                            await channel.send(embed=embed)
                            
                        except Exception as e:
                            print(f"Erro ao notificar presença no servidor {guild_id}: {e}")
                
                # Atualizar último status conhecido
                last_presence[str(user_id)] = current_status
            
            save_last_presence(last_presence)
            
    except Exception as e:
        print(f"❌ Erro no monitoramento de presença: {e}")

@tasks.loop(seconds=CHECK_INTERVAL * 3)  # Grupos são verificados com menos frequência
async def monitoring_groups_task():
    """Task de monitoramento de grupos para todos os servidores"""
    try:
        with monitoring_lock:
            # Iterar através de todos os servidores
            for guild_id, guild_info in guild_data.items():
                guild_groups = guild_info.get("tracked_groups", {})
                if not guild_groups:
                    continue
                    
                # Verificar canal de notificações
                channel = get_notification_channel(int(guild_id))
                if not channel:
                    continue
                
                for group_id_str, group_data in guild_groups.items():
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
                            group_data['member_count'] = current_member_count
                            
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
                            embed.add_field(name="🏠 Servidor", value=channel.guild.name, inline=True)
                            embed.add_field(name="📊 Mudança", value=change_text, inline=True)
                            embed.add_field(name="👥 Antes", value=str(old_member_count), inline=True)
                            embed.add_field(name="👥 Agora", value=str(current_member_count), inline=True)
                            
                            await channel.send(embed=embed)
                            await asyncio.sleep(1)  # Pequeno delay entre notificações
                            
                    except (ValueError, TypeError) as e:
                        print(f"Erro ao processar grupo {group_id_str} no servidor {guild_id}: {e}")
                        continue
            
            # Salvar mudanças
            save_guild_data()
            
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
    BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not BOT_TOKEN:
        print("❌ Token do bot não encontrado! Defina a variável DISCORD_BOT_TOKEN")
    else:
        run_bot(BOT_TOKEN)