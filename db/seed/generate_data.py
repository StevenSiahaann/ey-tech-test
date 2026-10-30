"""
Synthetic Data Generator for Conversational BI Agent.
Generates realistic, balanced retail transaction data with:
- 5 equal channels (POS, E-commerce, Marketplace, Mobile App, Social Commerce)
- Realistic calendar patterns (seasonality, weekend bumps, Ramadan/holiday peaks)
- Deliberate anomalies for Question 10 (drop >30% vs 7-day average)
- Direct output to SQL seed file (db/seed/seed_data.sql) or direct PostgreSQL insertion.
"""

import os
import random
from datetime import date, datetime, timedelta
from decimal import Decimal

# Reproducibility
SEED = 42
random.seed(SEED)

AS_OF_DATE = os.getenv("AS_OF_DATE", "2026-10-29")
START_DATE = os.getenv("START_DATE", "2024-01-01")

as_of = datetime.strptime(AS_OF_DATE, "%Y-%m-%d").date()
start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()

# ============================================================================
# Master Dimensions
# ============================================================================

REGIONS = ["Jawa", "Sumatera", "Kalimantan", "Sulawesi", "Bali & Nusa Tenggara"]
REGION_WEIGHTS = [0.55, 0.20, 0.10, 0.08, 0.07]

CITIES_BY_REGION = {
    "Jawa": ["Jakarta", "Surabaya", "Bandung", "Semarang", "Yogyakarta", "Bekasi", "Tangerang"],
    "Sumatera": ["Medan", "Palembang", "Pekanbaru", "Bandar Lampung", "Padang"],
    "Kalimantan": ["Balikpapan", "Banjarmasin", "Pontianak", "Samarinda"],
    "Sulawesi": ["Makassar", "Manado", "Palu"],
    "Bali & Nusa Tenggara": ["Denpasar", "Mataram", "Kupang"]
}

SEGMENTS = ["Consumer", "Corporate", "SMB"]
SEGMENT_WEIGHTS = [0.70, 0.10, 0.20]

CHANNELS = ["POS", "E-commerce", "Marketplace", "Mobile App", "Social Commerce"]
# Strictly equal probability (20% each)
CHANNEL_WEIGHTS = [0.20, 0.20, 0.20, 0.20, 0.20]

CATEGORIES = {
    "FMCG": [
        ("Minyak Goreng Premium 2L", "Sania", 34000, 38500),
        ("Beras Pandan Wangi 5kg", "Top Koki", 68000, 78000),
        ("Susu UHT Full Cream 1L", "Ultra Milk", 17500, 21000),
        ("Mie Instan Goreng (Karton)", "Indomie", 112000, 128000),
        ("Kopi Bubuk Arabika 250g", "Kapal Api", 28000, 34500),
        ("Sabun Mandi Cair 450ml", "Lifebuoy", 22000, 26500),
        ("Shampoo Anti Dandruff 340ml", "Clear", 35000, 42000),
        ("Deterjen Bubuk 1.8kg", "Rinso", 42000, 49500),
        ("Air Mineral 600ml (Karton)", "Aqua", 48000, 56000),
        ("Biskuit Gandum Coklat 300g", "Roma", 14000, 17500)
    ],
    "Electronics": [
        ("Smartphone Galaxy A55 5G", "Samsung", 4800000, 5699000),
        ("Wireless Noise Canceling Earbuds", "Sony", 1450000, 1899000),
        ("Smart TV 43 Inch 4K UHD", "LG", 3600000, 4299000),
        ("Powerbank 20000mAh Fast Charge", "Anker", 380000, 499000),
        ("Mechanical Keyboard RGB", "Keychron", 980000, 1290000)
    ],
    "Fashion": [
        ("Kemeja Oxford Pria Regular", "Uniqlo", 210000, 299000),
        ("Celana Chino Slim Fit", "Erigo", 160000, 235000),
        ("Sneakers Classic Canvas", "Compass", 320000, 449000),
        ("Tas Ransel Laptop Waterproof", "Eiger", 280000, 399000),
        ("Hijab Voal Premium Signature", "Buttonscarves", 140000, 225000)
    ],
    "Home & Living": [
        ("Wajan Anti Lengket Granit 28cm", "LocknLock", 220000, 319000),
        ("Set Seprei Katun King 180x200", "Kintakun", 170000, 245000),
        ("Air Fryer Digital 4L", "Philips", 750000, 999000),
        ("Dispenser Galon Bawah", "Miyako", 620000, 799000)
    ],
    "Health & Beauty": [
        ("Sunscreen Serum SPF 50", "Azarine", 45000, 62000),
        ("Moisturizer Gel Ceramide 30g", "Skintific", 95000, 135000),
        ("Micellar Water Cleanser 400ml", "Garnier", 65000, 89000),
        ("Multivitamin Complete 60 Tablet", "Blackmores", 165000, 220000)
    ]
}

