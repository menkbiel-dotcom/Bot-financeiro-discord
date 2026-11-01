import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
import calendar
from pathlib import Path
from datetime import timedelta

DB_PATH = Path(__file__).resolve().with_name("financas.db")


def init_db():
    """Cria as tabelas do banco de dados caso não existam."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                valor REAL NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('receita', 'despesa')),
                categoria TEXT NOT NULL,
                descricao TEXT,
                data TEXT NOT NULL
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transacoes_usuario_guild_data ON transacoes(usuario_id, guild_id, data)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transacoes_usuario_guild_tipo_categoria_data ON transacoes(usuario_id, guild_id, tipo, categoria, data)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                categoria TEXT NOT NULL,
                valor_limite REAL NOT NULL,
                UNIQUE(usuario_id, guild_id, categoria)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                nome TEXT NOT NULL,
                valor REAL NOT NULL,
                dia_vencimento INTEGER NOT NULL CHECK(dia_vencimento BETWEEN 1 AND 31),
                dias_aviso INTEGER NOT NULL DEFAULT 3,
                ultima_notificacao TEXT
            )
        """)

        cursor.execute("ALTER TABLE faturas ADD COLUMN paga_em TEXT") if "paga_em" not in {r[1] for r in cursor.execute("PRAGMA table_info(faturas)")} else None
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes_servidor (
                guild_id TEXT PRIMARY KEY,
                fuso_horario TEXT NOT NULL DEFAULT 'America/Sao_Paulo'
            )
        """)

        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        yield conn
    finally:
        conn.close()


def adicionar_transacao(usuario_id: str, guild_id: str, valor: float, tipo: str,
                         categoria: str, descricao: str = ""):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transacoes (usuario_id, guild_id, valor, tipo, categoria, descricao, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (usuario_id, guild_id, valor, tipo, categoria.strip().casefold(), descricao,
              datetime.now().astimezone().isoformat()))
        conn.commit()
        return cursor.lastrowid


def obter_saldo(usuario_id: str, guild_id: str) -> float:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor ELSE 0 END), 0) AS saldo
            FROM transacoes
            WHERE usuario_id = ? AND guild_id = ?
        """, (usuario_id, guild_id))
        row = cursor.fetchone()
        return row["saldo"] if row else 0.0


def obter_resumo_por_categoria(usuario_id: str, guild_id: str, tipo: str = "despesa",
                                mes: int = None, ano: int = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT categoria, SUM(valor) as total
            FROM transacoes
            WHERE usuario_id = ? AND guild_id = ? AND tipo = ?
        """
        params = [usuario_id, guild_id, tipo]

        if mes is not None and ano is not None:
            inicio = date(ano, mes, 1).isoformat()
            fim = date(ano + (mes == 12), 1 if mes == 12 else mes + 1, 1).isoformat()
            query += " AND data >= ? AND data < ?"
            params.extend([inicio, fim])

        query += " GROUP BY categoria ORDER BY total DESC"
        cursor.execute(query, params)
        return cursor.fetchall()


def obter_ultimas_transacoes(usuario_id: str, guild_id: str, limite: int = 10):
    limite = max(1, min(int(limite), 25))
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM transacoes
            WHERE usuario_id = ? AND guild_id = ?
            ORDER BY data DESC
            LIMIT ?
        """, (usuario_id, guild_id, limite))
        return cursor.fetchall()


def obter_transacao(transacao_id: int, usuario_id: str, guild_id: str):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM transacoes WHERE id=? AND usuario_id=? AND guild_id=?",
                            (transacao_id, usuario_id, guild_id)).fetchone()


def editar_transacao(transacao_id: int, usuario_id: str, guild_id: str, *, valor=None, categoria=None, descricao=None):
    campos, valores = [], []
    if valor is not None:
        campos.append("valor=?"); valores.append(valor)
    if categoria is not None:
        campos.append("categoria=?"); valores.append(categoria.strip().casefold())
    if descricao is not None:
        campos.append("descricao=?"); valores.append(descricao.strip())
    if not campos:
        return False
    valores.extend([transacao_id, usuario_id, guild_id])
    with get_connection() as conn:
        cur = conn.execute(f"UPDATE transacoes SET {', '.join(campos)} WHERE id=? AND usuario_id=? AND guild_id=?", valores)
        conn.commit()
        return cur.rowcount > 0


def categorias_existentes(usuario_id: str, guild_id: str, limite: int = 25):
    with get_connection() as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT categoria FROM transacoes WHERE usuario_id=? AND guild_id=? ORDER BY categoria LIMIT ?",
                                           (usuario_id, guild_id, limite))]


def transacoes_periodo(usuario_id: str, guild_id: str, inicio: str, fim: str):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM transacoes WHERE usuario_id=? AND guild_id=? AND data>=? AND data<? ORDER BY data DESC",
                            (usuario_id, guild_id, inicio, fim)).fetchall()


