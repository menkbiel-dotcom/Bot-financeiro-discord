import io
from datetime import datetime

import discord
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from discord import app_commands
from discord.ext import commands

import database as db


class Relatorios(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="relatorio", description="Mostra o resumo de gastos por categoria no mês")
    @app_commands.describe(mes="Mês (1-12), padrão é o mês atual",
                            ano="Ano, padrão é o ano atual")
    async def relatorio(self, interaction: discord.Interaction, mes: int = None, ano: int = None):
        agora = datetime.now()
        mes = mes or agora.month
        ano = ano or agora.year

        dados = db.obter_resumo_por_categoria(
            str(interaction.user.id), str(interaction.guild_id), tipo="despesa", mes=mes, ano=ano
        )

        if not dados:
            await interaction.response.send_message(
                f"Nenhuma despesa registrada em {mes:02d}/{ano}.", ephemeral=True
            )
            return

        total = sum(row["total"] for row in dados)

        embed = discord.Embed(
            title=f"📊 Relatório de {mes:02d}/{ano}",
            description=f"**Total gasto: R$ {total:.2f}**",
            color=discord.Color.orange(),
        )
        for row in dados:
            pct = (row["total"] / total) * 100 if total else 0
            embed.add_field(
                name=row["categoria"].capitalize(),
                value=f"R$ {row['total']:.2f} ({pct:.1f}%)",
                inline=False,
            )

        # Gera gráfico de pizza
        categorias = [row["categoria"].capitalize() for row in dados]
        valores = [row["total"] for row in dados]

        # Só mostra a porcentagem escrita na fatia se ela for grande o suficiente
        # pra caber sem virar bagunça; fatias pequenas ficam só na legenda.
        def formatar_pct(pct):
            return f"{pct:.1f}%" if pct >= 5 else ""

        cores = plt.cm.tab20.colors

        fig, ax = plt.subplots(figsize=(7, 5.5))
        wedges, _, _ = ax.pie(
            valores,
            labels=None,
            autopct=formatar_pct,
            pctdistance=0.75,
            startangle=90,
            colors=cores,
            textprops={"fontsize": 9, "color": "white", "weight": "bold"},
        )
        ax.axis("equal")

        legenda_labels = [
            f"{cat} — R$ {val:.2f} ({(val / total) * 100:.1f}%)"
            for cat, val in zip(categorias, valores)
        ]
        ax.legend(
            wedges,
            legenda_labels,
            title="Categorias",
            loc="center left",
            bbox_to_anchor=(1.0, 0.5),
            fontsize=9,
            frameon=False,
        )

        plt.title(f"Gastos por categoria - {mes:02d}/{ano}")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        buf.seek(0)
        plt.close(fig)

        file = discord.File(buf, filename="relatorio.png")
        embed.set_image(url="attachment://relatorio.png")

        await interaction.response.send_message(embed=embed, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(Relatorios(bot))