STORES = [
    # Jakarta Stores (crucial for Question 8)
    ("STR-JKT-01", "Grand Indonesia Flagship Store", "Jakarta", "Jawa"),
    ("STR-JKT-02", "Central Park Mall Store", "Jakarta", "Jawa"),
    ("STR-JKT-03", "Pondok Indah Mall 2", "Jakarta", "Jawa"),
    ("STR-JKT-04", "Mall Kelapa Gading 3", "Jakarta", "Jawa"),
    ("STR-JKT-05", "Senayan City Boutique", "Jakarta", "Jawa"),
    # Other Jawa Cities
    ("STR-SBY-01", "Tunjungan Plaza 6", "Surabaya", "Jawa"),
    ("STR-SBY-02", "Pakuwon Mall Superstore", "Surabaya", "Jawa"),
    ("STR-BDG-01", "Paris Van Java Mall", "Bandung", "Jawa"),
    ("STR-BDG-02", "Trans Studio Mall", "Bandung", "Jawa"),
    ("STR-SMG-01", "Paragon Mall Semarang", "Semarang", "Jawa"),
    ("STR-YOG-01", "Pakualaman Plaza", "Yogyakarta", "Jawa"),
    ("STR-BKS-01", "Summarecon Mall Bekasi", "Bekasi", "Jawa"),
    ("STR-TNG-01", "Supermal Karawaci", "Tangerang", "Jawa"),
    # Sumatera
    ("STR-MDN-01", "Sun Plaza Medan", "Medan", "Sumatera"),
    ("STR-MDN-02", "Centre Point Medan", "Medan", "Sumatera"),
    ("STR-PLB-01", "Palembang Icon", "Palembang", "Sumatera"),
    ("STR-PKU-01", "Mall SKA Pekanbaru", "Pekanbaru", "Sumatera"),
    # Kalimantan
    ("STR-BPN-01", "Pentacity Balikpapan", "Balikpapan", "Kalimantan"),
    ("STR-BJM-01", "Duta Mall Banjarmasin", "Banjarmasin", "Kalimantan"),
    ("STR-PTK-01", "Ayani Mega Mall", "Pontianak", "Kalimantan"),
    # Sulawesi
    ("STR-MKS-01", "Trans Studio Mall Makassar", "Makassar", "Sulawesi"),
    ("STR-MKS-02", "Mall Panakkukang", "Makassar", "Sulawesi"),
    ("STR-MND-01", "Manado Town Square", "Manado", "Sulawesi"),
    # Bali & Nusa Tenggara
    ("STR-DPS-01", "Beachwalk Shopping Center", "Denpasar", "Bali & Nusa Tenggara"),
    ("STR-DPS-02", "Level 21 Mall Denpasar", "Denpasar", "Bali & Nusa Tenggara"),
    ("STR-MTR-01", "Lombok Epicentrum Mall", "Mataram", "Bali & Nusa Tenggara"),
    # Online Fulfillment Hubs (1 per region for routing online orders)
    ("STR-ONL-JAW", "DC Hub Jawa (Online Fulfillment)", "Jakarta", "Jawa"),
    ("STR-ONL-SUM", "DC Hub Sumatera (Online Fulfillment)", "Medan", "Sumatera"),
    ("STR-ONL-KAL", "DC Hub Kalimantan (Online Fulfillment)", "Balikpapan", "Kalimantan"),
    ("STR-ONL-SUL", "DC Hub Sulawesi (Online Fulfillment)", "Makassar", "Sulawesi"),
    ("STR-ONL-BAL", "DC Hub Bali-Nusra (Online Fulfillment)", "Denpasar", "Bali & Nusa Tenggara")
]

