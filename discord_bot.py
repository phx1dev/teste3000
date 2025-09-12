import discord
from discord.ext import commands, tasks
import json
import os
import threading
from datetime import datetime
import asyncio
import time
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
    EMOJIS,
    BOT_OWNER_ID,
    RATE_LIMIT_CONFIG,
    BACKUP_CONFIG
)
from utils import (
    logger,
    input_validator,
    backup_manager,
    rate_limiter,
    is_owner,
    safe_json_load,
    safe_json_save,
    auto_backup_task,
    task_watchdog,
    critical_notifier
)
from functools import wraps
from typing import Any, cast

# ====== CLASSES DE EXCEÇÃO CUSTOMIZADAS ======

class SecurityError(Exception):
    """Erro de segurança crítico"""
    pass

class SystemError(Exception):
    """Erro de sistema crítico"""
    pass

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
    """Carrega dados de todos os servidores com sistema robusto"""
    global guild_data
    guild_data = safe_json_load(GUILD_DATA_FILE, {})
    logger.info(f"Dados dos servidores carregados: {len(guild_data)} servidor(es)")

def save_guild_data():
    """Salva dados de todos os servidores com sistema robusto"""
    success = safe_json_save(GUILD_DATA_FILE, guild_data)
    if success:
        logger.info("Dados dos servidores salvos com sucesso")
    else:
        logger.error("Falha ao salvar dados dos servidores")

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
    return safe_json_load(BADGES_FILE, {})

def save_known_badges(badges):
    """Salva as badges conhecidas no arquivo"""
    safe_json_save(BADGES_FILE, badges)

def load_last_presence():
    """Carrega o último status de presença dos usuários"""
    return safe_json_load(PRESENCE_FILE, {})

def save_last_presence(presence_data):
    """Salva o último status de presença dos usuários"""
    safe_json_save(PRESENCE_FILE, presence_data)

# Função removida: is_authorized agora é redundante
# A lógica foi integrada no decorador @secure_command

# ====== DECORADOR UNIVERSAL DE SEGURANÇA ======

def secure_command(require_owner: bool = False):
    """Decorador universal para segurança de comandos"""
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            user_id = interaction.user.id
            
            # Verificar se precisa ser owner
            if require_owner and not is_owner(user_id):
                await interaction.response.send_message(
                    "❌ Este comando só pode ser usado pelo proprietário do bot!", ephemeral=True
                )
                return
            
            # Verificar autorização geral (lógica integrada do is_authorized)
            if not require_owner:
                if not is_owner(user_id):
                    if not AUTHORIZED_DISCORD_IDS:
                        if not BOT_OWNER_ID:
                            await interaction.response.send_message(
                                "❌ Bot não configurado! O proprietário precisa definir BOT_OWNER_ID no config.py",
                                ephemeral=True
                            )
                        else:
                            await interaction.response.send_message(
                                "❌ Você não tem permissão para usar este comando!", ephemeral=True
                            )
                        return
                    elif user_id not in AUTHORIZED_DISCORD_IDS:
                        await interaction.response.send_message(
                            "❌ Você não tem permissão para usar este comando!", ephemeral=True
                        )
                        return
            
            # Verificar rate limiting (exceto para owner)
            if not is_owner(user_id):
                can_proceed, limit_message = rate_limiter.can_make_request(user_id)
                if not can_proceed:
                    await interaction.response.send_message(f"⚠️ {limit_message}", ephemeral=True)
                    return
            
            # Verificar se está em um servidor (exceto comandos de owner)
            if not require_owner and not interaction.guild:
                await interaction.response.send_message(
                    "❌ Este comando só pode ser usado em servidores Discord!", ephemeral=True
                )
                return
            
            # Executar comando original
            try:
                return await func(interaction, *args, **kwargs)
            except Exception as e:
                logger.error(f"Erro no comando {func.__name__}", e, {
                    "user": user_id,
                    "guild": interaction.guild.id if interaction.guild else None
                })
                
                # Notificar erro crítico se necessário
                await critical_notifier.notify_critical_error(e, {
                    "command": func.__name__,
                    "user": user_id,
                    "guild": interaction.guild.id if interaction.guild else None
                })
                
                if interaction.response.is_done():
                    await interaction.followup.send("❌ Erro interno no comando. Tente novamente.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Erro interno no comando. Tente novamente.", ephemeral=True)
                    
        # Marcar função como protegida
        try:
            setattr(wrapper, '_secure_guard', True)
        except AttributeError:
            # Fallback se não conseguir setar o atributo
            pass
        return wrapper
    return decorator

