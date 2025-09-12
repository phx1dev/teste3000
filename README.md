# Bot Discord - Monitor de Badges e Presença Roblox

Bot do Discord desenvolvido para monitorar badges e presença de usuários do Roblox, com comandos slash para gerenciamento e notificações automáticas.

## ✨ Funcionalidades

- 🏆 **Monitoramento de Badges**: Detecta automaticamente novas badges conquistadas
- 📶 **Monitoramento de Presença**: Notifica quando usuários ficam online/jogando
- 🎮 **Comandos Slash**: Interface moderna com comandos `/track`, `/removetrack`, `/view` e `/list`
- 🔒 **Sistema de Permissões**: Apenas usuários autorizados podem usar os comandos
- 📊 **Informações Detalhadas**: Visualize última badge obtida e estatísticas dos usuários
- 🚀 **Deploy Automático**: Pronto para hospedar no Railway

## 🚀 Configuração Rápida

### 1. Criar Bot no Discord

1. Vá em [Discord Developer Portal](https://discord.com/developers/applications)
2. Clique em "New Application" e dê um nome ao seu bot
3. Vá em "Bot" no menu lateral
4. Clique em "Reset Token" e copie o token
5. Guarde o token com segurança (você vai precisar dele)

### 2. Configurar Permissões

No Discord Developer Portal, vá em "OAuth2 > URL Generator":
- Selecione `bot` e `applications.commands`
- Marque as permissões:
  - Send Messages
  - Use Slash Commands
  - Embed Links
  - Read Message History
- Use a URL gerada para convidar o bot ao seu servidor

### 3. Configurar IDs Autorizados

1. No Discord, ative Developer Mode: `Settings > Advanced > Developer Mode`
2. Clique com botão direito no seu usuário e selecione "Copy ID"
3. Edite o arquivo `config.py` e adicione seu ID na lista `AUTHORIZED_DISCORD_IDS`

```python
AUTHORIZED_DISCORD_IDS = [
    123456789012345678,  # Substitua pelo seu ID
    987654321098765432   # IDs de outros usuários autorizados
]
```

### 4. Configurar Canal de Notificações

1. Clique com botão direito no canal onde quer receber notificações
2. Selecione "Copy ID"
3. No arquivo `config.py`, substitua `NOTIFICATION_CHANNEL_ID` pelo ID copiado

## 🎮 Comandos Disponíveis

- `/track <username>` - Adiciona um usuário à lista de monitoramento
- `/removetrack <username>` - Remove um usuário da lista de monitoramento
- `/view <username>` - Mostra informações detalhadas e última badge do usuário
- `/list` - Lista todos os usuários sendo monitorados

## 🚂 Deploy no Railway

### 1. Preparar Repositório

```bash
git init
git add .
git commit -m "Initial commit - Discord Bot Roblox Monitor"
git branch -M main
git remote add origin https://github.com/seu-usuario/seu-repositorio.git
git push -u origin main
```

### 2. Deploy no Railway

1. Vá em [Railway.app](https://railway.app) e faça login
2. Clique em "New Project"
3. Selecione "Deploy from GitHub repo"
4. Escolha seu repositório
5. Configure a variável de ambiente:
   - Nome: `DISCORD_BOT_TOKEN`
   - Valor: Token do seu bot Discord

### 3. Configurar Variáveis de Ambiente

No painel do Railway, vá em "Variables" e adicione:

```
DISCORD_BOT_TOKEN=seu_token_aqui
```

### 4. Deploy Automático

O Railway detectará automaticamente os arquivos de configuração (`Procfile`, `requirements.txt`, `railway.json`) e fará o deploy automaticamente.

## 🛠️ Desenvolvimento Local

### Pré-requisitos

- Python 3.11+
- pip ou uv para gerenciamento de pacotes

### Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/discord-bot-roblox-monitor.git
cd discord-bot-roblox-monitor
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure o arquivo `.env`:
```bash
cp .env.example .env
# Edite o .env com seu token do bot
```

4. Configure os IDs autorizados no arquivo `config.py`

5. Execute o bot:
```bash
python bot_main.py
```

## 📁 Estrutura do Projeto

```
├── bot_main.py          # Arquivo principal para executar o bot
├── discord_bot.py       # Lógica principal do bot Discord
├── config.py            # Configurações do bot
├── api_utils.py         # Utilitários para API do Roblox
├── sheets_sync.py       # Sincronização com Google Sheets (opcional)
├── requirements.txt     # Dependências Python
├── Procfile            # Configuração do Railway
├── railway.json        # Configurações específicas do Railway
├── runtime.txt         # Versão do Python
├── .env.example        # Exemplo de variáveis de ambiente
└── README.md           # Este arquivo
```

## 🔧 Configurações Avançadas

### Personalizar Mensagens

Edite o arquivo `config.py` para personalizar as mensagens de resposta, cores dos embeds e emojis utilizados.

### Alterar Intervalo de Monitoramento

No arquivo `config.py`, modifique `CHECK_INTERVAL` (em segundos):

```python
CHECK_INTERVAL = 30  # Verifica a cada 30 segundos
```

### Adicionar Mais Usuários Autorizados

Adicione mais IDs na lista `AUTHORIZED_DISCORD_IDS` no arquivo `config.py`.

## 🚨 Solução de Problemas

### Bot não responde aos comandos

1. Verifique se o bot está online no servidor
2. Confirme se os slash commands foram sincronizados (aparece no log na inicialização)
3. Verifique se seu ID está na lista `AUTHORIZED_DISCORD_IDS`

### Erro "Token inválido"

1. Regenere o token no Discord Developer Portal
2. Atualize a variável de ambiente `DISCORD_BOT_TOKEN`
3. Reinicie o bot

### Notificações não aparecem

1. Verifique se `NOTIFICATION_CHANNEL_ID` está configurado corretamente
2. Confirme se o bot tem permissão para enviar mensagens no canal
3. Verifique se há usuários sendo monitorados (`/list`)

## 📝 Changelog

### v2.0.0 - Conversão para Bot Discord
- ✅ Migração do sistema webhook para bot Discord com slash commands
- ✅ Implementação dos comandos `/track`, `/removetrack`, `/view` e `/list`
- ✅ Sistema de permissões por ID do Discord
- ✅ Configuração para deploy no Railway
- ✅ Monitoramento automático em background

### v1.0.0 - Sistema Original
- Sistema webhook original para monitoramento de badges e presença

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique a seção "Solução de Problemas"
2. Consulte os logs do Railway ou do terminal local
3. Abra uma issue no repositório GitHub

## 📄 Licença

Este projeto é open source e está disponível sob a licença MIT.