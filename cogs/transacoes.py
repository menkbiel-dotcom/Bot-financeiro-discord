import discord
import math
import csv
import io
from datetime import date, datetime, timedelta
from discord import app_commands
from discord.ext import commands
import database as db


class Transacoes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gasto.autocomplete("categoria")(self.autocompletar_categoria)
        self.receita.autocomplete("categoria")(self.autocompletar_categoria)

    async def autocompletar_categoria(self, interaction: discord.Interaction, atual: str):
        padrao = ["Alimentação", "Moradia", "Transporte", "Saúde", "Lazer", "Salário", "Freelance", "Outros"]
        usadas = db.categorias_existentes(str(interaction.user.id), str(interaction.guild_id)) if interaction.guild_id else []
        opcoes = list(dict.fromkeys(usadas + padrao))
        return [app_commands.Choice(name=c[:100], value=c) for c in opcoes if atual.casefold() in c.casefold()][:25]

    @app_commands.guild_only()
    @app_commands.command(name="gasto", description="Registra uma despesa")
    @app_commands.describe(valor="Valor gasto", categoria="Categoria do gasto",
                            descricao="Descrição opcional")
    async def gasto(self, interaction: discord.Interaction, valor: float,
                     categoria: str, descricao: str = ""):
        if not math.isfinite(valor) or valor <= 0:
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True)
            return

        categoria = categoria.strip()
        descricao = descricao.strip()
        if not categoria or len(categoria) > 50 or len(descricao) > 500:
            await interaction.response.send_message("❌ Use uma categoria de até 50 caracteres e descrição de até 500.", ephemeral=True)
            return

        usuario_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        gasto_antes = db.obter_gasto_categoria_mes_atual(usuario_id, guild_id, categoria)
        db.adicionar_transacao(
            usuario_id=usuario_id,
            guild_id=guild_id,
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
        gasto_atual = db.obter_gasto_categoria_mes_atual(usuario_id, guild_id, categoria)
        metas = db.obter_metas(usuario_id, guild_id)
        meta_categoria = next((m for m in metas if m["categoria"] == categoria.lower()), None)

        if meta_categoria and gasto_antes <= meta_categoria["valor_limite"] < gasto_atual:
            embed.add_field(
                name="⚠️ Atenção",
                value=f"Você ultrapassou a meta de **{categoria}** "
                      f"(R$ {gasto_atual:.2f} / R$ {meta_categoria['valor_limite']:.2f})",
                inline=False,
            )
        elif meta_categoria and gasto_antes < meta_categoria["valor_limite"] * 0.8 <= gasto_atual:
            embed.add_field(name="📣 Alerta de meta", value=f"Você chegou a 80% da meta de **{categoria}** (R$ {gasto_atual:.2f} / R$ {meta_categoria['valor_limite']:.2f}).", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="receita", description="Registra uma receita/entrada")
    @app_commands.describe(valor="Valor recebido", categoria="Categoria da receita",
                            descricao="Descrição opcional")
    async def receita(self, interaction: discord.Interaction, valor: float,
                       categoria: str, descricao: str = ""):
        if not math.isfinite(valor) or valor <= 0:
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True)
            return

        categoria = categoria.strip()
        descricao = descricao.strip()
        if not categoria or len(categoria) > 50 or len(descricao) > 500:
            await interaction.response.send_message("❌ Use uma categoria de até 50 caracteres e descrição de até 500.", ephemeral=True)
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="saldo", description="Mostra seu saldo atual")
    async def saldo(self, interaction: discord.Interaction):
        saldo = db.obter_saldo(str(interaction.user.id), str(interaction.guild_id))
        cor = discord.Color.green() if saldo >= 0 else discord.Color.red()

        embed = discord.Embed(
            title=f"💼 Saldo de {interaction.user.display_name}",
            description=f"**R$ {saldo:.2f}**",
            color=cor,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="saldo_mes", description="Compara receitas e despesas deste mês com o anterior")
    async def saldo_mes(self, interaction: discord.Interaction):
        hoje = datetime.now()
        anterior = date(hoje.year, hoje.month, 1) - timedelta(days=1)
        atual = db.resumo_mensal(str(interaction.user.id), str(interaction.guild_id), hoje.year, hoje.month)
        passado = db.resumo_mensal(str(interaction.user.id), str(interaction.guild_id), anterior.year, anterior.month)
        liquido = atual['receita'] - atual['despesa']
        liquido_anterior = passado['receita'] - passado['despesa']
        delta = liquido - liquido_anterior
        embed = discord.Embed(title="📈 Resumo mensal", color=discord.Color.green() if liquido >= 0 else discord.Color.red())
        embed.add_field(name=f"Este mês ({hoje:%m/%Y})", value=f"Entradas R$ {atual['receita']:.2f}\nDespesas R$ {atual['despesa']:.2f}\nSaldo R$ {liquido:.2f}", inline=True)
        embed.add_field(name=f"Mês anterior ({anterior:%m/%Y})", value=f"Entradas R$ {passado['receita']:.2f}\nDespesas R$ {passado['despesa']:.2f}\nSaldo R$ {liquido_anterior:.2f}", inline=True)
        embed.set_footer(text=f"Variação do saldo: {'+' if delta >= 0 else ''}R$ {delta:.2f}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="extrato", description="Mostra suas últimas transações")
    @app_commands.describe(quantidade="Quantidade de transações a mostrar (padrão 10)")
    async def extrato(self, interaction: discord.Interaction, quantidade: int = 10):
        quantidade = max(1, min(quantidade, 25))
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="apagar", description="Apaga uma transação pelo ID (veja o ID em /extrato)")
    @app_commands.describe(id_transacao="ID da transação a apagar")
    async def apagar(self, interaction: discord.Interaction, id_transacao: int):
        sucesso = db.deletar_transacao(
            id_transacao, str(interaction.user.id), str(interaction.guild_id)
        )
        if sucesso:
            await interaction.response.send_message(f"✅ Transação {id_transacao} apagada.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Transação não encontrada (ou não pertence a você).", ephemeral=True
            )

    @app_commands.guild_only()
    @app_commands.command(name="editar_transacao", description="Edita valor, categoria ou descrição de um lançamento")
    @app_commands.describe(id_transacao="ID visto no extrato", valor="Novo valor", categoria="Nova categoria", descricao="Nova descrição; deixe em branco para não alterar")
    async def editar_transacao(self, interaction: discord.Interaction, id_transacao: int,
                               valor: float = None, categoria: str = None, descricao: str = None):
        if valor is not None and (not math.isfinite(valor) or valor <= 0):
            await interaction.response.send_message("❌ O valor precisa ser maior que zero.", ephemeral=True); return
        if categoria is not None and (not categoria.strip() or len(categoria) > 50):
            await interaction.response.send_message("❌ Categoria inválida (máximo 50 caracteres).", ephemeral=True); return
        if descricao is not None and len(descricao) > 500:
            await interaction.response.send_message("❌ Descrição limitada a 500 caracteres.", ephemeral=True); return
        sucesso = db.editar_transacao(id_transacao, str(interaction.user.id), str(interaction.guild_id), valor=valor, categoria=categoria, descricao=descricao)
        texto = "✅ Transação atualizada." if sucesso else "❌ Transação não encontrada ou nenhum campo informado."
        await interaction.response.send_message(texto, ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="repetir_transacao", description="Duplica um lançamento com a data de hoje")
    async def repetir_transacao(self, interaction: discord.Interaction, id_transacao: int):
        item = db.obter_transacao(id_transacao, str(interaction.user.id), str(interaction.guild_id))
        if not item:
            await interaction.response.send_message("❌ Transação não encontrada.", ephemeral=True); return
        novo_id = db.adicionar_transacao(str(interaction.user.id), str(interaction.guild_id), item['valor'], item['tipo'], item['categoria'], item['descricao'] or "")
        await interaction.response.send_message(f"✅ Lançamento repetido como ID {novo_id}.", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="categorias", description="Mostra categorias usadas e sugestões")
    async def categorias(self, interaction: discord.Interaction):
        usadas = db.categorias_existentes(str(interaction.user.id), str(interaction.guild_id))
        padrao = ["Alimentação", "Moradia", "Transporte", "Saúde", "Lazer", "Salário", "Freelance", "Outros"]
        await interaction.response.send_message("**Suas categorias:** " + (", ".join(usadas) if usadas else "nenhuma ainda") + "\n**Sugestões:** " + ", ".join(padrao), ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="exportar_csv", description="Exporta suas transações recentes em CSV")
    @app_commands.describe(dias="Período em dias (1 a 365), padrão 30")
    async def exportar_csv(self, interaction: discord.Interaction, dias: int = 30):
        if not 1 <= dias <= 365:
            await interaction.response.send_message("❌ Escolha um período entre 1 e 365 dias.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        fim = datetime.now().astimezone()
        inicio = fim - timedelta(days=dias)
        rows = db.transacoes_periodo(str(interaction.user.id), str(interaction.guild_id), inicio.isoformat(), fim.isoformat())
        buf = io.StringIO(newline="")
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(["id", "data", "tipo", "valor", "categoria", "descricao"])
        for row in rows:
            writer.writerow([row["id"], row["data"], row["tipo"], f"{row['valor']:.2f}", row["categoria"], row["descricao"] or ""])
        file = discord.File(io.BytesIO(buf.getvalue().encode("utf-8-sig")), filename=f"extrato_{dias}_dias.csv")
        await interaction.followup.send(f"CSV com {len(rows)} lançamento(s).", file=file, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Transacoes(bot))
