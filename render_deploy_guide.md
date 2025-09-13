# 🚀 Deploy no Render.com - Guia Completo

## 📋 **Pré-requisitos**
- Conta no GitHub
- Conta no Render.com (gratuita)
- Token do Discord Bot

## 🔧 **Passo 1: Preparar Repositório GitHub**

```bash
# 1. Criar repo no GitHub com o nome: roblox-discord-bot
# 2. No Replit Shell, executar:

git remote add origin https://github.com/SEU_USERNAME/roblox-discord-bot.git
git add .
git commit -m "🎨 Sistema otimizado para Render.com"
git push -u origin main
```

## 🎯 **Passo 2: Deploy no Render**

### **2.1 Criar Serviço**
1. Acesse [render.com](https://render.com) e faça login
2. Clique **"New +"** → **"Background Worker"**
3. Conecte sua conta GitHub
4. Selecione o repositório `roblox-discord-bot`

### **2.2 Configurar Serviço**
- **Name**: `roblox-discord-bot`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python bot_main.py`
- **Plan**: `Free` (750 horas/mês)

### **2.3 Variáveis de Ambiente**
No dashboard do Render, adicione:

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `BOT_TOKEN` | `seu_token_do_discord` | Token do Discord Bot |
| `DISCORD_BOT_TOKEN` | `seu_token_do_discord` | Backup do token |
| `DATA_DIR` | `/opt/render/project/src/data` | Diretório de dados |
| `RENDER` | `true` | Identifica plataforma Render |

### **2.4 Configurar Disco (Opcional)**
Para persistência de dados:
1. Na aba **"Settings"** do serviço
2. **"Disks"** → **"Add Disk"**
3. **Name**: `roblox-bot-data`
4. **Mount Path**: `/opt/render/project/src/data`
5. **Size**: `1 GB` (free tier)

## ✅ **Passo 3: Verificar Deploy**

### **3.1 Logs do Deploy**
No dashboard do Render, vá em **"Logs"** e verifique:
```
🤖 Iniciando Bot Discord - Monitor Roblox
🌐 Plataforma: Render.com Compatible
🎨 Rodando no Render.com (produção)
✅ Discord bot logado como: SEU_BOT_NOME
```

### **3.2 Testar Comandos Discord**
No Discord, teste os comandos:
- `/adicionar_usuario [roblox_username]`
- `/listar_usuarios`
- `/remover_usuario [roblox_username]`

## 🎯 **Características do Free Tier**

✅ **Incluído no Free Tier:**
- 750 horas/mês (suficiente para 24/7)
- 512MB RAM
- 0.1 CPU units
- 1GB disco persistente

⚠️ **Limitações Free Tier:**
- **Background Workers**: NÃO dormem (diferente de Web Services)
- **Recursos**: 512MB RAM, 0.1 CPU units
- **Uptime**: ~99% para free tier

## 🚀 **Para Operação 24/7 Real**

### **Upgrade para Starter Plan ($7/mês):**
- Sem sleep
- 512MB RAM garantidos
- 99.99% uptime SLA
- Suporte prioritário

### **Como Fazer Upgrade:**
1. Dashboard do serviço → **"Settings"**
2. **"Plan"** → **"Starter ($7/month)"**
3. **"Upgrade Plan"**

## 🛠 **Troubleshooting**

### **Bot não conecta:**
```bash
# Verificar se BOT_TOKEN está configurado
echo $BOT_TOKEN
```

### **Dados não persistem:**
- Verificar se disco está configurado em `/opt/render/project/src/data`
- Confirmar variável `DATA_DIR` correta

### **Background Worker não conecta:**
- Para Background Workers, não há sleep por inatividade
- Verificar logs de deploy no dashboard Render

## 📊 **Monitoramento**

### **Logs em Tempo Real:**
```bash
# No dashboard Render → "Logs"
# Filtrar por: ERROR, WARNING, INFO
```

### **Health Check Interno:**
O sistema possui endpoints internos de saúde:
- Status do bot
- Uptime
- Estatísticas de monitoramento

## 🎯 **Resultado Final**

✅ **Sistema 100% Bulletproof para Render.com**
✅ **Free tier: 750h/mês (24/7 com margem)**  
✅ **Auto-restart em caso de falha**
✅ **Monitoramento completo de badges e presença**
✅ **Comandos slash otimizados**
✅ **Persistência de dados configurada**

## 📞 **Suporte**

Em caso de problemas:
1. **Logs do Render**: Dashboard → Logs
2. **Discord**: Verificar se bot está online no servidor
3. **GitHub**: Confirmar último commit foi enviado
4. **Render Status**: [status.render.com](https://status.render.com)