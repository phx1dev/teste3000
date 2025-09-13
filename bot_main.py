#!/usr/bin/env python3
"""
Bot do Discord para monitoramento de badges e presença do Roblox
Adaptado do sistema webhook original para funcionar como bot Discord com slash commands
"""

import os
import sys
from discord_bot import run_bot

def main():
    """Função principal para executar o bot"""
    
    print("🤖 Iniciando Bot Discord - Monitor Roblox")
    print("=" * 50)
    
    # Verificar se o token do bot está configurado
    bot_token = os.getenv('BOT_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
    if not bot_token:
        print("❌ ERRO: Token do bot não configurado!")
        print("📝 Configure a variável de ambiente BOT_TOKEN (Railway) ou DISCORD_BOT_TOKEN")
        print("💡 Exemplo: BOT_TOKEN='seu_token_aqui' (Railway)")
        print("🔗 Obtenha seu token em: https://discord.com/developers/applications")
        return False
    
    print("✅ Token do bot encontrado")
    print("🚀 Iniciando bot...")
    
    try:
        # Executar o bot
        run_bot(bot_token)
        
    except KeyboardInterrupt:
        print("\n⏹️  Bot interrompido pelo usuário")
        return True
        
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)