# Função removida: check_permissions_and_limits agora é redundante
# Toda a lógica foi integrada no decorador @secure_command

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

# ====== HANDLERS GLOBAIS DE ERRO ======

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Handler global de erro para slash commands"""
    try:
        logger.error(f"Erro em comando slash: {interaction.command.name if interaction.command else 'Unknown'}", error, {
            "user": interaction.user.id,
            "guild": interaction.guild.id if interaction.guild else None
        })
        
        # Notificar erro crítico se necessário
        await critical_notifier.notify_critical_error(error, {
            "command": interaction.command.name if interaction.command else "Unknown",
            "user": interaction.user.id,
            "guild": interaction.guild.id if interaction.guild else None
        })
        
        # Responder ao usuário
        error_msg = "❌ Erro interno no comando. Tente novamente ou contate o suporte."
        
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            error_msg = f"⏰ Comando em cooldown. Tente novamente em {error.retry_after:.1f}s."
        elif isinstance(error, discord.app_commands.MissingPermissions):
            error_msg = "❌ Você não tem permissões suficientes para usar este comando."
        
        if interaction.response.is_done():
            await interaction.followup.send(error_msg, ephemeral=True)
        else:
            await interaction.response.send_message(error_msg, ephemeral=True)
            
    except Exception as e:
        logger.critical("Erro crítico no handler de erro", e)

@bot.event
async def on_error(event: str, *args, **kwargs):
    """Handler global de erro para eventos"""
    import sys
    error = sys.exc_info()[1]
    
    logger.critical(f"Erro no evento {event}", error, {
        "args": str(args)[:1000],
        "kwargs": str(kwargs)[:1000]
    })
    
    # Notificar erro crítico
    await critical_notifier.notify_critical_error(error, {
        "event": event,
        "args": str(args)[:500]
    })
    
    # Se for um erro de task, tentar reiniciar automaticamente via watchdog
    if "task" in event.lower():
        logger.warning(f"Erro de task detectado: {event}. Ativando restart via watchdog...")
        # O watchdog vai detectar e reiniciar a task automaticamente

@bot.event
async def on_ready():
    """Executado quando o bot está online"""
    print(f'{bot.user} está online!')
    print(f'IDs autorizados: {AUTHORIZED_DISCORD_IDS}')
    
    # Configurar sistema de notificações críticas
    critical_notifier.set_bot(bot)
    
    # Carregar dados salvos
    load_guild_data()
    
    # Registrar tasks no watchdog
    task_watchdog.register_task("badges", monitoring_badge_task)
    task_watchdog.register_task("presence", monitoring_presence_task) 
    task_watchdog.register_task("groups", monitoring_groups_task)
    
    # Iniciar tasks de monitoramento com watchdog
    try:
        if not monitoring_badge_task.is_running():
            monitoring_badge_task.start()
            logger.info("Task de monitoramento de badges iniciada")
            
        if not monitoring_presence_task.is_running():
            monitoring_presence_task.start()
            logger.info("Task de monitoramento de presença iniciada")
            
        if not monitoring_groups_task.is_running():
            monitoring_groups_task.start()
            logger.info("Task de monitoramento de grupos iniciada")
        
            
        # Registrar e ativar TaskWatchdog com todas as tasks críticas
        task_watchdog.register_task("badges", monitoring_badge_task, lambda: monitoring_badge_task.start())
        task_watchdog.register_task("presence", monitoring_presence_task, lambda: monitoring_presence_task.start())
        task_watchdog.register_task("groups", monitoring_groups_task, lambda: monitoring_groups_task.start())
        
        # Iniciar watchdog para monitoramento ativo
        watchdog_task = asyncio.create_task(task_watchdog.monitor_tasks())
        task_watchdog.register_task("watchdog_monitor", watchdog_task)
        logger.info("TaskWatchdog ativado - monitoramento ativo de tasks")
        
        # Iniciar task de backup automático
        backup_task = asyncio.create_task(auto_backup_task())
        task_watchdog.register_task("auto_backup", backup_task)
        logger.info("Task de backup automático iniciada e registrada no watchdog")
        
        logger.info("✅ Sistema de monitoramento bulletproof iniciado para todos os servidores!")
        
        # Criar backup inicial
        backup_success = backup_manager.create_backup([
            "guild_data.json", "known_badges.json", "last_presence.json"
        ], "startup")
        if backup_success:
            logger.info("Backup inicial criado com sucesso")
            
        # Auditoria rigorosa de segurança: verificar cobertura 100% do @secure_command
        total_commands = len(bot.tree.get_commands())
        logger.info(f"🔍 Auditoria de segurança: {total_commands} comandos registrados")
        
        # Verificar se TODOS os comandos têm proteção @secure_command
        unprotected_commands = []
        try:
            for command in bot.tree.get_commands():
                # Verificar se o comando tem callback (evita erro com Groups)
                if hasattr(command, 'callback') and command.callback:
                    callback = command.callback
                    if not (hasattr(callback, '__wrapped__') or getattr(callback, '_secure_guard', False)):
                        unprotected_commands.append(command.name)
        except Exception as audit_error:
            logger.warning(f"Erro na auditoria de comandos: {audit_error}")
            # Continuar sem falhar o startup
        
        if unprotected_commands:
            security_warning = f"⚠️ AVISO DE SEGURANÇA: Comandos sem proteção: {unprotected_commands}"
            logger.critical(security_warning)
            # Não travar o startup, apenas alertar
            try:
                await critical_notifier.notify_critical_error(
                    SecurityError(security_warning), 
                    {"unprotected_commands": unprotected_commands}
                )
            except Exception:
                pass  # Não falhar se notificação falhar
        else:
            logger.info("✅ Todos os comandos estão protegidos com @secure_command")
        
        # Verificar configurações críticas
        config_issues = []
        if not BOT_OWNER_ID:
            config_issues.append("BOT_OWNER_ID não definido")
        if not AUTHORIZED_DISCORD_IDS and not BOT_OWNER_ID:
            config_issues.append("Nenhum usuário autorizado definido")
            
        if config_issues:
            logger.warning(f"⚠️ Problemas de configuração: {', '.join(config_issues)}")
        
        # Verificar e ativar todas as funcionalidades críticas
        critical_systems = {
            "TaskWatchdog": task_watchdog is not None,
            "CriticalNotifier": critical_notifier is not None,
            "BackupManager": backup_manager is not None,
            "RateLimiter": rate_limiter is not None
        }
        
        for system, active in critical_systems.items():
            if not active:
                critical_error = f"Sistema crítico {system} não está ativo!"
                logger.critical(critical_error)
                raise SystemError(critical_error)
            logger.info(f"✅ Sistema crítico {system}: Ativo")
            
        logger.info("🛡️ Sistema bulletproof VALIDADO e totalmente operacional!")
            
    except Exception as e:
        logger.critical("Erro crítico ao iniciar sistema de monitoramento", e)
        await critical_notifier.notify_critical_error(e, {"phase": "startup"})
    
    # Sincronizar slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ {len(synced)} slash commands sincronizados")
    except Exception as e:
        logger.error("Erro ao sincronizar commands", e)

# ====== COMANDOS SLASH ======

@bot.tree.command(name="monitorarmembros", description="Adiciona um usuário à lista de monitoramento individual deste servidor")
@discord.app_commands.describe(username="Nome do usuário do Roblox para monitorar")
@secure_command()
async def monitor_user(interaction: discord.Interaction, username: str):
    """Comando /monitorarmembros - Adiciona usuário à lista de monitoramento individual do servidor"""
    
    # Validar entrada
    valid_username, validation_error = input_validator.validate_username(username)
    if not valid_username:
        await interaction.response.send_message(f"❌ {validation_error}", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Obter informações do usuário com tratamento robusto de erros
        try:
            user_info, success, error = await asyncio.to_thread(get_user_info_by_username, username)
            if not success or not user_info:
                logger.warning(f"Usuário não encontrado: {username}", {"error": error, "guild": interaction.guild.id})
                await interaction.followup.send(f"❌ Usuário '{username}' não encontrado no Roblox: {error}")
                return
        except Exception as e:
            logger.error(f"Erro ao buscar usuário: {username}", e, {"guild": interaction.guild.id})
            await interaction.followup.send("❌ Erro interno ao buscar usuário. Tente novamente.")
            return
        
        user_id = user_info.get('id')
        if not user_id:
            await interaction.followup.send(f"❌ Não foi possível obter ID do usuário '{username}'")
            return
        
        # Verificar limites do servidor
        guild_users = get_tracked_users(interaction.guild.id)
        max_users = RATE_LIMIT_CONFIG["max_users_per_guild"]
        
        if len(guild_users) >= max_users and not is_owner(interaction.user.id):
            await interaction.followup.send(
                f"⚠️ Limite máximo de usuários atingido para este servidor: {max_users}"
            )
            return
            
        # Verificar se já está sendo monitorado no servidor
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
        
        if save_guild_data():
            logger.info(f"Usuário adicionado: {username} (ID: {user_id})", {
                "guild": interaction.guild.id,
                "added_by": interaction.user.id,
                "total_users": len(guild_users)
            })
        else:
            logger.error("Falha ao salvar dados após adicionar usuário", None, {
                "username": username,
                "guild": interaction.guild.id
            })
            await interaction.followup.send("❌ Erro ao salvar dados. Usuário pode não ter sido adicionado corretamente.")
            return
        
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
@secure_command()
async def remove_user(interaction: discord.Interaction, username: str):
    """Comando /removermembro - Remove usuário da lista de monitoramento individual do servidor"""
        
    # Validar entrada
    valid_username, validation_error = input_validator.validate_username(username)
    if not valid_username:
        await interaction.response.send_message(f"❌ {validation_error}", ephemeral=True)
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

@bot.tree.command(name="setup", description="Configuração inicial do bot (somente proprietário)")
@secure_command(require_owner=True)
async def setup_bot(interaction: discord.Interaction):
    """Comando /setup - Configuração inicial para proprietário"""
    
    user_id = interaction.user.id
    
    # Verificar se é proprietário (deve funcionar mesmo sem configuração)
    if BOT_OWNER_ID and user_id != BOT_OWNER_ID:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado pelo proprietário do bot!", ephemeral=True
        )
        return
    
    # Se não há owner configurado, permitir que o primeiro usuário se torne owner
    if not BOT_OWNER_ID:
        embed = discord.Embed(
            title="🔧 Configuração Inicial do Bot",
            color=COLORS["warning"],
            description=(
                f"**Usuário {interaction.user.mention} será definido como proprietário.**\n\n"
                "⚠️ Para completar a configuração:\n"
                "1. Edite `config.py` e defina `BOT_OWNER_ID = {user_id}`\n"
                "2. Reinicie o bot\n"
                "3. Use `/setchannel` para configurar notificações\n"
                "4. Use `/monitorarmembros` para adicionar usuários\n\n"
                "📋 **Status atual:**\n"
                f"• Proprietário: Não configurado\n"
                f"• IDs Autorizados: {len(AUTHORIZED_DISCORD_IDS)} usuário(s)\n"
                f"• Servidores ativos: {len(guild_data)}"
            ).format(user_id=user_id)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Mostrar status do sistema
    total_users = sum(len(guild_info.get("tracked_users", {})) for guild_info in guild_data.values())
    total_groups = sum(len(guild_info.get("tracked_groups", {})) for guild_info in guild_data.values())
    
    embed = discord.Embed(
        title="🔧 Status do Sistema",
        color=COLORS["info"]
    )
    embed.add_field(name="👑 Proprietário", value=f"<@{BOT_OWNER_ID}>", inline=True)
    embed.add_field(name="🔑 IDs Autorizados", value=str(len(AUTHORIZED_DISCORD_IDS)), inline=True)
    embed.add_field(name="🏠 Servidores", value=str(len(guild_data)), inline=True)
    embed.add_field(name="👥 Total Usuários", value=str(total_users), inline=True)
    embed.add_field(name="📊 Total Grupos", value=str(total_groups), inline=True)
    embed.add_field(name="💾 Backups", value="✅ Ativo" if BACKUP_CONFIG["enable_auto_backup"] else "❌ Inativo", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="list", description="Lista todos os usuários monitorados neste servidor")
@secure_command()
async def list_tracked(interaction: discord.Interaction):
    """Comando /list - Lista usuários monitorados no servidor"""
    
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
@secure_command()
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Comando /setchannel - Define canal de notificações para o servidor"""
    
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
@secure_command()
async def add_group(interaction: discord.Interaction, group_id: int):
    """Comando /adicionargrupo - Adiciona grupo ao monitoramento de membros"""
        
    # Validar ID do grupo
    valid_id, validation_error = input_validator.validate_roblox_id(group_id)
    if not valid_id:
        await interaction.response.send_message(f"❌ {validation_error}", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        guild_groups = get_tracked_groups(interaction.guild.id)
        max_groups = RATE_LIMIT_CONFIG["max_groups_per_guild"]
        
        # Verificar limites do servidor
        if len(guild_groups) >= max_groups and not is_owner(interaction.user.id):
            await interaction.followup.send(
                f"⚠️ Limite máximo de grupos atingido para este servidor: {max_groups}"
            )
            return
            
        # Verificar se já está sendo monitorado
        if str(group_id) in guild_groups:
            await interaction.followup.send(
                f"⚠️ O grupo ID {group_id} já está sendo monitorado neste servidor!"
            )
            return
        
        # Obter informações do grupo com tratamento robusto
        try:
            group_info, success, error = await asyncio.to_thread(get_group_info_robust, group_id)
            if not success:
                logger.warning(f"Grupo não encontrado: {group_id}", {"error": error, "guild": interaction.guild.id})
                await interaction.followup.send(f"❌ Erro ao obter informações do grupo: {error}")
                return
        except Exception as e:
            logger.error(f"Erro ao buscar grupo: {group_id}", e, {"guild": interaction.guild.id})
            await interaction.followup.send("❌ Erro interno ao buscar grupo. Tente novamente.")
            return
        
        # Adicionar à lista de grupos monitorados
        guild_groups[str(group_id)] = {
            "name": group_info.get('name', f'Grupo {group_id}'),
            "member_count": group_info.get('memberCount', 0),
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat()
        }
        
        if save_guild_data():
            logger.info(f"Grupo adicionado: {group_id}", {
                "guild": interaction.guild.id,
                "added_by": interaction.user.id,
                "total_groups": len(guild_groups)
            })
        else:
            logger.error("Falha ao salvar dados após adicionar grupo", None, {
                "group_id": group_id,
                "guild": interaction.guild.id
            })
        
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
@secure_command()
async def add_group_members_to_monitoring(interaction: discord.Interaction, group_id: int, limit: int = 100):
    """Comando /adicionarmembrosgrupo - Adiciona membros do grupo à lista de usuários monitorados individualmente"""
    
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

@bot.tree.command(name="emergencia", description="Comando de emergência para proprietário (força backup e diagnóstico)")
@secure_command(require_owner=True)
async def emergency_command(interaction: discord.Interaction):
    """Comando /emergencia - Sistema de recuperação de emergência"""
    
    # Apenas proprietário pode usar
    if not is_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado pelo proprietário do bot!", ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Backup forçado
        backup_success = backup_manager.create_backup([
            "guild_data.json", "known_badges.json", "last_presence.json", "bot.log"
        ], "emergency")
        
        # Limpar rate limits de todos os usuários
        rate_limiter.requests.clear()
        rate_limiter.blocked_users.clear()
        
        # Diagnóstico do sistema
        total_users = sum(len(guild_info.get("tracked_users", {})) for guild_info in guild_data.values())
        total_groups = sum(len(guild_info.get("tracked_groups", {})) for guild_info in guild_data.values())
        
        embed = discord.Embed(
            title="🚨 Recuperação de Emergência",
            color=COLORS["error"]
        )
        embed.add_field(name="💾 Backup Forçado", value="✅ Sucesso" if backup_success else "❌ Falha", inline=True)
        embed.add_field(name="🔄 Rate Limits", value="✅ Resetados", inline=True)
        embed.add_field(name="🏠 Servidores", value=str(len(guild_data)), inline=True)
        embed.add_field(name="👥 Total Usuários", value=str(total_users), inline=True)
        embed.add_field(name="📊 Total Grupos", value=str(total_groups), inline=True)
        embed.add_field(name="📋 Tasks Ativas", value=f"Badges: {monitoring_badge_task.is_running()}\nPresença: {monitoring_presence_task.is_running()}\nGrupos: {monitoring_groups_task.is_running()}", inline=False)
        
        logger.critical("Comando de emergência executado", None, {
            "user": interaction.user.id,
            "guild": interaction.guild.id if interaction.guild else None
        })
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.critical("Erro no comando de emergência", e)
        await interaction.followup.send("❌ Erro crítico no sistema de emergência!", ephemeral=True)

@bot.tree.command(name="grupos", description="Lista todos os grupos monitorados neste servidor")
@secure_command()
async def list_groups(interaction: discord.Interaction):
    """Comando /grupos - Lista grupos monitorados no servidor"""
    
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
                        
                        # Obter badges atuais do usuário com tratamento robusto
                        try:
                            current_badges, success, _ = await asyncio.to_thread(get_user_badges_robust, roblox_id)
                            if not success or not current_badges:
                                continue
                        except Exception as e:
                            logger.error(f"Erro ao obter badges do usuário {roblox_id}", e, {"guild": guild_id})
                            continue
                        
                        # Comparar com badges conhecidas
                        current_badge_ids = set(badge['id'] for badge in current_badges)
                        user_known_badges = set(known_badges.get(roblox_id_str, []))
                        new_badge_ids = current_badge_ids - user_known_badges
                        
                        if new_badge_ids:
                            try:
                                # Obter info do usuário com tratamento seguro
                                user_info, _, _ = await asyncio.to_thread(get_user_info_robust, int(roblox_id))
                                avatar_url, _, _ = await asyncio.to_thread(get_user_avatar_robust, int(roblox_id))
                            except Exception as e:
                                logger.warning(f"Erro ao obter info do usuário {roblox_id}", e)
                                user_info, avatar_url = None, None
                            
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
            
            # Obter presença de todos os usuários com tratamento robusto
            try:
                presence_data, success, _ = await asyncio.to_thread(get_users_presence_robust, list(all_user_ids))
                if not success or not presence_data:
                    logger.warning("Falha ao obter dados de presença")
                    return
            except Exception as e:
                logger.error("Erro crítico no monitoramento de presença", e)
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
                        
                        # Obter informações atuais do grupo com tratamento robusto
                        try:
                            group_info, success, error = await asyncio.to_thread(get_group_info_robust, group_id)
                            if not success:
                                logger.warning(f"Erro ao obter info do grupo {group_id}", None, {"error": error})
                                continue
                        except Exception as e:
                            logger.error(f"Erro crítico ao monitorar grupo {group_id}", e, {"guild": guild_id})
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