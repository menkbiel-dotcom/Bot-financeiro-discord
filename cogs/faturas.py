from datetime import date, datetime, time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import database as db

# Horário do dia em que o bot confere as faturas (hora local do servidor onde ele roda)
HORARIO_CHECAGEM = time(hour=9, minute=0)


class Faturas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.checar_faturas.start()

    def cog_unload(self):
        self.checar_faturas.cancel()

    @app_commands.command(name="fatura", description="Cadastra uma fatura/conta para receber lembretes")
    @app_commands.describe(
        nome="Nome da fatura (ex: Cartão de crédito, Aluguel)",
        valor="Valor da fatura",
        dia_vencimento="Dia do mês em que vence (1 a 31)",
        dias_aviso="Com quantos dias de antecedência avisar (padrão: 3)",
    )
    async def fatura(self, interaction: discord.Interaction, nome: str, valor: float,
                      dia_vencimento: int, dias_aviso: int = 3):
        if valor <= 0:
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True)
            return
        if not (1 <= dia_vencimento <= 31):
            await interaction.response.send_message("❌ O dia de vencimento precisa ser entre 1 e 31.", ephemeral=True)
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

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="faturas", description="Lista suas faturas cadastradas")
    async def faturas(self, interaction: discord.Interaction):
        faturas = db.obter_faturas(str(interaction.user.id), str(interaction.guild_id))

        if not faturas:
            await interaction.response.send_message(
                "Você ainda não cadastrou nenhuma fatura. Use `/fatura`.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🧾 Suas faturas", color=discord.Color.blue())
        for f in faturas:
            proximo = db.proximo_vencimento(f["dia_vencimento"])
            embed.add_field(
                name=f"{f['nome']} (ID {f['id']})",
                value=(
                    f"R$ {f['valor']:.2f} • vence dia {f['dia_vencimento']}\n"
                    f"Próximo vencimento: {proximo.strftime('%d/%m/%Y')}\n"
                    f"Aviso: {f['dias_aviso']} dia(s) antes"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="apagar_fatura", description="Apaga uma fatura pelo ID (veja o ID em /faturas)")
    @app_commands.describe(id_fatura="ID da fatura a apagar")
    async def apagar_fatura(self, interaction: discord.Interaction, id_fatura: int):
        sucesso = db.deletar_fatura(id_fatura, str(interaction.user.id))
        if sucesso:
            await interaction.response.send_message(f"✅ Fatura {id_fatura} apagada.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Fatura não encontrada (ou não pertence a você).", ephemeral=True
            )

    @tasks.loop(time=HORARIO_CHECAGEM)
    async def checar_faturas(self):
        hoje = date.today()
        hoje_iso = hoje.isoformat()

        for f in db.obter_todas_faturas():
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
                print(f"Erro ao enviar lembrete de fatura {f['id']}: {e}")

    @checar_faturas.before_loop
    async def antes_de_checar(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Faturas(bot))
