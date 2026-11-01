import sys

import duckdb
import numpy as np
import pandas as pd
from faker import Faker

from common import CLEAN_CSV, CLEAN_DB, CLEAN_MANIFEST, export_csv, write_db, write_manifest

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 42
N_CUSTOMERS, N_PRODUCTS, N_ORDERS = 2000, 150, 6000
N_NAMESAKES = 15

CITIES = ["Москва", "Санкт-Петербург", "Нижний Новгород", "Казань", "Екатеринбург",
          "Новосибирск", "Самара", "Пенза", "Ростов-на-Дону", "Воронеж", "Уфа", "Пермь"]
CATEGORIES = ["electronics", "books", "clothing", "home", "toys", "sports", "beauty", "food"]
EMAIL_DOMAINS = ["mail.ru", "yandex.ru", "gmail.com", "rambler.ru", "bk.ru", "list.ru", "inbox.ru"]
STATUSES = np.array(["new", "paid", "shipped", "delivered", "cancelled"])
STATUS_P = [0.08, 0.10, 0.12, 0.60, 0.10]
METHODS = ["card", "sbp", "wallet", "cash_on_delivery"]


def ts(seconds):
    return pd.to_datetime(np.asarray(seconds, dtype="int64"), unit="s")


def epoch(s):
    return int(pd.Timestamp(s).timestamp())


def build_customers(rng, fake):
    n = N_CUSTOMERS
    start, end = epoch("2022-01-01"), epoch("2024-06-30")
    registered_s = rng.integers(start, end, n)
    ref = pd.Timestamp("2025-07-01")
    birth = ref - pd.to_timedelta(rng.integers(18 * 365, 75 * 365, n), unit="D")
    phones = [fake.phone_number() if rng.random() > 0.25 else None for _ in range(n)]
    logins = [fake.unique.user_name().lower() for _ in range(n)]
    domains = rng.choice(EMAIL_DOMAINS, n)
    df = pd.DataFrame({
        "customer_id": np.arange(1, n + 1),
        "full_name": [fake.name() for _ in range(n)],
        "email": [f"{u}@{d}" for u, d in zip(logins, domains)],
        "phone": phones,
        "birth_date": birth.date,
        "city": rng.choice(CITIES, n),
        "registered_at": ts(registered_s),
    })
    namesakes = rng.choice(n, 2 * N_NAMESAKES, replace=False).reshape(-1, 2)
    df.loc[namesakes[:, 1], "full_name"] = df.loc[namesakes[:, 0], "full_name"].to_numpy()
    return df, registered_s


def build_products(rng, fake):
    n = N_PRODUCTS
    rubles = np.clip(np.round(np.exp(rng.normal(np.log(1500), 0.9, n))), 50, 100000).astype(int)
    cats = rng.choice(CATEGORIES, n)
    df = pd.DataFrame({
        "product_id": np.arange(1, n + 1),
        "name": [f"{c} {fake.word().capitalize()} {i}" for i, c in enumerate(cats, 1)],
        "category": cats,
        "price": rubles.astype(float),
        "stock_qty": rng.integers(0, 500, n),
    })
    return df, rubles * 100


def build_orders_items_payments(rng, registered_s, price_cents):
    n = N_ORDERS
    cust_idx = rng.integers(0, N_CUSTOMERS, n)
    reg_s = registered_s[cust_idx]
    end_s = epoch("2025-06-30")
    ordered_s = reg_s + 3600 + (rng.random(n) * (end_s - reg_s - 3600)).astype(np.int64)
    status = rng.choice(STATUSES, n, p=STATUS_P)
    shipped_s = ordered_s + rng.integers(6 * 3600, 96 * 3600, n)
    delivered_s = shipped_s + rng.integers(24 * 3600, 240 * 3600, n)

    order_ids = np.arange(1, n + 1)
    counts = rng.choice([1, 2, 3, 4, 5], n, p=[0.35, 0.30, 0.20, 0.10, 0.05])
    item_order, item_product, item_qty = [], [], []
    for oid, k in zip(order_ids, counts):
        prods = rng.choice(N_PRODUCTS, k, replace=False)
        item_order.extend([oid] * k)
        item_product.extend(prods + 1)
        item_qty.extend(rng.integers(1, 6, k))
    items = pd.DataFrame({
        "order_item_id": np.arange(1, len(item_order) + 1),
        "order_id": item_order,
        "product_id": item_product,
        "quantity": item_qty,
    })
    items["unit_cents"] = price_cents[items["product_id"].to_numpy() - 1]
    items["line_cents"] = items["quantity"] * items["unit_cents"]
    total_cents = items.groupby("order_id")["line_cents"].sum().reindex(order_ids).to_numpy()

    has_ship = np.isin(status, ["shipped", "delivered"])
    has_deliv = status == "delivered"
    orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": cust_idx + 1,
        "status": status,
        "ordered_at": ts(ordered_s),
        "shipped_at": ts(shipped_s).where(has_ship),
        "delivered_at": ts(delivered_s).where(has_deliv),
        "total_amount": total_cents / 100.0,
    })
    items_out = pd.DataFrame({
        "order_item_id": items["order_item_id"],
        "order_id": items["order_id"],
        "product_id": items["product_id"],
        "quantity": items["quantity"],
        "unit_price": items["unit_cents"] / 100.0,
    })

    paid_mask = np.isin(status, ["paid", "shipped", "delivered"])
    pidx = np.flatnonzero(paid_mask)
    payments = pd.DataFrame({
        "payment_id": np.arange(1, len(pidx) + 1),
        "order_id": order_ids[pidx],
        "amount": total_cents[pidx] / 100.0,
        "paid_at": ts(ordered_s[pidx] + rng.integers(60, 7200, len(pidx))),
        "method": rng.choice(METHODS, len(pidx)),
    })
    return orders, items_out, payments


