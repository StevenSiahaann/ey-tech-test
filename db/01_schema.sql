-- ============================================================================
-- Conversational BI / Data Agent Database Schema
-- Standard Relational Schema for Retail & E-Commerce Transactions
-- ============================================================================

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(150) NOT NULL,
    segment VARCHAR(50) NOT NULL, -- Consumer, Corporate, SMB
    city VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL, -- Jawa, Sumatera, Kalimantan, Sulawesi, Bali & Nusa Tenggara
    signup_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS stores (
    store_id VARCHAR(50) PRIMARY KEY,
    store_name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL, -- FMCG, Electronics, Fashion, Home & Living, Health & Beauty
    brand VARCHAR(100) NOT NULL,
    unit_cost NUMERIC(14, 2) NOT NULL CHECK (unit_cost >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50) PRIMARY KEY,
    order_date DATE NOT NULL,
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id),
    channel VARCHAR(50) NOT NULL, -- POS, E-commerce, Marketplace, Mobile App, Social Commerce
    status VARCHAR(50) NOT NULL,  -- Completed, Cancelled, Returned, Pending
    payment_method VARCHAR(50) NOT NULL -- Cash, Debit Card, Credit Card, E-Wallet, Bank Transfer, COD
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id VARCHAR(50) NOT NULL REFERENCES products(product_id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    unit_price NUMERIC(14, 2) NOT NULL CHECK (unit_price >= 0),
    discount NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (discount >= 0)
);

-- ============================================================================
-- Indexes for Analytical Query Performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_channel ON orders(channel);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_store_id ON orders(store_id);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);

CREATE INDEX IF NOT EXISTS idx_stores_region ON stores(region);
CREATE INDEX IF NOT EXISTS idx_stores_city ON stores(city);

CREATE INDEX IF NOT EXISTS idx_customers_region ON customers(region);
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers(city);
CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(segment);
