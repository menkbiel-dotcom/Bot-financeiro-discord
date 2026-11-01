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
- `/pagar_fatura id_fatura` — marca a fatura recorrente como paga neste mês
- `/fuso_horario fuso` — configura o fuso IANA usado nos lembretes, por exemplo `America/Sao_Paulo`
- `/saldo_mes` — compara receitas, despesas e saldo com o mês anterior
- `/categorias` — mostra categorias usadas e sugestões; `/gasto` e `/receita` oferecem autocomplete
- `/editar_transacao id_transacao [valor] [categoria] [descricao]` — corrige um lançamento
- `/repetir_transacao id_transacao` — copia um lançamento para hoje
- `/exportar_csv [dias]` — envia um CSV privado de até 365 dias

**Sobre os lembretes de fatura:** o bot verifica as faturas às 9h no fuso configurado para cada servidor e manda uma **mensagem privada (DM)**. Por padrão, avisa com 3 dias de antecedência. Uma fatura marcada como paga não gera lembretes de novo naquele mês; ela continua cadastrada para os meses seguintes.

Os dados são separados por usuário e por servidor, e as respostas dos comandos são privadas (visíveis só para quem executou o comando).

O extrato mostra no máximo 25 transações por vez. Relatórios, metas e faturas mostram até 25 itens por resposta, para respeitar os limites do Discord. O horário dos lembretes segue o fuso horário configurado no servidor onde o bot está rodando.

O fuso padrão é `America/Sao_Paulo`; use `/fuso_horario` para alterar. O bot grava logs rotativos em `bot.log` e cria backups SQLite em `backups/`, mantendo os 14 mais recentes. Segredos e dados locais (`.env`, banco, logs, backups e ambiente virtual) ficam fora do Git.

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

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Configurar o token

Copie `.env.example` para `.env` e cole seu token:

```powershell
Copy-Item .env.example .env
```

Edite `.env` localmente e defina seu token. Nunca publique esse arquivo nem cole o token em issues ou mensagens:
```
DISCORD_TOKEN=seu_token_aqui
```

### 4. Rodar o bot

```powershell
.\.venv\Scripts\python.exe bot.py
```

Se tudo der certo, você verá no terminal:
```
✅ Bot conectado como SeuBot
🔄 18 comandos slash sincronizados.
```

Os comandos slash podem levar alguns minutos para aparecer no Discord na primeira vez (sincronização global). Se quiser que apareçam instantaneamente durante testes, você pode sincronizar apenas para um servidor específico — me avise se quiser esse ajuste.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Estrutura do projeto

```
discord-finance-bot/
├── bot.py              # ponto de entrada do bot
├── database.py         # camada de acesso ao SQLite
├── cogs/
│   ├── transacoes.py    # lançamentos, edição, repetição, CSV e saldo
│   ├── relatorios.py    # relatórios com gráfico
│   ├── metas.py         # metas e alertas
│   └── faturas.py       # faturas recorrentes e lembretes por fuso
├── tests/               # testes isolados da camada SQLite
├── requirements.txt
├── .env.example         # modelo sem segredos
└── .gitignore           # exclui segredos e dados locais
```

## Hospedagem (deploy)

- **Railway**: conecte o repositório, defina a variável `DISCORD_TOKEN`, e o Railway roda `python bot.py` automaticamente com um `Procfile` (`worker: python bot.py`)
- **Oracle Cloud Free Tier / VPS**: use um `systemd` service ou `screen`/`tmux` para manter o processo rodando
