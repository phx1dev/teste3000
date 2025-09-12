"""
Utilitários de API melhorados para sistema de tracking confiável
"""
import requests
import time
import random
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
import threading

class RateLimiter:
    """Controla rate limiting para APIs do Roblox"""
    
    def __init__(self):
        self.last_calls = {}
        self.lock = threading.Lock()
        
        # Rate limits por endpoint (calls per minute)
        self.limits = {
            'badges': 60,      # 60 calls/minute para badges API
            'presence': 120,   # 120 calls/minute para presence API
            'users': 600,      # 600 calls/minute para users API
            'places': 600,     # 600 calls/minute para places API
            'groups': 600      # 600 calls/minute para groups API
        }
    
    def wait_if_needed(self, endpoint: str):
        """Aguarda se necessário para respeitar rate limits"""
        with self.lock:
            now = time.time()
            
            if endpoint not in self.last_calls:
                self.last_calls[endpoint] = []
            
            # Limpar calls antigas (últimos 60 segundos)
            self.last_calls[endpoint] = [
                call_time for call_time in self.last_calls[endpoint]
                if now - call_time < 60
            ]
            
            limit = self.limits.get(endpoint, 60)
            
            if len(self.last_calls[endpoint]) >= limit:
                # Calcular tempo de espera
                oldest_call = min(self.last_calls[endpoint])
                wait_time = 60 - (now - oldest_call) + 0.1
                
                if wait_time > 0:
                    print(f"⏳ Rate limit: aguardando {wait_time:.1f}s para {endpoint}")
                    time.sleep(wait_time)
            
            # Registrar esta chamada
            self.last_calls[endpoint].append(time.time())