PAYMENT_METHODS_POS = ["Cash", "Debit Card", "Credit Card", "E-Wallet"]
PAYMENT_METHODS_ONLINE = ["Credit Card", "E-Wallet", "Bank Transfer", "COD"]

# Deliberate Anomaly Dates (Question 10 target anomalies)
# On these dates, order volume / revenue drops by 45-60% vs baseline
ANOMALY_DATES = {
    date(2026, 9, 14): "Nationwide payment gateway outage",
    date(2026, 5, 20): "Core system migration downtime",
    date(2025, 2, 11): "Flooding & logistics disruption in Java",
    date(2026, 10, 18): "ERP synchronization failure"
}


def generate_customers(n=3500):
    customers = []
    first_names = ["Budi", "Siti", "Ahmad", "Dewi", "Eko", "Rini", "Hendra", "Maya", "Dian", "Agus",
                   "Putri", "Reza", "Fitri", "Fajar", "Sri", "Andi", "Nur", "Bambang", "Wulandari", "Indra"]
    last_names = ["Santoso", "Wijaya", "Kusuma", "Pratama", "Saputra", "Lestari", "Hidayat", "Siregar",
                  "Pramono", "Nugroho", "Setiawan", "Utami", "Handayani", "Wibowo", "Hartono"]
    
    for i in range(1, n + 1):
        cust_id = f"CUST-{i:05d}"
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        region = random.choices(REGIONS, weights=REGION_WEIGHTS, k=1)[0]
        city = random.choice(CITIES_BY_REGION[region])
        segment = random.choices(SEGMENTS, weights=SEGMENT_WEIGHTS, k=1)[0]
        
        # Signup between 2022-01-01 and 2025-12-31
        days_offset = random.randint(0, 1200)
        signup = date(2022, 1, 1) + timedelta(days=days_offset)
        
        customers.append((cust_id, name, segment, city, region, signup))
    return customers


def generate_products():
    products = []
    idx = 1
    for cat_name, items in CATEGORIES.items():
        for p_name, brand, unit_cost, unit_price in items:
            p_id = f"PRD-{idx:04d}"
            products.append((p_id, p_name, cat_name, brand, unit_cost, unit_price))
            idx += 1
    return products


