-- @rule F01 customers
SELECT customer_id FROM customers WHERE email IS NULL;

-- @rule F02 customers
SELECT customer_id FROM customers WHERE city IS NULL OR trim(city) IN ('', 'N/A', '-', 'нет данных');

-- @rule F03 customers
SELECT customer_id FROM customers
WHERE email IS NOT NULL AND NOT regexp_full_match(email, '[^@\s]+@[^@\s]+\.[^@\s]+');

-- @rule F04 products
SELECT product_id FROM products WHERE price <= 0;

-- @rule F05 order_items
SELECT order_item_id FROM order_items WHERE quantity <= 0;

-- @rule F06 orders
SELECT order_id FROM orders
WHERE status IS NULL OR status NOT IN ('new', 'paid', 'shipped', 'delivered', 'cancelled');

-- @rule F07 customers
SELECT customer_id FROM customers
WHERE birth_date > CAST(registered_at AS DATE)
   OR birth_date < CAST(registered_at AS DATE) - INTERVAL 120 YEAR;

-- @rule F08 customers
SELECT c.customer_id FROM customers c
WHERE EXISTS (
    SELECT 1 FROM customers d
    WHERE d.customer_id <> c.customer_id AND d.email = c.email AND d.full_name = c.full_name
);

-- @rule F09 customers
SELECT c.customer_id FROM customers c
WHERE EXISTS (
    SELECT 1 FROM customers d
    WHERE lower(d.email) = lower(c.email) AND d.email <> c.email
);

-- @rule F10 orders
SELECT order_id FROM orders WHERE shipped_at < ordered_at OR delivered_at < shipped_at;

-- @rule F11 orders
SELECT order_id FROM orders
WHERE (status IN ('new', 'paid', 'cancelled') AND (shipped_at IS NOT NULL OR delivered_at IS NOT NULL))
   OR (status = 'shipped' AND (shipped_at IS NULL OR delivered_at IS NOT NULL))
   OR (status = 'delivered' AND (shipped_at IS NULL OR delivered_at IS NULL));

-- @rule F12 order_items
WITH m AS (
    SELECT order_item_id, unit_price, median(unit_price) OVER (PARTITION BY product_id) AS med
    FROM order_items
)
SELECT order_item_id FROM m WHERE unit_price > 20 * med;

-- @rule F13 orders
SELECT o.order_id FROM orders o
WHERE o.customer_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM customers c WHERE c.customer_id = o.customer_id);

-- @rule F14 order_items
SELECT i.order_item_id FROM order_items i
WHERE i.product_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = i.product_id);

-- @rule F15 orders
SELECT o.order_id FROM orders o
JOIN (SELECT order_id, sum(quantity * unit_price) AS s FROM order_items GROUP BY order_id) i USING (order_id)
WHERE abs(o.total_amount - i.s) > 0.005;

-- @rule F16 payments
SELECT p.payment_id FROM payments p
JOIN orders o USING (order_id)
WHERE abs(p.amount - o.total_amount) > 0.005;

-- @rule F17 orders
SELECT o.order_id FROM orders o
WHERE o.status IN ('paid', 'shipped', 'delivered')
  AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.order_id);

-- @rule F18 orders
SELECT o.order_id FROM orders o
JOIN customers c USING (customer_id)
WHERE o.ordered_at < c.registered_at;

-- @rule F19 orders
SELECT o.order_id FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id);