class APIClient:
    """Cliente de API melhorado com retry logic e tratamento robusto de erros"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.session = requests.Session()
        
        # Configurar headers padrão
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        # Cache para reduzir chamadas desnecessárias
        self.cache = {}
        self.cache_ttl = {}
        
        # Estatísticas
        self.stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'cache_hits': 0,
            'retries': 0
        }
    
    def _is_cache_valid(self, key: str, ttl_minutes: int = 5) -> bool:
        """Verifica se cache é válido"""
        if key not in self.cache or key not in self.cache_ttl:
            return False
        
        cache_time = self.cache_ttl[key]
        return datetime.now() - cache_time < timedelta(minutes=ttl_minutes)
    
    def _set_cache(self, key: str, data: Any):
        """Define cache"""
        self.cache[key] = data
        self.cache_ttl[key] = datetime.now()
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """Obtém do cache"""
        return self.cache.get(key)
    
    def make_request(
        self,
        url: str,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        max_retries: int = 3,
        cache_ttl: int = 0,
        timeout: int = 15
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Faz request com retry logic e tratamento de erros
        
        Returns:
            (sucesso, dados, erro)
        """
        
        # Verificar cache se habilitado
        if cache_ttl > 0:
            cache_key = f"{url}:{json.dumps(params, sort_keys=True) if params else ''}"
            if self._is_cache_valid(cache_key, cache_ttl):
                self.stats['cache_hits'] += 1
                return True, self._get_cache(cache_key), None
        
        # Rate limiting
        self.rate_limiter.wait_if_needed(endpoint)
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                self.stats['total_calls'] += 1
                
                if attempt > 0:
                    self.stats['retries'] += 1
                    # Backoff exponencial com jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"🔄 Retry {attempt}/{max_retries} em {wait_time:.1f}s para {url}")
                    time.sleep(wait_time)
                
                # Fazer request
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=timeout)
                elif method.upper() == 'POST':
                    response = self.session.post(url, params=params, json=json_data, timeout=timeout)
                else:
                    raise ValueError(f"Método HTTP não suportado: {method}")
                
                # Verificar status code
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.stats['successful_calls'] += 1
                        
                        # Salvar no cache se habilitado
                        if cache_ttl > 0:
                            cache_key = f"{url}:{json.dumps(params, sort_keys=True) if params else ''}"
                            self._set_cache(cache_key, data)
                        
                        return True, data, None
                        
                    except json.JSONDecodeError as e:
                        last_error = f"Erro ao decodificar JSON: {e}"
                        print(f"⚠️  {last_error}")
                        continue
                        
                elif response.status_code == 429:  # Rate limited
                    last_error = "Rate limit atingido"
                    print(f"⚠️  {last_error}, aguardando...")
                    time.sleep(60)  # Aguardar 1 minuto
                    continue
                    
                elif response.status_code in [500, 502, 503, 504]:  # Server errors
                    last_error = f"Erro do servidor: {response.status_code}"
                    print(f"⚠️  {last_error}, tentando novamente...")
                    continue
                    
                else:
                    last_error = f"Status code inesperado: {response.status_code}"
                    # Para outros erros, não tentar novamente
                    break
                    
            except requests.exceptions.Timeout:
                last_error = "Timeout na requisição"
                print(f"⏰ {last_error}")
                continue
                
            except requests.exceptions.ConnectionError:
                last_error = "Erro de conexão"
                print(f"🔌 {last_error}")
                continue
                
            except Exception as e:
                last_error = f"Erro inesperado: {e}"
                print(f"❌ {last_error}")
                continue
        
        # Se chegou aqui, todas as tentativas falharam
        self.stats['failed_calls'] += 1
        return False, None, last_error
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cliente"""
        total = self.stats['total_calls']
        success_rate = (self.stats['successful_calls'] / total * 100) if total > 0 else 0
        
        return {
            **self.stats,
            'success_rate': round(success_rate, 2),
            'cache_entries': len(self.cache)
        }

# Instância global do cliente
api_client = APIClient()

def get_user_badges_robust(user_id: int) -> Tuple[List[Dict], bool, Optional[str]]:
    """
    Versão robusta para obter badges do usuário
    Returns: (badges, sucesso, erro)
    """
    try:
        url = f"https://badges.roblox.com/v1/users/{user_id}/badges"
        all_badges = []
        cursor = None
        error_count = 0
        max_errors = 3
        
        while True:
            params = {
                'limit': 100,
                'sortOrder': 'Desc'
            }
            
            if cursor:
                params['cursor'] = cursor
            
            success, data, error = api_client.make_request(
                url, 'badges', params=params, 
                max_retries=2, timeout=20
            )
            
            if not success:
                error_count += 1
                print(f"❌ Erro ao obter badges do usuário {user_id} (tentativa {error_count}): {error}")
                
                if error_count >= max_errors:
                    return [], False, f"Falhou após {max_errors} tentativas: {error}"
                
                # Aguardar antes de tentar novamente
                time.sleep(2)
                continue
            
            if not data or 'data' not in data:
                return [], False, "Resposta da API inválida"
            
            batch_badges = data.get('data', [])
            if not batch_badges:
                break
                
            all_badges.extend(batch_badges)
            print(f"    🔗 API Badges: +{len(batch_badges)} badges obtidas (total: {len(all_badges)})")
            
            cursor = data.get('nextPageCursor')
            if not cursor:
                break
            
            # Pequeno delay entre páginas para evitar rate limit
            time.sleep(0.1)
        
        return all_badges, True, None
        
    except Exception as e:
        return [], False, f"Erro inesperado: {e}"

def get_users_presence_robust(user_ids: List[int]) -> Tuple[List[Dict], bool, Optional[str]]:
    """
    Versão robusta para obter presença dos usuários
    Returns: (presenças, sucesso, erro)
    """
    try:
        url = "https://presence.roblox.com/v1/presence/users"
        
        success, data, error = api_client.make_request(
            url, 'presence', method='POST',
            json_data={"userIds": user_ids},
            max_retries=3, timeout=15
        )
        
        if not success:
            return [], False, error
        
        if not data or 'userPresences' not in data:
            return [], False, "Resposta da API inválida"
        
        presences = data.get('userPresences', [])
        print(f"    🔗 API Presença: {len(presences)} usuários retornados")
        
        # Debug detalhado
        for presence in presences:
            user_id = presence.get('userId')
            status = presence.get('userPresenceType', 0)
            status_text = {0: "Offline", 1: "Online", 2: "Em Jogo", 3: "No Studio"}.get(status, "Desconhecido")
            print(f"    🔍 Debug: Usuário {user_id} = Status {status} ({status_text})")
        
        return presences, True, None
        
    except Exception as e:
        return [], False, f"Erro inesperado: {e}"

def get_user_info_robust(user_id: int) -> Tuple[Optional[Dict], bool, Optional[str]]:
    """
    Versão robusta para obter informações do usuário
    Returns: (info, sucesso, erro)
    """
    try:
        url = f"https://users.roblox.com/v1/users/{user_id}"
        
        success, data, error = api_client.make_request(
            url, 'users', cache_ttl=10,  # Cache por 10 minutos
            max_retries=2, timeout=10
        )
        
        if not success:
            return None, False, error
        
        if not data or 'id' not in data:
            return None, False, "Resposta da API inválida"
        
        return data, True, None
        
    except Exception as e:
        return None, False, f"Erro inesperado: {e}"

def get_user_avatar_robust(user_id: int) -> Tuple[Optional[str], bool, Optional[str]]:
    """
    Versão robusta para obter avatar do usuário
    Returns: (avatar_url, sucesso, erro)
    """
    try:
        url = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
        params = {
            'userIds': user_id,
            'size': '150x150',
            'format': 'Png',
            'isCircular': False
        }
        
        success, data, error = api_client.make_request(
            url, 'users', params=params,
            cache_ttl=30,  # Cache por 30 minutos
            max_retries=2, timeout=10
        )
        
        if not success:
            return None, False, error
        
        if not data or 'data' not in data or not data['data']:
            return None, False, "Resposta da API inválida"
        
        avatar_url = data['data'][0].get('imageUrl')
        return avatar_url, True, None
        
    except Exception as e:
        return None, False, f"Erro inesperado: {e}"

def get_badge_info_robust(badge_id: int) -> Tuple[Optional[Dict], bool, Optional[str]]:
    """
    Versão robusta para obter informações da badge
    Returns: (info, sucesso, erro)
    """
    try:
        url = f"https://badges.roblox.com/v1/badges/{badge_id}"
        
        success, data, error = api_client.make_request(
            url, 'badges', cache_ttl=60,  # Cache por 1 hora
            max_retries=2, timeout=10
        )
        
        if not success:
            return None, False, error
        
        if not data or 'id' not in data:
            return None, False, "Resposta da API inválida"
        
        return data, True, None
        
    except Exception as e:
        return None, False, f"Erro inesperado: {e}"

def get_place_info_robust(place_id: int) -> Tuple[Optional[Dict], bool, Optional[str]]:
    """
    Versão robusta para obter informações do place/jogo
    Returns: (info, sucesso, erro)
    """
    try:
        url = "https://games.roblox.com/v1/games/multiget-place-details"
        params = {'placeIds': str(place_id)}
        
        success, data, error = api_client.make_request(
            url, 'places', params=params,
            cache_ttl=60,  # Cache por 1 hora
            max_retries=2, timeout=10
        )
        
        if not success:
            return None, False, error
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None, False, "Resposta da API inválida"
        
        place_info = data[0]
        place_name = place_info.get('name', 'Nome não encontrado')
        print(f"    🎮 Jogo encontrado: {place_name}")
        
        return place_info, True, None
        
    except Exception as e:
        return None, False, f"Erro inesperado: {e}"

def get_group_info_robust(group_id: int) -> Tuple[Optional[Dict], bool, Optional[str]]:
    """
    Versão robusta para obter informações do grupo
    Returns: (info, sucesso, erro)
    """
    try:
        url = f"https://groups.roblox.com/v1/groups/{group_id}"
        
        success, data, error = api_client.make_request(
            url, 'groups', cache_ttl=30,  # Cache por 30 minutos
            max_retries=2, timeout=10
        )
        
        if not success:
            return None, False, error
        
        if not data or 'id' not in data:
            return None, False, "Resposta da API inválida"
        
        return data, True, None
        
    except Exception as e:
        return None, False, f"Erro inesperado: {e}"

def get_group_members_robust(group_id: int, limit: int = 100) -> Tuple[List[Dict], bool, Optional[str]]:
    """
    Versão robusta para obter membros do grupo
    Usa a API de roles para obter membros de todos os papéis
    Returns: (membros, sucesso, erro)
    """
    try:
        # Primeiro obter todos os roles do grupo
        roles_url = f"https://groups.roblox.com/v1/groups/{group_id}/roles"
        
        success, roles_data, error = api_client.make_request(
            roles_url, 'groups', max_retries=2, timeout=10
        )
        
        if not success:
            return [], False, error
        
        if not roles_data or 'roles' not in roles_data:
            return [], False, "Não foi possível obter roles do grupo"
        
        all_members = []
        unique_members = {}  # Para evitar duplicatas
        
        # Iterar através de cada role
        for role in roles_data['roles']:
            role_id = role.get('id')
            if not role_id:
                continue
            
            # Obter membros deste role
            members_url = f"https://groups.roblox.com/v1/groups/{group_id}/roles/{role_id}/users"
            cursor = None
            
            while len(all_members) < limit:
                params = {
                    'limit': min(100, limit - len(all_members)),
                    'sortOrder': 'Asc'
                }
                
                if cursor:
                    params['cursor'] = cursor
                
                success, data, error = api_client.make_request(
                    members_url, 'groups', params=params,
                    max_retries=2, timeout=15
                )
                
                if not success:
                    print(f"Erro ao obter membros do role {role_id}: {error}")
                    break
                
                if not data or 'data' not in data:
                    break
                
                batch_members = data.get('data', [])
                if not batch_members:
                    break
                
                # Adicionar membros únicos
                for member in batch_members:
                    user_id = member.get('userId')
                    if user_id and user_id not in unique_members:
                        unique_members[user_id] = {
                            'user': {
                                'userId': user_id,
                                'username': member.get('username', f'User{user_id}'),
                                'displayName': member.get('displayName', member.get('username', f'User{user_id}'))
                            },
                            'role': {
                                'id': role_id,
                                'name': role.get('name', 'Unknown Role'),
                                'rank': role.get('rank', 0)
                            }
                        }
                        all_members.append(unique_members[user_id])
                        
                        if len(all_members) >= limit:
                            break
                
                cursor = data.get('nextPageCursor')
                if not cursor:
                    break
                
                # Pequeno delay para evitar rate limit
                time.sleep(0.1)
                
                if len(all_members) >= limit:
                    break
            
            if len(all_members) >= limit:
                break
            
            # Delay entre roles para evitar rate limiting
            time.sleep(0.2)
        
        return all_members, True, None
        
    except Exception as e:
        return [], False, f"Erro inesperado: {e}"

def print_api_stats():
    """Imprime estatísticas das APIs"""
    stats = api_client.get_stats()
    print(f"📊 Estatísticas da API:")
    print(f"   📞 Total de chamadas: {stats['total_calls']}")
    print(f"   ✅ Chamadas bem-sucedidas: {stats['successful_calls']}")
    print(f"   ❌ Chamadas falharam: {stats['failed_calls']}")
    print(f"   🔄 Tentativas de retry: {stats['retries']}")
    print(f"   💾 Cache hits: {stats['cache_hits']}")
    print(f"   📈 Taxa de sucesso: {stats['success_rate']}%")
    print(f"   🗃️  Entradas no cache: {stats['cache_entries']}")