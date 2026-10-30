"""
Automated Evaluation Harness for Conversational BI Agent.
Evaluates all 10 Technical Test Scenarios:
1. GMV MTD untuk region Jawa?
2. Revenue dan margin MTD untuk FMCG di Jawa?
3. Top 5 produk berdasarkan revenue bulan lalu?
4. Channel dengan revenue tertinggi di Q1 2025?
5. Cancel rate bulan ini?
6. Segment customer dengan margin tertinggi YTD?
7. Revenue POS vs E-commerce minggu ini?
8. Store di Jakarta dengan revenue tertinggi bulan ini?
9. Multi-step follow-up conversation (contextual chaining)
10. Revenue anomaly: drop >30% vs 7-day average
"""

import uuid
from backend.app.agent.graph import process_conversational_turn
from backend.app.stores.redis_session import session_store


TEST_CASES = [
    {
        "id": 1,
        "name": "GMV MTD Jawa",
        "question": "GMV MTD untuk region Jawa?",
        "check": lambda resp: (
            resp.sql is not None and
            "v_order_lines" in resp.sql and
            "store_region = 'Jawa'" in resp.sql and
            "SUM(gmv)" in resp.sql and
            any("MTD" in a for a in resp.assumptions)
        )
    },
    {
        "id": 2,
        "name": "Revenue & Margin FMCG Jawa",
        "question": "Revenue dan margin MTD untuk FMCG di Jawa?",
        "check": lambda resp: (
            resp.sql is not None and
            "product_category = 'FMCG'" in resp.sql and
            "store_region = 'Jawa'" in resp.sql and
            "SUM(revenue)" in resp.sql and
            "SUM(margin)" in resp.sql
        )
    },
    {
        "id": 3,
        "name": "Top 5 Produk Bulan Lalu",
        "question": "Top 5 produk berdasarkan revenue bulan lalu?",
        "check": lambda resp: (
            resp.sql is not None and
            "ORDER BY total_revenue DESC" in resp.sql and
            "LIMIT 5" in resp.sql and
            "2026-09-01" in resp.sql and "2026-09-30" in resp.sql
        )
    },
    {
        "id": 4,
        "name": "Channel Tertinggi Q1 2025",
        "question": "Channel dengan revenue tertinggi di Q1 2025?",
        "check": lambda resp: (
            resp.sql is not None and
            "2025-01-01" in resp.sql and "2025-03-31" in resp.sql and
            "channel" in resp.sql and
            "LIMIT 1" in resp.sql
        )
    },
    {
        "id": 5,
        "name": "Cancel Rate Bulan Ini",
        "question": "Cancel rate bulan ini?",
        "check": lambda resp: (
            resp.sql is not None and
            "v_orders" in resp.sql and
            "cancel_rate_pct" in resp.sql
        )
    },
    {
        "id": 6,
        "name": "Segment Customer Margin Tertinggi YTD",
        "question": "Segment customer dengan margin tertinggi YTD?",
        "check": lambda resp: (
            resp.sql is not None and
            "customer_segment" in resp.sql and
            "2026-01-01" in resp.sql and
            "SUM(margin)" in resp.sql and
            "LIMIT 1" in resp.sql
        )
    },
    {
        "id": 7,
        "name": "Revenue POS vs E-commerce Minggu Ini",
        "question": "Revenue POS vs E-commerce minggu ini?",
        "check": lambda resp: (
            resp.sql is not None and
            "channel IN ('POS', 'E-commerce')" in resp.sql and
            "SUM(revenue)" in resp.sql
        )
    },
    {
        "id": 8,
        "name": "Top Store di Jakarta Bulan Ini",
        "question": "Store di Jakarta dengan revenue tertinggi bulan ini?",
        "check": lambda resp: (
            resp.sql is not None and
            "store_city = 'Jakarta'" in resp.sql and
            "LIMIT 1" in resp.sql and
            "store_name" in resp.sql
        )
    },
    {
        "id": 10,
        "name": "Revenue Anomaly Drop >30%",
        "question": "Revenue anomaly: drop >30% vs 7-day average",
        "check": lambda resp: (
            resp.sql is not None and
            "v_daily_revenue" in resp.sql and
            "is_anomaly_drop_over_30pct = TRUE" in resp.sql
        )
    }
]


def run_evaluation():
    print("=" * 70)
    print("RUNNING AUTOMATED EVALUATION: 10 TECHNICAL TEST SCENARIOS")
    print("=" * 70)

    passed = 0
    total = len(TEST_CASES) + 1 # +1 for 3-step follow-up

    # 1. Evaluate Individual Questions
    for tc in TEST_CASES:
        session_id = f"eval-{uuid.uuid4().hex[:8]}"
        resp = process_conversational_turn(session_id, tc["question"])
        ok = tc["check"](resp)
        status = "PASSED [OK]" if ok else "FAILED [X]"
        if ok:
            passed += 1
        print(f"[{tc['id']:02d}] {tc['name']:<40} : {status}")
        if not ok:
            print(f"     SQL: {resp.sql}")
            print(f"     Summary: {resp.summary}")

    # 2. Evaluate Question 9: Multi-step follow-up conversation
    print("\n[09] Multi-Step Follow-Up Conversation Context:")
    seq_session = f"eval-seq-{uuid.uuid4().hex[:8]}"
    
    # Turn 1: Revenue FMCG MTD di Jawa?
    r1 = process_conversational_turn(seq_session, "Revenue FMCG MTD di Jawa?")
    t1_ok = ("product_category = 'FMCG'" in r1.sql and "store_region = 'Jawa'" in r1.sql)
    print(f"     Turn 1 (FMCG Jawa MTD)          : {'OK' if t1_ok else 'FAIL'}")

    # Turn 2: Breakdown per city.
    r2 = process_conversational_turn(seq_session, "Breakdown per city.")
    t2_ok = ("store_city" in r2.sql and "product_category = 'FMCG'" in r2.sql)
    print(f"     Turn 2 (Breakdown per city)     : {'OK' if t2_ok else 'FAIL'}")

    # Turn 3: Top 3 store dari city tertinggi.
    r3 = process_conversational_turn(seq_session, "Top 3 store dari city tertinggi.")
    t3_ok = ("store_name" in r3.sql and "LIMIT 3" in r3.sql and "product_category = 'FMCG'" in r3.sql)
    print(f"     Turn 3 (Top 3 store in top city): {'OK' if t3_ok else 'FAIL'}")

    if t1_ok and t2_ok and t3_ok:
        passed += 1
        print("     Overall Question #9             : PASSED [OK]")
    else:
        print("     Overall Question #9             : FAILED [X]")

    print("\n" + "=" * 70)
    print(f"EVALUATION SUMMARY: {passed}/{total} SCENARIOS PASSED ({passed/total*100:.1f}%)")
    print(f"REQUIREMENT: Minimum 8/10. STATUS: {'CRITERIA MET' if passed >= 8 else 'CRITERIA NOT MET'}")
    print("=" * 70)


if __name__ == "__main__":
    run_evaluation()
