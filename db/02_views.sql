-- ============================================================================
-- Conversational BI / Data Agent Semantic Layer Views
-- Deterministic calculation of GMV, Revenue, COGS, Margin, and Rolling Metrics
-- ============================================================================

-- View 1: Detailed Order Items with Pre-calculated Line-level Business Metrics
CREATE OR REPLACE VIEW v_order_lines AS
SELECT 
    oi.order_item_id,
    o.order_id,
    o.order_date,
    o.channel,
    o.status,
    o.payment_method,
    
    -- Store dimensions
    s.store_id,
    s.store_name,
    s.city AS store_city,
    s.region AS store_region,
    
    -- Customer dimensions
    c.customer_id,
    c.customer_name,
    c.segment AS customer_segment,
    c.city AS customer_city,
    c.region AS customer_region,
    
    -- Product dimensions
    p.product_id,
    p.product_name,
    p.category AS product_category,
    p.brand AS product_brand,
    
    -- Raw item measures
    oi.qty,
    oi.unit_price,
    oi.discount,
    p.unit_cost,
    
    -- Business Metrics per Line
    -- GMV = (qty * unit_price) - discount
    (oi.qty * oi.unit_price - oi.discount) AS gmv,
    
    -- Revenue = GMV for status = 'Completed' only
    CASE 
        WHEN o.status = 'Completed' THEN (oi.qty * oi.unit_price - oi.discount) 
        ELSE 0.00 
    END AS revenue,
    
    -- COGS = (qty * unit_cost) for status = 'Completed' only
    CASE 
        WHEN o.status = 'Completed' THEN (oi.qty * p.unit_cost) 
        ELSE 0.00 
    END AS cogs,
    
    -- Margin = Revenue - COGS
    CASE 
        WHEN o.status = 'Completed' THEN ((oi.qty * oi.unit_price - oi.discount) - (oi.qty * p.unit_cost)) 
        ELSE 0.00 
    END AS margin

FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
JOIN stores s ON o.store_id = s.store_id
JOIN customers c ON o.customer_id = c.customer_id;

-- View 2: Order-level Aggregated View (for accurate order counts, AOV, cancel rates)
CREATE OR REPLACE VIEW v_orders AS
SELECT 
    o.order_id,
    o.order_date,
    o.channel,
    o.status,
    o.payment_method,
    
    -- Store info
    s.store_id,
    s.store_name,
    s.city AS store_city,
    s.region AS store_region,
    
    -- Customer info
    c.customer_id,
    c.customer_name,
    c.segment AS customer_segment,
    c.city AS customer_city,
    c.region AS customer_region,
    
    -- Order level totals
    COUNT(oi.order_item_id) AS total_items,
    SUM(oi.qty) AS total_units,
    SUM(oi.qty * oi.unit_price - oi.discount) AS order_gmv,
    
    CASE 
        WHEN o.status = 'Completed' THEN SUM(oi.qty * oi.unit_price - oi.discount)
        ELSE 0.00 
    END AS order_revenue,
    
    CASE 
        WHEN o.status = 'Completed' THEN SUM(oi.qty * p.unit_cost)
        ELSE 0.00 
    END AS order_cogs,
    
    CASE 
        WHEN o.status = 'Completed' THEN SUM((oi.qty * oi.unit_price - oi.discount) - (oi.qty * p.unit_cost))
        ELSE 0.00 
    END AS order_margin,
    
    CASE WHEN o.status = 'Completed' THEN 1 ELSE 0 END AS is_completed,
    CASE WHEN o.status = 'Cancelled' THEN 1 ELSE 0 END AS is_cancelled

FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
JOIN stores s ON o.store_id = s.store_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY 
    o.order_id, o.order_date, o.channel, o.status, o.payment_method,
    s.store_id, s.store_name, s.city, s.region,
    c.customer_id, c.customer_name, c.segment, c.city, c.region;

-- View 3: Daily Summary & 7-Day Rolling Average for Anomaly Detection (Question 10)
CREATE OR REPLACE VIEW v_daily_revenue AS
WITH daily_agg AS (
    SELECT 
        o.order_date,
        COUNT(o.order_id) AS total_orders,
        COUNT(CASE WHEN o.status = 'Completed' THEN 1 END) AS completed_orders,
        COUNT(CASE WHEN o.status = 'Cancelled' THEN 1 END) AS cancelled_orders,
        COALESCE(SUM(CASE WHEN o.status = 'Completed' THEN (oi.qty * oi.unit_price - oi.discount) END), 0.00) AS daily_revenue,
        COALESCE(SUM(oi.qty * oi.unit_price - oi.discount), 0.00) AS daily_gmv
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY o.order_date
),
with_rolling AS (
    SELECT 
        d.order_date,
        d.total_orders,
        d.completed_orders,
        d.cancelled_orders,
        ROUND((d.cancelled_orders::numeric / NULLIF(d.total_orders, 0)::numeric) * 100, 2) AS cancel_rate_pct,
        d.daily_gmv,
        d.daily_revenue,
        -- Rolling 7-day average of previous 7 days (excluding current day)
        COALESCE(
            AVG(d.daily_revenue) OVER (
                ORDER BY d.order_date 
                ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
            ), 
            0.00
        ) AS avg_revenue_prev_7d
    FROM daily_agg d
)
SELECT 
    w.order_date,
    w.daily_revenue,
    ROUND(w.avg_revenue_prev_7d::numeric, 2) AS avg_revenue_prev_7d,
    CASE 
        WHEN w.avg_revenue_prev_7d > 0 THEN 
            ROUND(((w.daily_revenue - w.avg_revenue_prev_7d) / w.avg_revenue_prev_7d * 100)::numeric, 2)
        ELSE 0.00 
    END AS pct_change_vs_7d_avg,
    CASE 
        WHEN w.avg_revenue_prev_7d > 0 AND ((w.avg_revenue_prev_7d - w.daily_revenue) / w.avg_revenue_prev_7d) > 0.30 
        THEN TRUE 
        ELSE FALSE 
    END AS is_anomaly_drop_over_30pct,
    w.total_orders,
    w.completed_orders,
    w.cancelled_orders,
    w.cancel_rate_pct
FROM with_rolling w;
