import discord
from discord import app_commands
from discord.ext import commands
import database as db


class Metas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="meta", description="Define um limite mensal de gastos para uma categoria")
    @app_commands.describe(categoria="Categoria", valor="Valor limite mensal")
    async def meta(self, interaction: discord.Interaction, categoria: str, valor: float):
        if valor <= 0:
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True)
            return

        db.definir_meta(str(interaction.user.id), str(interaction.guild_id), categoria, valor)

        embed = discord.Embed(
            title="🎯 Meta definida",
            description=f"Limite mensal para **{categoria.capitalize()}**: R$ {valor:.2f}",
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="metas", description="Mostra suas metas e o progresso do mês atual")
    async def metas(self, interaction: discord.Interaction):
        metas = db.obter_metas(str(interaction.user.id), str(interaction.guild_id))

        if not metas:
            await interaction.response.send_message("Você ainda não definiu nenhuma meta. Use `/meta`.", ephemeral=True)
            return

        embed = discord.Embed(title="🎯 Suas metas do mês", color=discord.Color.purple())
        for m in metas:
            gasto_atual = db.obter_gasto_categoria_mes_atual(
                str(interaction.user.id), str(interaction.guild_id), m["categoria"]
            )
            limite = m["valor_limite"]
            pct = (gasto_atual / limite) * 100 if limite else 0
            barra = self._barra_progresso(pct)
            status = "⚠️ Estourou!" if gasto_atual > limite else "✅"

            embed.add_field(
                name=f"{m['categoria'].capitalize()} {status}",
                value=f"R$ {gasto_atual:.2f} / R$ {limite:.2f}\n{barra} {pct:.0f}%",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @staticmethod
    def _barra_progresso(pct: float, tamanho: int = 10) -> str:
        pct_limitado = min(pct, 100)
        preenchido = int((pct_limitado / 100) * tamanho)
        return "█" * preenchido + "░" * (tamanho - preenchido)


async def setup(bot: commands.Bot):
    await bot.add_cog(Metas(bot))