def resumo_mensal(usuario_id: str, guild_id: str, ano: int, mes: int):
    inicio = date(ano, mes, 1)
    fim = date(ano + (mes == 12), 1 if mes == 12 else mes + 1, 1)
    with get_connection() as conn:
        row = conn.execute("""SELECT COALESCE(SUM(CASE WHEN tipo='receita' THEN valor ELSE 0 END),0) receita,
            COALESCE(SUM(CASE WHEN tipo='despesa' THEN valor ELSE 0 END),0) despesa FROM transacoes
            WHERE usuario_id=? AND guild_id=? AND data>=? AND data<?""",
            (usuario_id, guild_id, inicio.isoformat(), fim.isoformat())).fetchone()
        return dict(row)


def marcar_fatura_paga(fatura_id: int, usuario_id: str, guild_id: str, competencia: str):
    with get_connection() as conn:
        cur = conn.execute("UPDATE faturas SET paga_em=? WHERE id=? AND usuario_id=? AND guild_id=?",
                           (competencia, fatura_id, usuario_id, guild_id))
        conn.commit()
        return cur.rowcount > 0


def configurar_fuso(guild_id: str, fuso_horario: str):
    with get_connection() as conn:
        conn.execute("INSERT INTO configuracoes_servidor(guild_id,fuso_horario) VALUES(?,?) ON CONFLICT(guild_id) DO UPDATE SET fuso_horario=excluded.fuso_horario",
                     (guild_id, fuso_horario))
        conn.commit()


def obter_fuso(guild_id: str):
    with get_connection() as conn:
        row = conn.execute("SELECT fuso_horario FROM configuracoes_servidor WHERE guild_id=?", (guild_id,)).fetchone()
        return row[0] if row else "America/Sao_Paulo"


def backup_database():
    """Cria backup consistente do SQLite e mantém os 14 mais recentes."""
    from datetime import datetime
    backup_dir = Path(DB_PATH).resolve().parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    destino = backup_dir / f"financas-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    origem = sqlite3.connect(DB_PATH, timeout=10)
    copia = sqlite3.connect(destino)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    antigos = sorted(backup_dir.glob("financas-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for antigo in antigos[14:]:
        antigo.unlink(missing_ok=True)
    return destino


def deletar_transacao(transacao_id: int, usuario_id: str, guild_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM transacoes WHERE id = ? AND usuario_id = ? AND guild_id = ?
        """, (transacao_id, usuario_id, guild_id))
        conn.commit()
        return cursor.rowcount > 0


def definir_meta(usuario_id: str, guild_id: str, categoria: str, valor_limite: float):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO metas (usuario_id, guild_id, categoria, valor_limite)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(usuario_id, guild_id, categoria)
            DO UPDATE SET valor_limite = excluded.valor_limite
        """, (usuario_id, guild_id, categoria.strip().casefold(), valor_limite))
        conn.commit()


def obter_metas(usuario_id: str, guild_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM metas WHERE usuario_id = ? AND guild_id = ?
        """, (usuario_id, guild_id))
        return cursor.fetchall()


def obter_gasto_categoria_mes_atual(usuario_id: str, guild_id: str, categoria: str) -> float:
    agora = datetime.now()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0) as total
            FROM transacoes
            WHERE usuario_id = ? AND guild_id = ? AND categoria = ? AND tipo = 'despesa'
              AND data >= ? AND data < ?
        """, (usuario_id, guild_id, categoria.strip().casefold(), date(agora.year, agora.month, 1).isoformat(),
              date(agora.year + (agora.month == 12), 1 if agora.month == 12 else agora.month + 1, 1).isoformat()))
        row = cursor.fetchone()
        return row["total"] if row else 0.0


# ---------------------- Faturas / lembretes ----------------------

def proximo_vencimento(dia_vencimento: int, referencia: date = None) -> date:
    """Calcula a próxima data de vencimento a partir de uma referência (hoje, por padrão)."""
    referencia = referencia or date.today()
    ano, mes = referencia.year, referencia.month
    ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
    dia = min(dia_vencimento, ultimo_dia_mes)
    candidato = date(ano, mes, dia)

    if candidato < referencia:
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
        ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
        dia = min(dia_vencimento, ultimo_dia_mes)
        candidato = date(ano, mes, dia)

    return candidato


def adicionar_fatura(usuario_id: str, guild_id: str, nome: str, valor: float,
                      dia_vencimento: int, dias_aviso: int = 3):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO faturas (usuario_id, guild_id, nome, valor, dia_vencimento, dias_aviso)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (usuario_id, guild_id, nome, valor, dia_vencimento, dias_aviso))
        conn.commit()
        return cursor.lastrowid


def obter_faturas(usuario_id: str, guild_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM faturas WHERE usuario_id = ? AND guild_id = ? ORDER BY dia_vencimento
        """, (usuario_id, guild_id))
        return cursor.fetchall()


def obter_todas_faturas():
    """Usado pela tarefa em segundo plano que checa lembretes de todo mundo."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faturas")
        return cursor.fetchall()


def deletar_fatura(fatura_id: int, usuario_id: str, guild_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM faturas WHERE id = ? AND usuario_id = ? AND guild_id = ?
        """, (fatura_id, usuario_id, guild_id))
        conn.commit()
        return cursor.rowcount > 0


def marcar_fatura_notificada(fatura_id: int, data_iso: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE faturas SET ultima_notificacao = ? WHERE id = ?
        """, (data_iso, fatura_id))
        conn.commit()
