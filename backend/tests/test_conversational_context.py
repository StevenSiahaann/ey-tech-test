"""
Unit tests for Multi-Turn Conversational Context, Morphology Disambiguation,
and Grounded Synthesis (Category vs Product Count, ORDER BY enforcement, Clean Assumptions).
"""

import unittest
from backend.app.agent.nodes.planner import plan_query
from backend.app.agent.nodes.generator import compile_sql_from_plan
from backend.app.agent.graph import process_conversational_turn
from backend.app.stores.redis_session import session_store


class TestConversationalContext(unittest.TestCase):

    def test_count_to_list_category_followup(self):
        """'emang ada berapa kategori produk?' followed by 'apa aja?' should list categories, not products."""
        s1 = {"user_message": "emang ada berapa kategori produk?", "language": "en"}
        out1 = plan_query(s1)
        plan1 = out1["plan"]
        self.assertIn("category_count", plan1.metrics)
        self.assertEqual(plan1.dimensions, [])

        s2 = {
            "user_message": "apa aja?",
            "language": "en",
            "prev_plan": plan1.model_dump(),
            "prev_result_digest": {}
        }
        out2 = plan_query(s2)
        plan2 = out2["plan"]
        self.assertEqual(plan2.intent, "exploratory")
        self.assertEqual(plan2.dimensions, ["product_category"])
        self.assertIn("product_count", plan2.metrics)

        sql2 = compile_sql_from_plan(plan2)
        self.assertIn("GROUP BY product_category", sql2)
        self.assertIn("ORDER BY total_products DESC", sql2)

    def test_kategori_produknya_morphology(self):
        """'kategori produknya?' with -nya suffix must resolve to product_category, not product revenue."""
        out = plan_query({"user_message": "kategori produknya?", "language": "en"})
        plan = out["plan"]
        self.assertEqual(plan.intent, "exploratory")
        self.assertEqual(plan.dimensions, ["product_category"])

    def test_multi_row_metric_query_has_order_by(self):
        """Any grouped metric_query must include ORDER BY so rows[0] is genuinely #1."""
        out = plan_query({"user_message": "revenue produk bulan ini", "language": "id"})
        plan = out["plan"]
        sql = compile_sql_from_plan(plan)
        self.assertIn("GROUP BY", sql)
        self.assertIn("ORDER BY total_revenue DESC", sql)

    def test_end_to_end_category_clarification_flow(self):
        """Full multi-turn flow from screenshots must distinguish 5 categories vs 28 products."""
        sid = "unit_test_cat_flow"
        session_store.clear_session(sid)

        r1 = process_conversational_turn(sid, "emang ada berapa kategori produk?", language="en")
        self.assertEqual(r1.kpis[0].value, 5)
        self.assertTrue(all("None to None" not in a for a in r1.assumptions))

        r2 = process_conversational_turn(sid, "apa aja?", language="en")
        self.assertEqual(r2.kpis[0].value, 5)
        self.assertEqual(r2.kpis[1].value, 28)

        r3 = process_conversational_turn(sid, "kategori produknya 28? apa 5?", language="en")
        self.assertEqual(r3.kpis[0].value, 5)
        self.assertEqual(r3.kpis[1].value, 28)

    def test_commander_routing_and_standalone_query(self):
        """Commander must assign the right Specialist Sub-Agent and rewrite follow-ups into standalone queries."""
        p_cat = plan_query({"user_message": "emang ada berapa kategori produk?", "language": "id"})["plan"]
        self.assertEqual(p_cat.specialist_agent, "CatalogMetadataSpecialist")

        p_follow = plan_query({
            "user_message": "apa aja?",
            "language": "id",
            "prev_plan": p_cat.model_dump(),
            "prev_result_digest": {}
        })["plan"]
        self.assertEqual(p_follow.specialist_agent, "CatalogMetadataSpecialist")
        self.assertIn("kategori produk", p_follow.standalone_query.lower())

        p_anom = plan_query({"user_message": "Revenue anomaly: drop >30% vs 7-day average", "language": "en"})["plan"]
        self.assertEqual(p_anom.specialist_agent, "AnomalyDiagnosticSpecialist")

        p_sql = plan_query({"user_message": "GMV MTD untuk region Jawa?", "language": "id"})["plan"]
        self.assertEqual(p_sql.specialist_agent, "AnalyticalSQLSpecialist")

    def test_negation_filters_single_and_multi(self):
        """'selain Jawa' -> != 'Jawa' and 'kecuali FMCG dan Electronics' -> NOT IN ('FMCG', 'Electronics')."""
        p1 = plan_query({"user_message": "GMV MTD untuk region selain Jawa?", "language": "id"})["plan"]
        self.assertEqual(len(p1.filters), 1)
        self.assertEqual(p1.filters[0].field, "store_region")
        self.assertEqual(p1.filters[0].operator, "!=")
        self.assertEqual(p1.filters[0].value, "Jawa")
        sql1 = compile_sql_from_plan(p1)
        self.assertIn("store_region != 'Jawa'", sql1)

        p2 = plan_query({"user_message": "Top 5 produk bulan lalu kecuali FMCG dan Electronics", "language": "id"})["plan"]
        cat_filters = [f for f in p2.filters if f.field == "product_category"]
        self.assertEqual(len(cat_filters), 1)
        self.assertEqual(cat_filters[0].operator, "NOT IN")
        self.assertEqual(cat_filters[0].value, ["FMCG", "Electronics"])
        sql2 = compile_sql_from_plan(p2)
        self.assertIn("product_category NOT IN ('FMCG', 'Electronics')", sql2)


if __name__ == "__main__":
    unittest.main()

