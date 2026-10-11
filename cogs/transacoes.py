import discord
from discord import app_commands
from discord.ext import commands
import database as db


class Transacoes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="gasto", description="Registra uma despesa")
    @app_commands.describe(valor="Valor gasto", categoria="Categoria do gasto",
                            descricao="Descrição opcional")
    async def gasto(self, interaction: discord.Interaction, valor: float,
                     categoria: str, descricao: str = ""):
        if valor <= 0:
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True)
            return

        db.adicionar_transacao(
            usuario_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            valor=valor,
            tipo="despesa",
            categoria=categoria,
            descricao=descricao,
        )

        embed = discord.Embed(
            title="💸 Despesa registrada",
            color=discord.Color.red(),
        )
        embed.add_field(name="Valor", value=f"R$ {valor:.2f}", inline=True)
        embed.add_field(name="Categoria", value=categoria.capitalize(), inline=True)
        if descricao:
            embed.add_field(name="Descrição", value=descricao, inline=False)

        # Verifica se estourou alguma meta
        gasto_atual = db.obter_gasto_categoria_mes_atual(
            str(interaction.user.id), str(interaction.guild_id), categoria
        )
        metas = db.obter_metas(str(interaction.user.id), str(interaction.guild_id))
        meta_categoria = next((m for m in metas if m["categoria"] == categoria.lower()), None)

        if meta_categoria and gasto_atual > meta_categoria["valor_limite"]:
            embed.add_field(
                name="⚠️ Atenção",
                value=f"Você ultrapassou a meta de **{categoria}** "
                      f"(R$ {gasto_atual:.2f} / R$ {meta_categoria['valor_limite']:.2f})",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="receita", description="Registra uma receita/entrada")
    @app_commands.describe(valor="Valor recebido", categoria="Categoria da receita",
                            descricao="Descrição opcional")
    async def receita(self, interaction: discord.Interaction, valor: float,
                       categoria: str, descricao: str = ""):
        if valor <= 0:
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True)
            return

        db.adicionar_transacao(
            usuario_id=str(interaction.user.id),
            guild_id=str(interaction.guild_id),
            valor=valor,
            tipo="receita",
            categoria=categoria,
            descricao=descricao,
        )

        embed = discord.Embed(
            title="💰 Receita registrada",
            color=discord.Color.green(),
        )
        embed.add_field(name="Valor", value=f"R$ {valor:.2f}", inline=True)
        embed.add_field(name="Categoria", value=categoria.capitalize(), inline=True)
        if descricao:
            embed.add_field(name="Descrição", value=descricao, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="saldo", description="Mostra seu saldo atual")
    async def saldo(self, interaction: discord.Interaction):
        saldo = db.obter_saldo(str(interaction.user.id), str(interaction.guild_id))
        cor = discord.Color.green() if saldo >= 0 else discord.Color.red()

        embed = discord.Embed(
            title=f"💼 Saldo de {interaction.user.display_name}",
            description=f"**R$ {saldo:.2f}**",
            color=cor,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="extrato", description="Mostra suas últimas transações")
    @app_commands.describe(quantidade="Quantidade de transações a mostrar (padrão 10)")
    async def extrato(self, interaction: discord.Interaction, quantidade: int = 10):
        transacoes = db.obter_ultimas_transacoes(
            str(interaction.user.id), str(interaction.guild_id), quantidade
        )

        if not transacoes:
            await interaction.response.send_message("Nenhuma transação encontrada ainda.", ephemeral=True)
            return

        embed = discord.Embed(title="📋 Últimas transações", color=discord.Color.blue())
        for t in transacoes:
            sinal = "+" if t["tipo"] == "receita" else "-"
            emoji = "💰" if t["tipo"] == "receita" else "💸"
            data_fmt = t["data"][:10]
            texto = f"{sinal}R$ {t['valor']:.2f} • {t['categoria'].capitalize()} • {data_fmt}"
            if t["descricao"]:
                texto += f"\n_{t['descricao']}_"
            embed.add_field(name=f"{emoji} ID {t['id']}", value=texto, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="apagar", description="Apaga uma transação pelo ID (veja o ID em /extrato)")
    @app_commands.describe(id_transacao="ID da transação a apagar")
    async def apagar(self, interaction: discord.Interaction, id_transacao: int):
        sucesso = db.deletar_transacao(id_transacao, str(interaction.user.id))
        if sucesso:
            await interaction.response.send_message(f"✅ Transação {id_transacao} apagada.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Transação não encontrada (ou não pertence a você).", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Transacoes(bot))
