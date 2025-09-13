#!/usr/bin/env python3
"""
Bot do Discord para monitoramento de badges e presença do Roblox
Adaptado do sistema webhook original para funcionar como bot Discord com slash commands
"""

import os
import sys
import threading
import time
from discord_bot import run_bot
from keep_alive import keep_alive

def main():
    """Função principal para executar o bot"""
    
    print("🤖 Iniciando Bot Discord - Monitor Roblox")
    print("=" * 50)
    
    # 1. Iniciar keep-alive em thread separada primeiro
    print("🌐 Iniciando servidor Flask (keep-alive)...")
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True, name="KeepAlive")
    keep_alive_thread.start()
    
    # Aguardar um pouco para o Flask iniciar completamente
    time.sleep(5)
    print("✅ Servidor Flask iniciado")
    
    # 2. Verificar se o token do bot está configurado
    bot_token = os.getenv('BOT_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
    if not bot_token:
        print("❌ ERRO: Token do bot não configurado!")
        print("📝 Configure a variável de ambiente BOT_TOKEN (Railway) ou DISCORD_BOT_TOKEN")
        print("💡 Exemplo: BOT_TOKEN='seu_token_aqui' (Railway)")
        print("🔗 Obtenha seu token em: https://discord.com/developers/applications")
        # Não retornar False - deixar o servidor Flask rodando para health checks
        print("⚠️  Mantendo servidor Flask ativo para health checks...")
        # Manter o processo vivo para o Railway
        while True:
            time.sleep(60)
    
    print("✅ Token do bot encontrado")
    print("🚀 Iniciando bot Discord...")
    
    try:
        # 3. Executar o bot (isso bloqueia a thread principal)
        run_bot(bot_token)
        
    except KeyboardInterrupt:
        print("\n⏹️  Bot interrompido pelo usuário")
        return True
        
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        # Não retornar False - deixar o servidor Flask rodando
        print("⚠️  Mantendo servidor Flask ativo após erro do bot...")
        while True:
            time.sleep(60)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)