def generate_orders_and_items(customers, products, target_orders=120000):
    """
    Generates realistic daily orders across all dates from start_dt to as_of.
    Maintains balanced ~20% per channel and intentional anomalies.
    """
    orders = []
    order_items = []
    
    total_days = (as_of - start_dt).days + 1
    base_orders_per_day = target_orders // total_days
    
    # Store mapping helpers
    physical_stores_by_region = {r: [s for s in STORES if s[3] == r and not s[0].startswith("STR-ONL")] for r in REGIONS}
    online_dc_by_region = {s[3]: s[0] for s in STORES if s[0].startswith("STR-ONL")}
    
    # Channel distribution tracking to enforce exact ~20%
    channel_counts = {c: 0 for c in CHANNELS}
    
    order_counter = 1
    item_counter = 1
    
    current_date = start_dt
    while current_date <= as_of:
        # Seasonality factors
        day_of_week = current_date.weekday()
        weekend_boost = 1.25 if day_of_week in (4, 5, 6) else 1.0  # Fri-Sun peak
        
        # Ramadan / Holiday boosts (e.g., April 2024, March/April 2025, March 2026)
        is_holiday = (
            (current_date.month == 4 and current_date.year == 2024) or
            (current_date.month in (3, 4) and current_date.year == 2025) or
            (current_date.month in (3, 4) and current_date.year == 2026) or
            (current_date.month == 12)  # Year-end holiday
        )
        season_multiplier = 1.30 if is_holiday else 1.0
        
        # Check for intentional anomaly drop
        is_anomaly = current_date in ANOMALY_DATES
        anomaly_mult = 0.40 if is_anomaly else 1.0
        
        daily_n = int(base_orders_per_day * weekend_boost * season_multiplier * anomaly_mult)
        daily_n += random.randint(-10, 10)
        daily_n = max(daily_n, 15)
        
        is_recent_3_days = (as_of - current_date).days <= 3
        
        for _ in range(daily_n):
            o_id = f"ORD-{order_counter:07d}"
            order_counter += 1
            
            # Select customer
            cust = random.choice(customers)
            cust_id, _, cust_segment, cust_city, cust_region, _ = cust
            
            # Equal channel selection
            channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]
            channel_counts[channel] += 1
            
            # Routing store:
            if channel == "POS":
                # Must be a physical store in customer's region
                avail_stores = physical_stores_by_region.get(cust_region, physical_stores_by_region["Jawa"])
                # Prefer same city if possible
                same_city = [s for s in avail_stores if s[2] == cust_city]
                chosen_store = random.choice(same_city) if same_city else random.choice(avail_stores)
                store_id = chosen_store[0]
                payment = random.choice(PAYMENT_METHODS_POS)
            else:
                # Online order routes to regional online DC Hub
                store_id = online_dc_by_region.get(cust_region, "STR-ONL-JAW")
                payment = random.choice(PAYMENT_METHODS_ONLINE)
            
            # Order status distribution
            if is_recent_3_days:
                status = random.choices(
                    ["Completed", "Pending", "Cancelled"],
                    weights=[0.75, 0.20, 0.05],
                    k=1
                )[0]
            else:
                # Historical orders cannot be Pending
                status = random.choices(
                    ["Completed", "Cancelled", "Returned"],
                    weights=[0.88, 0.08, 0.04],
                    k=1
                )[0]
            
            orders.append((o_id, current_date, cust_id, store_id, channel, status, payment))
            
            # Generate 1 to 4 line items
            num_items = random.choices([1, 2, 3, 4], weights=[0.55, 0.28, 0.12, 0.05], k=1)[0]
            chosen_prods = random.sample(products, num_items)
            
            for prod in chosen_prods:
                item_id = f"ITM-{item_counter:08d}"
                item_counter += 1
                
                prod_id, _, cat_name, _, unit_cost, base_price = prod
                
                # FMCG usually has higher qty (1-5), Electronics (1)
                if cat_name == "FMCG":
                    qty = random.choices([1, 2, 3, 4, 5], weights=[0.4, 0.3, 0.15, 0.1, 0.05], k=1)[0]
                elif cat_name == "Electronics":
                    qty = 1
                else:
                    qty = random.choices([1, 2], weights=[0.8, 0.2], k=1)[0]
                
                # Nominal discount per line item
                # 60% orders no discount; 40% get 5% to 15% discount
                has_disc = random.random() < 0.40
                if has_disc:
                    disc_pct = random.uniform(0.05, 0.15)
                    disc_val = round((base_price * qty) * Decimal(str(disc_pct)), -2)
                else:
                    disc_val = Decimal("0.00")
                
                order_items.append((item_id, o_id, prod_id, qty, base_price, disc_val))
                
        current_date += timedelta(days=1)
        
    print(f"Generated {len(orders)} orders, {len(order_items)} items.")
    print("Channel distribution:")
    total_o = len(orders)
    for c, cnt in channel_counts.items():
        print(f"  {c}: {cnt} ({cnt/total_o*100:.2f}%)")
        
    return orders, order_items


