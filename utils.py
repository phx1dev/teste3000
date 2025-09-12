"""
Utilitários para o bot Discord Roblox Monitor
Sistema robusto de logging, validação e backup
"""

import json
import os
import time
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Tuple
from logging.handlers import RotatingFileHandler
import asyncio
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

from config import LOGGING_CONFIG, BACKUP_CONFIG, RATE_LIMIT_CONFIG, BOT_OWNER_ID

# ====== SISTEMA DE LOGGING ======

class RobustLogger:
    """Sistema de logging robusto com rotação e múltiplos destinos"""
    
    def __init__(self, name: str = "RobloxBot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOGGING_CONFIG["log_level"]))
        
        # Evitar duplicar handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Configura handlers de logging"""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Handler para arquivo com rotação
        file_handler = RotatingFileHandler(
            LOGGING_CONFIG["log_file"],
            maxBytes=LOGGING_CONFIG["max_log_size"],
            backupCount=LOGGING_CONFIG["backup_count"]
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str, extra_data: Optional[Dict] = None):
        """Log de informação com dados extras opcionais"""
        if extra_data:
            message += f" | Dados: {json.dumps(extra_data, default=str)}"
        self.logger.info(message)
    
    def warning(self, message: str, extra_data: Optional[Dict] = None):
        """Log de aviso"""
        if extra_data:
            message += f" | Dados: {json.dumps(extra_data, default=str)}"
        self.logger.warning(message)
    
    def error(self, message: str, error: Optional[BaseException] = None, extra_data: Optional[Dict] = None):
        """Log de erro com traceback"""
        if error:
            message += f" | Erro: {str(error)}"
            if LOGGING_CONFIG["log_level"] == "DEBUG":
                message += f" | Traceback: {traceback.format_exc()}"
        if extra_data:
            message += f" | Dados: {json.dumps(extra_data, default=str)}"
        self.logger.error(message)
    
    def critical(self, message: str, error: Optional[BaseException] = None, extra_data: Optional[Dict] = None):
        """Log crítico - também pode enviar para Discord"""
        if error:
            message += f" | Erro Crítico: {str(error)}"
            message += f" | Traceback: {traceback.format_exc()}"
        if extra_data:
            message += f" | Dados: {json.dumps(extra_data, default=str)}"
        self.logger.critical(message)

# Instância global do logger
logger = RobustLogger()

# ====== SISTEMA DE VALIDAÇÃO ======

class InputValidator:
    """Validador robusto de entrada"""
    
    @staticmethod
    def validate_discord_id(user_id: Union[str, int]) -> Tuple[bool, Optional[str]]:
        """Valida ID do Discord"""
        try:
            user_id = int(user_id)
            if user_id <= 0 or user_id >= 2**63:
                return False, "ID do Discord deve ser um número positivo válido"
            return True, None
        except (ValueError, TypeError):
            return False, "ID do Discord deve ser um número"
    
    @staticmethod
    def validate_roblox_id(user_id: Union[str, int]) -> Tuple[bool, Optional[str]]:
        """Valida ID do Roblox"""
        try:
            user_id = int(user_id)
            if user_id <= 0 or user_id >= 10**15:  # Roblox IDs são menores
                return False, "ID do Roblox deve ser um número positivo válido"
            return True, None
        except (ValueError, TypeError):
            return False, "ID do Roblox deve ser um número"
    
    @staticmethod
    def validate_username(username: str) -> Tuple[bool, Optional[str]]:
        """Valida username do Roblox"""
        if not isinstance(username, str):
            return False, "Username deve ser uma string"
        
        username = username.strip()
        if len(username) < 3 or len(username) > 20:
            return False, "Username deve ter entre 3 e 20 caracteres"
        
        # Roblox permite apenas letras, números e underscore
        if not all(c.isalnum() or c == '_' for c in username):
            return False, "Username deve conter apenas letras, números e underscore"
        
        return True, None
    
    @staticmethod
    def validate_limit(limit: Union[str, int], max_limit: int = 500) -> Tuple[bool, Optional[str], int]:
        """Valida limite numérico"""
        try:
            limit = int(limit)
            if limit <= 0:
                return False, "Limite deve ser maior que zero", 0
            if limit > max_limit:
                return False, f"Limite máximo permitido: {max_limit}", 0
            return True, None, limit
        except (ValueError, TypeError):
            return False, "Limite deve ser um número", 0

# ====== SISTEMA DE BACKUP ======

class BackupManager:
    """Gerenciador robusto de backups"""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = backup_dir
        self.ensure_backup_dir()
    
    def ensure_backup_dir(self):
        """Garante que o diretório de backup existe"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            logger.info(f"Diretório de backup criado: {self.backup_dir}")
    
    def create_backup(self, files_to_backup: List[str], reason: str = "manual") -> bool:
        """Cria backup dos arquivos especificados"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{reason}_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            os.makedirs(backup_path, exist_ok=True)
            
            backed_up_files = []
            for file_path in files_to_backup:
                if os.path.exists(file_path):
                    backup_file_path = os.path.join(backup_path, os.path.basename(file_path))
                    shutil.copy2(file_path, backup_file_path)
                    backed_up_files.append(file_path)
            
            if backed_up_files:
                logger.info(f"Backup criado: {backup_name}", {
                    "files": backed_up_files,
                    "reason": reason,
                    "path": backup_path
                })
                self._cleanup_old_backups()
                return True
            else:
                logger.warning(f"Nenhum arquivo encontrado para backup: {files_to_backup}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao criar backup: {reason}", e)
            return False
    
    def _cleanup_old_backups(self):
        """Remove backups antigos mantendo apenas os mais recentes"""
        try:
            backups = []
            for item in os.listdir(self.backup_dir):
                backup_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(backup_path):
                    stat = os.stat(backup_path)
                    backups.append((backup_path, stat.st_mtime))
            
            backups.sort(key=lambda x: x[1], reverse=True)
            
            max_backups = BACKUP_CONFIG["max_backup_files"]
            if len(backups) > max_backups:
                for backup_path, _ in backups[max_backups:]:
                    shutil.rmtree(backup_path)
                    logger.info(f"Backup antigo removido: {backup_path}")
                    
        except Exception as e:
            logger.error("Erro ao limpar backups antigos", e)

# ====== SISTEMA DE RATE LIMITING ======

class RateLimiter:
    """Limitador de taxa para proteger contra abuso"""
    
    def __init__(self):
        self.requests = {}  # {user_id: [(timestamp, count), ...]}
        self.blocked_users = {}  # {user_id: unblock_timestamp}
    
    def can_make_request(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Verifica se o usuário pode fazer uma requisição"""
        current_time = time.time()
        
        # Verificar se o usuário está bloqueado
        if user_id in self.blocked_users:
            unblock_time = self.blocked_users[user_id]
            if current_time < unblock_time:
                remaining = int(unblock_time - current_time)
                return False, f"Você está temporariamente bloqueado. Tente novamente em {remaining} segundos."
            else:
                del self.blocked_users[user_id]
        
        # Limpar requisições antigas (mais de 1 minuto)
        if user_id in self.requests:
            self.requests[user_id] = [
                req for req in self.requests[user_id]
                if current_time - req[0] < 60
            ]
        
        # Contar requisições no último minuto
        user_requests = self.requests.get(user_id, [])
        total_requests = sum(req[1] for req in user_requests)
        
        max_requests = RATE_LIMIT_CONFIG["max_requests_per_minute"]
        
        if total_requests >= max_requests:
            # Bloquear usuário por 5 minutos
            self.blocked_users[user_id] = current_time + 300
            return False, f"Muitas requisições! Limite: {max_requests}/min. Bloqueado por 5 minutos."
        
        # Registrar nova requisição
        if user_id not in self.requests:
            self.requests[user_id] = []
        self.requests[user_id].append((current_time, 1))
        
        return True, None
    
    def clear_user_limits(self, user_id: int):
        """Limpa limites de um usuário (para owners/admins)"""
        self.requests.pop(user_id, None)
        self.blocked_users.pop(user_id, None)
        logger.info(f"Limites de rate limiting removidos para usuário {user_id}")

# ====== UTILITÁRIOS GERAIS ======

def is_owner(user_id: int) -> bool:
    """Verifica se o usuário é o owner do bot"""
    return bool(BOT_OWNER_ID and user_id == BOT_OWNER_ID)

def safe_json_load(file_path: str, default: Optional[Dict] = None) -> Dict:
    """Carrega JSON com tratamento seguro de erros"""
    if default is None:
        default = {}
    
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logger.info(f"Arquivo não existe, usando padrão: {file_path}")
            return default.copy()
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Erro ao carregar {file_path}, usando padrão", e)
        
        # Tentar backup automático do arquivo corrompido
        if os.path.exists(file_path):
            backup_path = f"{file_path}.corrupted_{int(time.time())}"
            try:
                shutil.copy2(file_path, backup_path)
                logger.info(f"Arquivo corrompido salvo como backup: {backup_path}")
            except Exception as backup_error:
                logger.error("Erro ao fazer backup do arquivo corrompido", backup_error)
        
        return default.copy()

def safe_json_save(file_path: str, data: Dict) -> bool:
    """Salva JSON com escrita atômica e tratamento seguro de erros"""
    try:
        # Criar backup antes de salvar
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
        
        # Salvar com escrita atômica (temp + rename)
        temp_path = f"{file_path}.tmp_{int(time.time())}"
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            # Garantir que os dados foram escritos no disco
            f.flush()
            os.fsync(f.fileno())
        
        
        # Mover arquivo temporário para o final (operação atômica)
        if os.name == 'nt':  # Windows
            if os.path.exists(file_path):
                os.remove(file_path)
        os.rename(temp_path, file_path)
        
        logger.info(f"Dados salvos com sucesso (atômico): {file_path}")
        return True
        
    except (IOError, TypeError) as e:
        logger.error(f"Erro ao salvar {file_path}", e)
        
        # Limpar arquivo temporário se existir
        temp_path = f"{file_path}.tmp_{int(time.time())}"
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        
        # Tentar restaurar backup se existir
        backup_path = f"{file_path}.backup"
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, file_path)
                logger.info(f"Backup restaurado: {file_path}")
            except Exception as restore_error:
                logger.error("Erro ao restaurar backup", restore_error)
        
        return False
        
# ====== SISTEMA DE WATCHDOG PARA TASKS ======

class TaskWatchdog:
    """Monitora e reinicia tasks que falharam"""
    
    def __init__(self):
        self.monitored_tasks = {}
        self.restart_counts = {}
        self.max_restarts = 5
        self.backoff_time = 30  # Segundos
    
    def register_task(self, task_name: str, task_obj=None, restart_func=None):
        """Registra uma task para monitoramento com capacidade de restart"""
        self.monitored_tasks[task_name] = {
            "task": task_obj,
            "restart_func": restart_func or (lambda: task_obj.start() if task_obj else None)
        }
        self.restart_counts[task_name] = 0
        logger.info(f"Task registrada no watchdog: {task_name}")
    
    def restart_task(self, task_name: str):
        """Reinicia uma task monitorada"""
        if task_name not in self.monitored_tasks:
            logger.error(f"Task não registrada: {task_name}")
            return False
            
        try:
            task_info = self.monitored_tasks[task_name]
            restart_func = task_info.get("restart_func")
            if restart_func:
                restart_func()
                logger.info(f"Task reiniciada: {task_name}")
                return True
        except Exception as e:
            logger.error(f"Erro ao reiniciar task {task_name}", e)
            
        return False
    
    async def monitor_tasks(self):
        """Loop de monitoramento de tasks"""
        while True:
            try:
                await asyncio.sleep(60)  # Verificar a cada minuto
                
                for task_name, task_info in self.monitored_tasks.items():
                    task = task_info["task"]
                    
                    if task and not task.is_running() and self.restart_counts[task_name] < self.max_restarts:
                        logger.warning(f"Task parada detectada: {task_name}. Reiniciando...")
                        
                        # Backoff exponencial
                        wait_time = self.backoff_time * (2 ** self.restart_counts[task_name])
                        await asyncio.sleep(min(wait_time, 300))  # Máx 5 minutos
                        
                        if self.restart_task(task_name):
                            self.restart_counts[task_name] += 1
                        else:
                            logger.error(f"Falha ao reiniciar task {task_name} após {self.restart_counts[task_name]} tentativas")
                            
            except Exception as e:
                logger.error("Erro no watchdog de tasks", e)
                await asyncio.sleep(60)

# Instância global do watchdog
task_watchdog = TaskWatchdog()

# ====== SISTEMA DE NOTIFICAÇÕES CRÍTICAS ======

class CriticalNotifier:
    """Sistema para notificar erros críticos via Discord"""
    
    def __init__(self):
        self.bot = None
        self.error_count = 0
        self.last_notification = 0
        self.cooldown = 300  # 5 minutos entre notificações
    
    def set_bot(self, bot_instance):
        """Define a instância do bot"""
        self.bot = bot_instance
    
    async def notify_critical_error(self, error: BaseException, context: Optional[Dict] = None):
        """Notifica erro crítico para proprietário"""
        # Sempre fazer backup em erro crítico se configurado
        if BACKUP_CONFIG.get("backup_on_critical_error", False):
            try:
                backup_manager.create_backup([
                    "guild_data.json", "known_badges.json", "last_presence.json", "bot.log"
                ], f"critical_error_{int(time.time())}")
                logger.info("Backup automático criado devido a erro crítico")
            except Exception as backup_error:
                logger.error("Falha ao criar backup de emergência", backup_error)
        
        if not LOGGING_CONFIG.get("log_errors_to_discord", False):
            return
            
        current_time = time.time()
        
        # Cooldown para evitar spam
        if current_time - self.last_notification < self.cooldown:
            return
            
        if not self.bot or not BOT_OWNER_ID:
            logger.warning("CriticalNotifier: Bot ou BOT_OWNER_ID não configurado para DMs")
            return
            
        try:
            owner = self.bot.get_user(BOT_OWNER_ID)
            if not owner:
                return
                
            self.error_count += 1
            
            # Import discord localmente para evitar problemas de dependência circular
            try:
                import discord
                from datetime import datetime as dt_import
            except ImportError:
                logger.error("Discord.py não está disponível para envio de DM")
                return
            
            embed = discord.Embed(
                title="🚨 Erro Crítico no Bot",
                color=0xFF0000,
                timestamp=dt_import.utcnow()
            )
            embed.add_field(name="Erro", value=str(error)[:1000], inline=False)
            
            if context:
                context_str = json.dumps(context, default=str, indent=2)[:1000]
                embed.add_field(name="Contexto", value=f"```json\n{context_str}\n```", inline=False)
                
            embed.add_field(name="Contador", value=str(self.error_count), inline=True)
            embed.footer.text = "Use /emergencia para diagnóstico completo"
            
            await owner.send(embed=embed)
            self.last_notification = current_time
            
        except Exception as notify_error:
            logger.error("Erro ao enviar notificação crítica", notify_error)

# Instâncias globais
critical_notifier = CriticalNotifier()
# Instâncias globais dos sistemas
input_validator = InputValidator()
backup_manager = BackupManager()
rate_limiter = RateLimiter()
task_watchdog = TaskWatchdog()

# ====== AUTO BACKUP ======

async def auto_backup_task():
    """Task automática de backup"""
    if not BACKUP_CONFIG["enable_auto_backup"]:
        return
    
    interval_seconds = BACKUP_CONFIG["backup_interval_hours"] * 3600
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            
            files_to_backup = [
                "guild_data.json",
                "known_badges.json", 
                "last_presence.json",
                "bot.log"
            ]
            
            success = backup_manager.create_backup(files_to_backup, "auto")
            if success:
                logger.info("Backup automático realizado com sucesso")
            else:
                logger.warning("Falha no backup automático")
                
        except Exception as e:
            logger.error("Erro na task de backup automático", e)
            await asyncio.sleep(60)  # Esperar 1 minuto antes de tentar novamente