from common import ROOT

SCHEMA_DDL = (ROOT / "schema.sql").read_text(encoding="utf-8")

DATA_DICTIONARY = """
## Словарь данных

### customers (2000 строк)
- customer_id INTEGER — идентификатор, уникален
- full_name VARCHAR — ФИО. Совпадение ФИО у разных клиентов допустимо (однофамильцы существуют)
- email VARCHAR — обязателен, уникален без учёта регистра, формат local@domain.tld
- phone VARCHAR — НЕОБЯЗАТЕЛЕН, клиент может не указать телефон (это не дефект)
- birth_date DATE — обязательна; клиенту не больше 120 лет и дата рождения раньше даты регистрации
- city VARCHAR — обязателен, город доставки
- registered_at TIMESTAMP — обязателен, момент регистрации

### products (150 строк)
- product_id INTEGER — идентификатор, уникален
- name VARCHAR — обязательно
- category VARCHAR — обязательна, одна из: electronics, books, clothing, home, toys, sports, beauty, food
- price DECIMAL(10,2) — обязательна, текущая цена в рублях, должна быть > 0
- stock_qty INTEGER — обязателен, остаток на складе, >= 0

### orders (6000 строк)
- order_id INTEGER — идентификатор, уникален
- customer_id INTEGER — обязателен, ссылка на customers.customer_id
- status VARCHAR — обязателен, одно из: new, paid, shipped, delivered, cancelled
- ordered_at TIMESTAMP — обязателен, момент оформления; не раньше customers.registered_at
- shipped_at TIMESTAMP — заполняется только для статусов shipped и delivered
- delivered_at TIMESTAMP — заполняется только для статуса delivered
- total_amount DECIMAL(12,2) — обязательна; должна равняться сумме quantity*unit_price по позициям заказа

Жизненный цикл заказа (статус -> какие даты и платёж должны быть):
- new: shipped_at=NULL, delivered_at=NULL, платежа нет
- paid: shipped_at=NULL, delivered_at=NULL, платёж есть (ровно один)
- shipped: shipped_at есть, delivered_at=NULL, платёж есть
- delivered: shipped_at есть, delivered_at есть, платёж есть
- cancelled: shipped_at=NULL, delivered_at=NULL, платежа нет

Порядок времён: registered_at <= ordered_at <= paid_at <= shipped_at <= delivered_at

### order_items (~13300 строк)
- order_item_id INTEGER — идентификатор, уникален
- order_id INTEGER — обязателен, ссылка на orders.order_id
- product_id INTEGER — обязателен, ссылка на products.product_id
- quantity INTEGER — обязательно, должно быть > 0
- unit_price DECIMAL(10,2) — обязательна, цена за единицу НА МОМЕНТ ЗАКАЗА (может отличаться
  от текущей products.price — это нормально, а не дефект), должна быть > 0

### payments (~4900 строк)
- payment_id INTEGER — идентификатор, уникален
- order_id INTEGER — обязателен, ссылка на orders.order_id; у каждого заказа не более одного платежа
- amount DECIMAL(12,2) — обязательна, должна равняться orders.total_amount
- paid_at TIMESTAMP — обязателен, между ordered_at и shipped_at заказа
- method VARCHAR — обязателен, одно из: card, sbp, wallet, cash_on_delivery

## Известные законные особенности данных (это не дефекты)
- Телефон пуст у части клиентов — поле необязательное.
- У заказов в статусе new/paid/cancelled нет shipped_at и delivered_at, у shipped нет delivered_at.
- Несколько клиентов могут иметь одинаковое full_name при разных email — однофамильцы, не дубли.
- Цены товаров и суммы заказов распределены с тяжёлым правым хвостом: дорогие товары и крупные
  заказы встречаются законно.
"""

SYSTEM_PROMPT = f"""Ты — аналитик данных. Тебе дана база данных интернет-магазина в DuckDB
(только для чтения). Твоя задача: сформировать правила проверки качества данных (data quality
rules) — SQL-запросы, которые находят проблемные строки.

Схема БД (ограничений PK/FK/NOT NULL в самой БД нет — все ограничения ниже логические,
их проверка и есть твоя задача):

```sql
{SCHEMA_DDL}
```

{DATA_DICTIONARY}

Инструкции:
1. У тебя есть инструмент run_sql — используй его, чтобы исследовать данные: посмотреть
   распределения значений, найти, какие именно некорректные значения встречаются в столбцах,
   проверить гипотезы. Диалект SQL — DuckDB (близок к PostgreSQL; доступны, например,
   regexp_matches, lower/trim, median, quantile_cont, оконные функции).
2. Когда закончишь исследование, вызови submit_rules ровно один раз со списком правил.
3. Каждое правило — это один SELECT (или WITH ... SELECT), первая колонка результата —
   первичный ключ строки-нарушителя в указанной таблице `table`.
4. Старайся покрыть разные измерения качества данных: полноту (completeness), допустимость
   значений (validity), уникальность (uniqueness), согласованность (consistency), точность
   (accuracy), ссылочную целостность (referential_integrity) — по всем пяти таблицам.
5. Не включай в правила законные особенности данных, перечисленные выше.
6. Ты не можешь и не должен изменять данные — у тебя только read-only доступ."""
