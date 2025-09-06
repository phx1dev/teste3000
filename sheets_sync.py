"""
Módulo de sincronização automática com Google Sheets
Sincroniza usuários do grupo "Comunidade Civil" a cada 20 minutos
"""

import gspread
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class SheetsSync:
    def __init__(self, credentials_file: str = "credentials.json", 
                 spreadsheet_url: str = "https://docs.google.com/spreadsheets/d/14XWmdfTkK5CWD4bKUgssFbwcZf_ICpsaqY3-BG6wAhY/edit?usp=sharing"):
        """
        Inicializa o sistema de sincronização com Google Sheets
        
        Args:
            credentials_file: Caminho para o arquivo JSON de credenciais
            spreadsheet_url: URL da planilha do Google Sheets
        """
        self.credentials_file = credentials_file
        self.spreadsheet_url = spreadsheet_url
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.client = None
        self.sheet = None
        self.sync_interval = 20 * 60  # 20 minutos em segundos
        self.is_running = False
        self.last_sync = None
        self.sync_count = 0
        
        # Callback para notificar mudanças no sistema principal
        self.on_users_changed = None
        
        print("📊 Inicializando sistema de sincronização Google Sheets...")
    
    def authenticate(self) -> bool:
        """Autentica e conecta com Google Sheets"""
        try:
            # Carrega credenciais
            credentials = Credentials.from_service_account_file(
                self.credentials_file, scopes=self.scopes)
            
            # Cria cliente
            self.client = gspread.authorize(credentials)
            
            # Abre planilha
            self.sheet = self.client.open_by_url(self.spreadsheet_url).sheet1
            
            print("✅ Autenticação Google Sheets realizada com sucesso")
            print(f"📋 Planilha conectada: {self.sheet.title}")
            
            return True
            
        except FileNotFoundError:
            print(f"❌ Arquivo de credenciais não encontrado: {self.credentials_file}")
            return False
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ Planilha não encontrada ou sem permissão: {self.spreadsheet_url}")
            return False
        except Exception as e:
            print(f"❌ Erro na autenticação Google Sheets: {e}")
            return False
    
    def read_sheet_data(self) -> List[Dict]:
        """
        Lê dados da planilha (IDs e status dos usuários)
        
        Returns:
            Lista de dicionários com 'user_id' e 'status'
        """
        try:
            if not self.sheet:
                print("❌ Planilha não conectada")
                return []
            
            # Lê dados das colunas A e B (A1:B20)
            data_range = self.sheet.get('A1:B20')
            
            users_data = []
            for i, row in enumerate(data_range):
                # Pula linha de cabeçalho se existir
                if i == 0 and (not row or not row[0].isdigit()):
                    continue
                
                # Verifica se a linha tem dados válidos
                if not row or len(row) < 2:
                    continue
                
                user_id_str = str(row[0]).strip()
                status = str(row[1]).strip().upper()
                
                # Valida ID do usuário (deve ser numérico)
                try:
                    user_id = int(user_id_str)
                except (ValueError, TypeError):
                    continue
                
                # Valida status (deve ser ATIVO ou INATIVO)
                if status not in ['ATIVO', 'INATIVO']:
                    continue
                
                users_data.append({
                    'user_id': user_id,
                    'status': status
                })
            
            print(f"    📊 {len(users_data)} usuário(s) encontrado(s) na planilha")
            
            return users_data
            
        except Exception as e:
            print(f"❌ Erro ao ler dados da planilha: {e}")
            return []
    
    def sync_users(self, current_group_config: Dict) -> Optional[Dict]:
        """
        Sincroniza usuários da planilha com a configuração atual
        
        Args:
            current_group_config: Configuração atual do grupo "Comunidade Civil"
            
        Returns:
            Nova configuração do grupo ou None se não houve mudanças
        """
        try:
            # Lê dados da planilha
            sheet_users = self.read_sheet_data()
            if not sheet_users:
                print("    ⚠️ Nenhum usuário válido encontrado na planilha")
                return None
            
            # Lista atual de usuários do grupo
            current_users = set(current_group_config.get('users', []))
            
            # Lista de usuários da planilha (apenas os ativos)
            sheet_active_users = {user['user_id'] for user in sheet_users if user['status'] == 'ATIVO'}
            sheet_all_users = {user['user_id'] for user in sheet_users}
            
            # Calcula mudanças
            users_to_add = sheet_active_users - current_users
            users_to_remove = current_users - sheet_all_users
            users_to_deactivate = {user['user_id'] for user in sheet_users 
                                 if user['status'] == 'INATIVO' and user['user_id'] in current_users}
            
            # Aplica mudanças
            new_users = current_users.copy()
            changes_made = False
            
            # Adiciona novos usuários ativos
            if users_to_add:
                new_users.update(users_to_add)
                changes_made = True
                print(f"    ➕ Adicionando {len(users_to_add)} usuário(s): {list(users_to_add)}")
            
            # Remove usuários que não estão mais na planilha
            if users_to_remove:
                new_users -= users_to_remove
                changes_made = True
                print(f"    ➖ Removendo {len(users_to_remove)} usuário(s): {list(users_to_remove)}")
            
            # Remove usuários inativos
            if users_to_deactivate:
                new_users -= users_to_deactivate
                changes_made = True
                print(f"    🚫 Desativando {len(users_to_deactivate)} usuário(s): {list(users_to_deactivate)}")
            
            if not changes_made:
                print("    ✅ Nenhuma alteração necessária")
                return None
            
            # Cria nova configuração
            new_config = current_group_config.copy()
            new_config['users'] = list(new_users)
            
            print(f"    🔄 Sincronização concluída: {len(current_users)} → {len(new_users)} usuários")
            
            return new_config
            
        except Exception as e:
            print(f"❌ Erro durante sincronização: {e}")
            return None
    
    def sync_loop(self, get_current_config_callback, update_config_callback):
        """
        Loop principal de sincronização (roda a cada 20 minutos)
        
        Args:
            get_current_config_callback: Função para obter configuração atual
            update_config_callback: Função para atualizar configuração
        """
        print("🔄 Iniciando loop de sincronização Google Sheets...")
        print(f"⏰ Intervalo de sincronização: {self.sync_interval // 60} minutos")
        
        # Primeira sincronização imediata após 30 segundos
        time.sleep(30)
        
        while self.is_running:
            try:
                self.sync_count += 1
                print(f"\\n📊 [SHEETS SYNC #{self.sync_count}] Executando sincronização... ({datetime.now().strftime('%H:%M:%S')})")
                
                # Obtém configuração atual do grupo "Comunidade Civil"
                current_groups = get_current_config_callback()
                if "Comunidade Civil" not in current_groups:
                    print("    ⚠️ Grupo 'Comunidade Civil' não encontrado")
                    time.sleep(self.sync_interval)
                    continue
                
                current_config = current_groups["Comunidade Civil"]
                
                # Executa sincronização
                new_config = self.sync_users(current_config)
                
                if new_config:
                    # Atualiza configuração
                    new_groups = current_groups.copy()
                    new_groups["Comunidade Civil"] = new_config
                    
                    # Aplica mudanças
                    success = update_config_callback(new_groups)
                    
                    if success:
                        print("    ✅ Configuração atualizada com sucesso")
                        self.last_sync = datetime.now()
                        
                        # Notifica callback se definido
                        if self.on_users_changed:
                            self.on_users_changed("Comunidade Civil", new_config['users'])
                    else:
                        print("    ❌ Falha ao atualizar configuração")
                else:
                    self.last_sync = datetime.now()
                
                print(f"    ⏰ Próxima sincronização em {self.sync_interval // 60} minutos...")
                
            except Exception as e:
                print(f"❌ Erro no loop de sincronização: {e}")
            
            # Aguarda próximo ciclo
            time.sleep(self.sync_interval)
        
        print("🛑 Loop de sincronização Google Sheets finalizado")
    
    def start(self, get_current_config_callback, update_config_callback):
        """
        Inicia o sistema de sincronização
        
        Args:
            get_current_config_callback: Função para obter configuração atual dos grupos
            update_config_callback: Função para atualizar configuração dos grupos
        """
        if self.is_running:
            print("⚠️ Sincronização já está em execução")
            return False
        
        # Autentica primeiro
        if not self.authenticate():
            print("❌ Falha na autenticação, sincronização não iniciada")
            return False
        
        # Marca como em execução
        self.is_running = True
        
        # Inicia thread de sincronização
        sync_thread = threading.Thread(
            target=self.sync_loop, 
            args=(get_current_config_callback, update_config_callback),
            daemon=True,
            name="SheetsSync"
        )
        sync_thread.start()
        
        print("✅ Sistema de sincronização Google Sheets iniciado")
        return True
    
    def stop(self):
        """Para o sistema de sincronização"""
        self.is_running = False
        print("🛑 Parando sistema de sincronização Google Sheets...")
    
    def get_status(self) -> Dict:
        """Retorna status atual do sistema de sincronização"""
        return {
            'running': self.is_running,
            'sync_count': self.sync_count,
            'last_sync': self.last_sync.strftime('%H:%M:%S %d/%m/%Y') if self.last_sync else None,
            'next_sync_in_minutes': self.sync_interval // 60,
            'authenticated': self.client is not None
        }


# Instância global para uso no sistema principal
sheets_sync = SheetsSync()