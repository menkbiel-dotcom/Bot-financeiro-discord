import tempfile
import unittest
from datetime import date
from pathlib import Path

import database as db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        test_temp = Path(__file__).resolve().parent / ".tmp"
        test_temp.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_temp)
        self.original_path = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "test.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp.cleanup()

    def test_balance_is_isolated_by_user_and_server(self):
        db.adicionar_transacao("u1", "g1", 100, "receita", "Salário")
        db.adicionar_transacao("u1", "g1", 25, "despesa", "Mercado")
        db.adicionar_transacao("u1", "g2", 800, "receita", "Salário")
        self.assertEqual(db.obter_saldo("u1", "g1"), 75)
        self.assertEqual(db.obter_saldo("u2", "g1"), 0)

    def test_edit_delete_and_duplicate_scope(self):
        item_id = db.adicionar_transacao("u1", "g1", 10, "despesa", "Lazer", "Cinema")
        self.assertTrue(db.editar_transacao(item_id, "u1", "g1", valor=12, categoria="Passeio"))
        self.assertFalse(db.editar_transacao(item_id, "u1", "g2", valor=15))
        item = db.obter_transacao(item_id, "u1", "g1")
        self.assertEqual(item["valor"], 12)
        self.assertEqual(item["categoria"], "passeio")
        self.assertFalse(db.deletar_transacao(item_id, "u1", "g2"))
        self.assertTrue(db.deletar_transacao(item_id, "u1", "g1"))

    def test_recent_limit_and_category_suggestions(self):
        for n in range(30):
            db.adicionar_transacao("u1", "g1", n + 1, "despesa", f"Cat{n:02d}")
        self.assertEqual(len(db.obter_ultimas_transacoes("u1", "g1", 99)), 25)
        self.assertLessEqual(len(db.categorias_existentes("u1", "g1")), 25)

    def test_month_summary_and_goal_spend(self):
        now = date.today()
        db.adicionar_transacao("u1", "g1", 120, "receita", "Salário")
        db.adicionar_transacao("u1", "g1", 35, "despesa", "Mercado")
        resumo = db.resumo_mensal("u1", "g1", now.year, now.month)
        self.assertEqual(resumo["receita"], 120)
        self.assertEqual(resumo["despesa"], 35)
        self.assertEqual(db.obter_gasto_categoria_mes_atual("u1", "g1", "MERCADO"), 35)

    def test_paid_invoice_is_monthly_and_timezone_is_per_guild(self):
        invoice_id = db.adicionar_fatura("u1", "g1", "Aluguel", 900, 5)
        self.assertTrue(db.marcar_fatura_paga(invoice_id, "u1", "g1", "2026-11"))
        self.assertFalse(db.marcar_fatura_paga(invoice_id, "u1", "g2", "2026-11"))
        self.assertEqual(db.obter_faturas("u1", "g1")[0]["paga_em"], "2026-11")
        self.assertEqual(db.obter_fuso("g1"), "America/Sao_Paulo")
        db.configurar_fuso("g1", "Europe/Lisbon")
        self.assertEqual(db.obter_fuso("g1"), "Europe/Lisbon")
        self.assertEqual(db.obter_fuso("g2"), "America/Sao_Paulo")

    def test_due_date_clamps_to_month_end_and_backup_is_readable(self):
        self.assertEqual(db.proximo_vencimento(31, date(2025, 2, 1)), date(2025, 2, 28))
        backup = db.backup_database()
        self.assertTrue(backup.exists())


if __name__ == "__main__":
    unittest.main()
