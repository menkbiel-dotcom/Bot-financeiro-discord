from datetime import date, datetime
import math
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord import app_commands
from discord.ext import commands, tasks

import database as db

logger = logging.getLogger(__name__)

class Faturas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.checar_faturas.start()

    def cog_unload(self):
        self.checar_faturas.cancel()

    @app_commands.guild_only()
    @app_commands.command(name="fatura", description="Cadastra uma fatura/conta para receber lembretes")
    @app_commands.describe(
        nome="Nome da fatura (ex: Cartão de crédito, Aluguel)",
        valor="Valor da fatura",
        dia_vencimento="Dia do mês em que vence (1 a 31)",
        dias_aviso="Com quantos dias de antecedência avisar (padrão: 3)",
    )
    async def fatura(self, interaction: discord.Interaction, nome: str, valor: float,
                      dia_vencimento: int, dias_aviso: int = 3):
        nome = nome.strip()
        if not math.isfinite(valor) or valor <= 0:
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True)
            return
        if not (1 <= dia_vencimento <= 31):
            await interaction.response.send_message("❌ O dia de vencimento precisa ser entre 1 e 31.", ephemeral=True)
            return
        if not nome or len(nome) > 100:
            await interaction.response.send_message("❌ O nome precisa ter entre 1 e 100 caracteres.", ephemeral=True)
            return
        if not 0 <= dias_aviso <= 30:
            await interaction.response.send_message("❌ O aviso deve ser entre 0 e 30 dias.", ephemeral=True)
            return

        db.adicionar_fatura(
            usuario_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            nome=nome,
            valor=valor,
            dia_vencimento=dia_vencimento,
            dias_aviso=dias_aviso,
        )

        proximo = db.proximo_vencimento(dia_vencimento)

        embed = discord.Embed(title="🧾 Fatura cadastrada", color=discord.Color.blue())
        embed.add_field(name="Nome", value=nome, inline=True)
        embed.add_field(name="Valor", value=f"R$ {valor:.2f}", inline=True)
        embed.add_field(name="Vence todo dia", value=str(dia_vencimento), inline=True)
        embed.add_field(name="Próximo vencimento", value=proximo.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Aviso", value=f"{dias_aviso} dia(s) antes, por mensagem privada", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="faturas", description="Lista suas faturas cadastradas")
    async def faturas(self, interaction: discord.Interaction):
        faturas = db.obter_faturas(str(interaction.user.id), str(interaction.guild_id))

        if not faturas:
            await interaction.response.send_message(
                "Você ainda não cadastrou nenhuma fatura. Use `/fatura`.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🧾 Suas faturas", color=discord.Color.blue())
        competencia_atual = datetime.now(ZoneInfo(db.obter_fuso(str(interaction.guild_id)))).strftime("%Y-%m")
        for f in faturas[:25]:
            proximo = db.proximo_vencimento(f["dia_vencimento"])
            embed.add_field(
                name=f"{f['nome']} (ID {f['id']})",
                value=(
                    f"R$ {f['valor']:.2f} • vence dia {f['dia_vencimento']}\n"
                    f"Próximo vencimento: {proximo.strftime('%d/%m/%Y')}\n"
                    f"Aviso: {f['dias_aviso']} dia(s) antes\n"
                    f"Situação: {'✅ paga neste mês' if f['paga_em'] == competencia_atual else '⏳ pendente'}"
                ),
                inline=False,
            )
        if len(faturas) > 25:
            embed.set_footer(text=f"Exibindo 25 de {len(faturas)} faturas. Apague as que não usa mais para ver todas.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="apagar_fatura", description="Apaga uma fatura pelo ID (veja o ID em /faturas)")
    @app_commands.describe(id_fatura="ID da fatura a apagar")
    async def apagar_fatura(self, interaction: discord.Interaction, id_fatura: int):
        sucesso = db.deletar_fatura(
            id_fatura, str(interaction.user.id), str(interaction.guild_id)
        )
        if sucesso:
            await interaction.response.send_message(f"✅ Fatura {id_fatura} apagada.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Fatura não encontrada (ou não pertence a você).", ephemeral=True
            )

    @app_commands.guild_only()
    @app_commands.command(name="pagar_fatura", description="Marca uma fatura como paga neste mês")
    async def pagar_fatura(self, interaction: discord.Interaction, id_fatura: int):
        competencia = datetime.now(ZoneInfo(db.obter_fuso(str(interaction.guild_id)))).strftime("%Y-%m")
        ok = db.marcar_fatura_paga(id_fatura, str(interaction.user.id), str(interaction.guild_id), competencia)
        await interaction.response.send_message("✅ Fatura marcada como paga neste mês." if ok else "❌ Fatura não encontrada.", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="fuso_horario", description="Define o fuso dos lembretes (ex.: America/Sao_Paulo)")
    @app_commands.describe(fuso="Nome IANA, como America/Sao_Paulo ou Europe/Lisbon")
    async def fuso_horario(self, interaction: discord.Interaction, fuso: str):
        try:
            ZoneInfo(fuso)
        except (ZoneInfoNotFoundError, ValueError):
            await interaction.response.send_message("❌ Fuso inválido. Use o formato IANA, por exemplo `America/Sao_Paulo`.", ephemeral=True); return
        db.configurar_fuso(str(interaction.guild_id), fuso)
        await interaction.response.send_message(f"✅ Fuso dos lembretes definido para `{fuso}` (aviso às 9h).", ephemeral=True)

    @tasks.loop(minutes=1)
    async def checar_faturas(self):
        for f in db.obter_todas_faturas():
            try:
                fuso = ZoneInfo(db.obter_fuso(str(f["guild_id"])))
                agora = datetime.now(fuso)
                hoje = agora.date()
                if agora.hour != 9 or agora.minute >= 5:
                    continue
            except (ZoneInfoNotFoundError, ValueError):
                logger.exception("Fuso inválido para guild %s", f["guild_id"])
                continue
            competencia = hoje.strftime("%Y-%m")
            if f["paga_em"] == competencia:
                continue
            hoje_iso = hoje.isoformat()
            proximo = db.proximo_vencimento(f["dia_vencimento"], referencia=hoje)
            dias_restantes = (proximo - hoje).days

            ja_notificada_hoje = f["ultima_notificacao"] == hoje_iso
            deve_avisar = 0 <= dias_restantes <= f["dias_aviso"] and not ja_notificada_hoje

            if not deve_avisar:
                continue

            try:
                usuario = await self.bot.fetch_user(int(f["usuario_id"]))
                if dias_restantes == 0:
                    texto = f"🚨 Sua fatura **{f['nome']}** (R$ {f['valor']:.2f}) vence **hoje**!"
                else:
                    texto = (
                        f"🔔 Sua fatura **{f['nome']}** (R$ {f['valor']:.2f}) vence em "
                        f"**{dias_restantes} dia(s)**, no dia {proximo.strftime('%d/%m/%Y')}."
                    )
                await usuario.send(texto)
                db.marcar_fatura_notificada(f["id"], hoje_iso)
            except discord.Forbidden:
                # Usuário com DMs fechadas para o bot; não há como avisar por aqui.
                db.marcar_fatura_notificada(f["id"], hoje_iso)
            except Exception as e:
                logger.exception("Erro ao enviar lembrete da fatura %s", f["id"])

    @checar_faturas.before_loop
    async def antes_de_checar(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Faturas(bot))