INVARIANTS = {
    "total_amount = sum(items)": """
        SELECT count(*) FROM orders o JOIN (
          SELECT order_id, sum(quantity * unit_price) s FROM order_items GROUP BY 1
        ) i USING (order_id) WHERE abs(o.total_amount - i.s) > 0.001""",
    "every order has items": """
        SELECT count(*) FROM orders WHERE order_id NOT IN (SELECT order_id FROM order_items)""",
    "payment amount = total": """
        SELECT count(*) FROM payments p JOIN orders o USING (order_id)
        WHERE abs(p.amount - o.total_amount) > 0.001""",
    "exactly one payment for paid/shipped/delivered": """
        SELECT count(*) FROM orders o
        WHERE (o.status IN ('paid','shipped','delivered'))
           <> (o.order_id IN (SELECT order_id FROM payments))""",
    "one payment per order": """
        SELECT count(*) FROM (SELECT order_id FROM payments GROUP BY 1 HAVING count(*) > 1)""",
    "time order": """
        SELECT count(*) FROM orders
        WHERE shipped_at < ordered_at OR delivered_at < shipped_at""",
    "order after registration": """
        SELECT count(*) FROM orders o JOIN customers c USING (customer_id)
        WHERE o.ordered_at < c.registered_at""",
    "orphan customer_id": """
        SELECT count(*) FROM orders WHERE customer_id NOT IN (SELECT customer_id FROM customers)""",
    "orphan product_id": """
        SELECT count(*) FROM order_items WHERE product_id NOT IN (SELECT product_id FROM products)""",
    "status vs dates": """
        SELECT count(*) FROM orders WHERE
          (status IN ('new','paid','cancelled') AND (shipped_at IS NOT NULL OR delivered_at IS NOT NULL))
          OR (status = 'shipped' AND (shipped_at IS NULL OR delivered_at IS NOT NULL))
          OR (status = 'delivered' AND (shipped_at IS NULL OR delivered_at IS NULL))""",
    "status in domain": """
        SELECT count(*) FROM orders
        WHERE status NOT IN ('new','paid','shipped','delivered','cancelled')""",
    "paid_at between ordered_at and shipped_at": """
        SELECT count(*) FROM payments p JOIN orders o USING (order_id)
        WHERE p.paid_at < o.ordered_at OR (o.shipped_at IS NOT NULL AND p.paid_at > o.shipped_at)""",
    "email valid": """
        SELECT count(*) FROM customers
        WHERE NOT regexp_full_match(email, '[^@\\s]+@[^@\\s]+\\.[^@\\s]+')""",
    "email unique (case-insensitive)": """
        SELECT count(*) FROM (SELECT lower(email) FROM customers GROUP BY 1 HAVING count(*) > 1)""",
    "required fields not null": """
        SELECT
          (SELECT count(*) FROM customers WHERE full_name IS NULL OR email IS NULL OR birth_date IS NULL
                                             OR city IS NULL OR registered_at IS NULL)
        + (SELECT count(*) FROM products WHERE name IS NULL OR category IS NULL OR price IS NULL OR stock_qty IS NULL)
        + (SELECT count(*) FROM orders WHERE customer_id IS NULL OR status IS NULL OR ordered_at IS NULL
                                          OR total_amount IS NULL)
        + (SELECT count(*) FROM order_items WHERE order_id IS NULL OR product_id IS NULL OR quantity IS NULL
                                               OR unit_price IS NULL)
        + (SELECT count(*) FROM payments WHERE order_id IS NULL OR amount IS NULL OR paid_at IS NULL
                                            OR method IS NULL)""",
    "positive price/quantity": """
        SELECT (SELECT count(*) FROM products WHERE price <= 0)
             + (SELECT count(*) FROM order_items WHERE quantity <= 0 OR unit_price <= 0)""",
    "primary keys unique": """
        SELECT (SELECT count(*) - count(DISTINCT customer_id) FROM customers)
             + (SELECT count(*) - count(DISTINCT product_id) FROM products)
             + (SELECT count(*) - count(DISTINCT order_id) FROM orders)
             + (SELECT count(*) - count(DISTINCT order_item_id) FROM order_items)
             + (SELECT count(*) - count(DISTINCT payment_id) FROM payments)""",
}


def check_invariants(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    ok = True
    for name, sql in INVARIANTS.items():
        bad = con.execute(sql).fetchone()[0]
        print(f"  {'OK  ' if bad == 0 else 'FAIL'} {name}: {bad}")
        ok &= bad == 0
    con.close()
    return ok


def main():
    rng = np.random.default_rng(SEED)
    Faker.seed(SEED)
    fake = Faker("ru_RU")

    customers, registered_s = build_customers(rng, fake)
    products, price_cents = build_products(rng, fake)
    orders, items, payments = build_orders_items_payments(rng, registered_s, price_cents)

    frames = {"customers": customers, "products": products, "orders": orders,
              "order_items": items, "payments": payments}
    write_db(CLEAN_DB, frames)

    print(f"clean DB: {CLEAN_DB} (seed={SEED})")
    print("invariants:")
    if not check_invariants(CLEAN_DB):
        sys.exit(1)

    tables = export_csv(CLEAN_DB, CLEAN_CSV)
    write_manifest(CLEAN_MANIFEST, SEED, tables)
    for t, info in tables.items():
        print(f"  {t:12s} {info['rows']:6d} rows  sha256={info['sha256'][:16]}")


if __name__ == "__main__":
    main()
