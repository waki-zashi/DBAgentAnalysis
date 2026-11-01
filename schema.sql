CREATE TABLE customers (
    customer_id   INTEGER,
    full_name     VARCHAR,
    email         VARCHAR,
    phone         VARCHAR,
    birth_date    DATE,
    city          VARCHAR,
    registered_at TIMESTAMP
);

CREATE TABLE products (
    product_id INTEGER,
    name       VARCHAR,
    category   VARCHAR,
    price      DECIMAL(10, 2),
    stock_qty  INTEGER
);

CREATE TABLE orders (
    order_id     INTEGER,
    customer_id  INTEGER,
    status       VARCHAR,
    ordered_at   TIMESTAMP,
    shipped_at   TIMESTAMP,
    delivered_at TIMESTAMP,
    total_amount DECIMAL(12, 2)
);

CREATE TABLE order_items (
    order_item_id INTEGER,
    order_id      INTEGER,
    product_id    INTEGER,
    quantity      INTEGER,
    unit_price    DECIMAL(10, 2)
);

CREATE TABLE payments (
    payment_id INTEGER,
    order_id   INTEGER,
    amount     DECIMAL(12, 2),
    paid_at    TIMESTAMP,
    method     VARCHAR
);
