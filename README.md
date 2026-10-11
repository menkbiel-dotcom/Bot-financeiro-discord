[README.md](https://github.com/user-attachments/files/33313054/README.md)
# Bot-financeiro-discord
organização financeira de qualquer lugar que você estiver e com uma planilha implementada
# Bot Financeiro para Discord

Bot para ajudar você (e seu servidor) a organizar receitas, despesas, relatórios e metas de gastos, tudo direto no Discord.

## Funcionalidades

- `/gasto valor categoria [descricao]` — registra uma despesa
- `/receita valor categoria [descricao]` — registra uma receita
- `/saldo` — mostra seu saldo atual (receitas - despesas)
- `/extrato [quantidade]` — lista suas últimas transações
- `/apagar id_transacao` — apaga uma transação pelo ID
- `/relatorio [mes] [ano]` — gera um resumo e gráfico de pizza dos gastos por categoria
- `/meta categoria valor` — define um limite mensal de gastos para uma categoria
- `/metas` — mostra o progresso de todas as suas metas no mês atual
- `/fatura nome valor dia_vencimento [dias_aviso]` — cadastra uma conta/fatura recorrente para receber lembretes (ex: `/fatura nome:Cartão valor:350 dia_vencimento:15`)
- `/faturas` — lista suas faturas cadastradas e a próxima data de vencimento de cada uma
- `/apagar_fatura id_fatura` — apaga uma fatura cadastrada

**Sobre os lembretes de fatura:** todo dia às 9h (horário de onde o bot está rodando), ele confere sozinho se alguma fatura está perto de vencer e manda uma **mensagem privada (DM)** avisando. Por padrão avisa com 3 dias de antecedência, mas você pode mudar isso no `dias_aviso` ao cadastrar. Importante: pra receber a DM, sua conta do Discord precisa permitir mensagens diretas de membros do servidor (isso já vem ativado por padrão).

Os dados são separados por usuário e por servidor (guild), então cada pessoa vê apenas suas próprias finanças.

## Como configurar

### 1. Criar a aplicação no Discord

1. Acesse o [Discord Developer Portal](https://discord.com/developers/applications)
2. Clique em "New Application" e dê um nome ao bot
3. Vá em "Bot" no menu lateral → "Add Bot"
4. Copie o **Token** (você vai usar no `.env`)
5. Em "OAuth2" → "URL Generator":
   - Scopes: `bot`, `applications.commands`
   - Permissões: `Send Messages`, `Embed Links`, `Attach Files`, `Use Slash Commands`
6. Use o link gerado para convidar o bot para o seu servidor

### 2. Instalar dependências

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar o token

Copie `.env.example` para `.env` e cole seu token:

```bash
cp .env.example .env
```

Edite o `.env`:
```
DISCORD_TOKEN=seu_token_aqui
```

### 4. Rodar o bot

```bash
python bot.py
```

Se tudo der certo, você verá no terminal:
```
✅ Bot conectado como SeuBot#1234
🔄 8 comandos slash sincronizados.
```

Os comandos slash podem levar alguns minutos para aparecer no Discord na primeira vez (sincronização global). Se quiser que apareçam instantaneamente durante testes, você pode sincronizar apenas para um servidor específico — me avise se quiser esse ajuste.

## Estrutura do projeto

```
discord-finance-bot/
├── bot.py              # ponto de entrada do bot
├── database.py         # camada de acesso ao SQLite
├── cogs/
│   ├── transacoes.py    # /gasto /receita /saldo /extrato /apagar
│   ├── relatorios.py     # /relatorio (com gráfico)
│   └── metas.py          # /meta /metas
├── requirements.txt
├── .env.example
└── financas.db          # criado automaticamente na primeira execução
```

## Próximos passos possíveis

- Migrar de SQLite para PostgreSQL (útil se o bot for usado em muitos servidores)
- Adicionar contas/carteiras separadas (ex: "conta corrente", "cartão de crédito")
- Exportar extrato em CSV/Excel
- Lembretes automáticos de contas a pagar
- Deploy em Railway/Render para rodar 24/7

## Hospedagem (deploy)

- **Railway**: conecte o repositório, defina a variável `DISCORD_TOKEN`, e o Railway roda `python bot.py` automaticamente com um `Procfile` (`worker: python bot.py`)
- **Oracle Cloud Free Tier / VPS**: use um `systemd` service ou `screen`/`tmux` para manter o processo rodando
