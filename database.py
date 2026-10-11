import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
import calendar

DB_PATH = "financas.db"


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

        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        """, (usuario_id, guild_id, valor, tipo, categoria.lower(), descricao,
              datetime.now().isoformat()))
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

        if mes and ano:
            query += " AND strftime('%m', data) = ? AND strftime('%Y', data) = ?"
            params.extend([f"{mes:02d}", str(ano)])

        query += " GROUP BY categoria ORDER BY total DESC"
        cursor.execute(query, params)
        return cursor.fetchall()


def obter_ultimas_transacoes(usuario_id: str, guild_id: str, limite: int = 10):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM transacoes
            WHERE usuario_id = ? AND guild_id = ?
            ORDER BY data DESC
            LIMIT ?
        """, (usuario_id, guild_id, limite))
        return cursor.fetchall()


def deletar_transacao(transacao_id: int, usuario_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM transacoes WHERE id = ? AND usuario_id = ?
        """, (transacao_id, usuario_id))
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
        """, (usuario_id, guild_id, categoria.lower(), valor_limite))
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
              AND strftime('%m', data) = ? AND strftime('%Y', data) = ?
        """, (usuario_id, guild_id, categoria.lower(), f"{agora.month:02d}", str(agora.year)))
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


def deletar_fatura(fatura_id: int, usuario_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM faturas WHERE id = ? AND usuario_id = ?
        """, (fatura_id, usuario_id))
        conn.commit()
        return cursor.rowcount > 0


def marcar_fatura_notificada(fatura_id: int, data_iso: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE faturas SET ultima_notificacao = ? WHERE id = ?
        """, (data_iso, fatura_id))
        conn.commit()
