"""
Configurações do Bot Discord para monitoramento Roblox
Edite este arquivo para configurar o bot de acordo com suas necessidades
"""

# ====== CONFIGURAÇÕES DO BOT ======

# IDs do Discord autorizados a usar os comandos do bot
# IMPORTANTE: Substitua pelos IDs reais dos usuários autorizados
AUTHORIZED_DISCORD_IDS = [
    # Exemplos (substitua pelos IDs reais):
    # 123456789012345678,  # ID do primeiro usuário autorizado
    # 987654321098765432,  # ID do segundo usuário autorizado
    # Para obter seu ID: Settings > Advanced > Developer Mode > Right click no usuário > Copy ID
]

# Canal onde o bot enviará notificações automáticas de badges e presença
# IMPORTANTE: Substitua pelo ID do canal onde quer receber notificações
NOTIFICATION_CHANNEL_ID = None  # Exemplo: 1234567890123456789

# Intervalo de checagem em segundos (recomendado: 30-60 segundos)
CHECK_INTERVAL = 30

# ====== COMO CONFIGURAR ======

"""
1. OBTER TOKEN DO BOT:
   - Vá em https://discord.com/developers/applications
   - Crie uma nova aplicação ou selecione uma existente
   - Vá em "Bot" no menu lateral
   - Copie o token e configure como variável de ambiente: DISCORD_BOT_TOKEN

2. CONFIGURAR IDs AUTORIZADOS:
   - No Discord, ative o Developer Mode: Settings > Advanced > Developer Mode
   - Clique com botão direito no usuário e selecione "Copy ID"
   - Adicione o ID na lista AUTHORIZED_DISCORD_IDS acima

3. CONFIGURAR CANAL DE NOTIFICAÇÕES:
   - Clique com botão direito no canal desejado
   - Selecione "Copy ID"
   - Substitua NOTIFICATION_CHANNEL_ID pelo ID copiado

4. PERMISSÕES DO BOT:
   O bot precisa das seguintes permissões:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Read Message History

5. CONVIDAR BOT PARA SERVIDOR:
   - Na página do bot no Discord Developer Portal
   - Vá em "OAuth2" > "URL Generator"
   - Selecione "bot" e "applications.commands"
   - Selecione as permissões necessárias
   - Use a URL gerada para convidar o bot
"""

# ====== CONFIGURAÇÕES AVANÇADAS ======

# Mensagens de resposta personalizadas
MESSAGES = {
    "unauthorized": "❌ Você não tem permissão para usar este comando!",
    "user_not_found": "❌ Usuário '{}' não encontrado no Roblox!",
    "already_tracked": "⚠️ O usuário '{}' já está sendo monitorado!",
    "user_added": "✅ Usuário '{}' (ID: {}) adicionado à lista de monitoramento!",
    "user_not_tracked": "❌ Usuário '{}' não está na lista de monitoramento!",
    "user_removed": "✅ Usuário '{}' removido da lista de monitoramento!",
    "no_tracked_users": "📋 Nenhum usuário está sendo monitorado.",
    "invalid_user_id": "❌ ID do usuário inválido: {}",
    "api_error": "❌ Erro ao obter {}: {}",
    "no_badges": "Nenhuma badge encontrada"
}

# Cores dos embeds Discord (em hexadecimal)
COLORS = {
    "info": 0x00B4D8,      # Azul para informações
    "success": 0x00FF00,   # Verde para sucessos
    "warning": 0xFF9900,   # Laranja para avisos
    "error": 0xFF0000,     # Vermelho para erros
    "badge": 0x00FF00,     # Verde para novas badges
    "online": 0x00FF00,    # Verde para online
    "playing": 0x0099FF,   # Azul para jogando
    "studio": 0xFF9900     # Laranja para Roblox Studio
}

# Emojis usados nas mensagens (pode personalizar)
EMOJIS = {
    "trophy": "🏆",
    "user": "👤",
    "id": "🆔",
    "link": "🔗",
    "info": "📊",
    "list": "📋",
    "game": "🎮",
    "status": "📶",
    "calendar": "📅",
    "success": "✅",
    "warning": "⚠️",
    "error": "❌",
    "offline": "⭕",
    "online": "🟢",
    "playing": "🔵",
    "studio": "🟠"
}