def write_sql_file(customers, stores, products, orders, order_items, output_path="db/seed/seed_data.sql"):
    print(f"Writing SQL seed to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("-- Synthetic Data Seed File\n")
        f.write("BEGIN;\n\n")
        
        # 1. Customers
        f.write("-- 1. Customers\n")
        f.write("INSERT INTO customers (customer_id, customer_name, segment, city, region, signup_date) VALUES\n")
        c_lines = []
        for c in customers:
            clean_name = c[1].replace("'", "''")
            c_lines.append(f"('{c[0]}', '{clean_name}', '{c[2]}', '{c[3]}', '{c[4]}', '{c[5]}')")
        f.write(",\n".join(c_lines) + ";\n\n")
        
        # 2. Stores
        f.write("-- 2. Stores\n")
        f.write("INSERT INTO stores (store_id, store_name, city, region) VALUES\n")
        s_lines = []
        for s in stores:
            clean_sname = s[1].replace("'", "''")
            s_lines.append(f"('{s[0]}', '{clean_sname}', '{s[2]}', '{s[3]}')")
        f.write(",\n".join(s_lines) + ";\n\n")
        
        # 3. Products
        f.write("-- 3. Products\n")
        f.write("INSERT INTO products (product_id, product_name, category, brand, unit_cost) VALUES\n")
        p_lines = []
        for p in products:
            clean_pname = p[1].replace("'", "''")
            clean_brand = p[3].replace("'", "''")
            p_lines.append(f"('{p[0]}', '{clean_pname}', '{p[2]}', '{clean_brand}', {p[4]})")
        f.write(",\n".join(p_lines) + ";\n\n")
        
        # 4. Orders (batching by 5000)
        f.write("-- 4. Orders\n")
        batch_size = 5000
        for b_idx in range(0, len(orders), batch_size):
            batch = orders[b_idx:b_idx+batch_size]
            o_lines = []
            for o in batch:
                o_lines.append(f"('{o[0]}', '{o[1]}', '{o[2]}', '{o[3]}', '{o[4]}', '{o[5]}', '{o[6]}')")
            f.write("INSERT INTO orders (order_id, order_date, customer_id, store_id, channel, status, payment_method) VALUES\n")
            f.write(",\n".join(o_lines) + ";\n")
        f.write("\n")
        
        # 5. Order Items (batching by 5000)
        f.write("-- 5. Order Items\n")
        for b_idx in range(0, len(order_items), batch_size):
            batch = order_items[b_idx:b_idx+batch_size]
            it_lines = []
            for it in batch:
                it_lines.append(f"('{it[0]}', '{it[1]}', '{it[2]}', {it[3]}, {it[4]}, {it[5]})")
            f.write("INSERT INTO order_items (order_item_id, order_id, product_id, qty, unit_price, discount) VALUES\n")
            f.write(",\n".join(it_lines) + ";\n")
        f.write("\n")
        
        f.write("COMMIT;\n")
    print(f"Successfully wrote SQL seed file: {output_path} ({os.path.getsize(output_path) / 1024 / 1024:.2f} MB)")


def main():
    print(f"Generating synthetic data: {START_DATE} to {AS_OF_DATE}...")
    customers = generate_customers(n=2500)
    products = generate_products()
    orders, order_items = generate_orders_and_items(customers, products, target_orders=95000)
    
    os.makedirs("db/seed", exist_ok=True)
    write_sql_file(customers, STORES, products, orders, order_items, "db/seed/seed_data.sql")


if __name__ == "__main__":
    main()
