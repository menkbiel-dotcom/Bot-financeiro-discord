import os
import asyncio
import logging
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

import database as db

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

logger = logging.getLogger("finance_bot")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler("bot.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_handler)
logging.getLogger("discord").setLevel(logging.WARNING)

intents = discord.Intents.default()

COGS = ["cogs.transacoes", "cogs.relatorios", "cogs.metas", "cogs.faturas"]


class FinanceBot(commands.Bot):
    async def setup_hook(self):
        if db.DB_PATH.exists():
            try:
                await asyncio.to_thread(db.backup_database)
                logger.info("Backup inicial do banco concluído.")
            except Exception:
                logger.exception("Falha no backup inicial; o bot continuará sem interromper a inicialização.")
        db.init_db()
        for cog in COGS:
            await self.load_extension(cog)
        synced = await self.tree.sync()
        logger.info("%s comandos slash sincronizados.", len(synced))


bot = FinanceBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info("Bot conectado como %s (ID: %s)", bot.user, bot.user.id)
    if not backup_diario.is_running():
        backup_diario.start()


@tasks.loop(hours=24)
async def backup_diario():
    try:
        path = await asyncio.to_thread(db.backup_database)
        logger.info("Backup diário concluído: %s", path.name)
    except Exception:
        logger.exception("Falha no backup diário.")


@backup_diario.before_loop
async def aguardar_backup_diario():
    await bot.wait_until_ready()
    await asyncio.sleep(24 * 60 * 60)


@bot.tree.error
async def tratar_erro_comando(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error("Erro em comando slash", exc_info=(type(error), error, error.__traceback__))
    mensagem = "❌ Ocorreu um erro ao processar o comando. Tente novamente; se persistir, avise quem administra o bot."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(mensagem, ephemeral=True)
        else:
            await interaction.response.send_message(mensagem, ephemeral=True)
    except discord.HTTPException:
        logger.exception("Não foi possível responder à interação com erro.")


async def main():
    if not TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN não encontrado. Crie um arquivo .env com DISCORD_TOKEN=seu_token_aqui"
        )

    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
