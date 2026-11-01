# Журнал загрязнения БД

Файл сгенерирован `inject_faults.py`, руками не редактируется.

- seed загрязнения: `2026`
- seed чистой БД: `42`
- дата генерации: 2026-11-01T17:59:41
- полный построчный журнал: `data/journal.json` (эталон для оценки), плоская таблица всех изменений: `data/changes.csv`

## Размеры таблиц

| Таблица | Чистая | Грязная | Δ |
|---|---:|---:|---:|
| customers | 2000 | 2050 | +50 |
| products | 150 | 150 | +0 |
| orders | 6000 | 6000 | +0 |
| order_items | 13254 | 13166 | -88 |
| payments | 4853 | 4803 | -50 |

## Внедрённые дефекты

| ID | Ур. | Измерение | Таблица | Дефект | Эпизодов | Строк-нарушителей | Изменений |
|---|---|---|---|---|---:|---:|---:|
| F01 | L1 | completeness | customers | Обязательное поле customers.email пустое (NULL) | 100 | 100 | 100 |
| F02 | L1 | completeness | customers | customers.city содержит заглушку вместо значения ('', ' ', 'N/A', '-', 'нет данных') | 60 | 60 | 60 |
| F03 | L1 | validity | customers | customers.email имеет невалидный формат (нет '@', двойной '@', пробел, домен без точки) | 50 | 50 | 50 |
| F04 | L1 | validity | products | products.price неположительная (0 или отрицательная) | 8 | 8 | 8 |
| F05 | L1 | validity | order_items | order_items.quantity неположительное (0, -1, -2); total_amount и платёж пересчитаны согласованно | 40 | 40 | 113 |
| F06 | L1 | validity | orders | orders.status вне допустимого перечня (опечатки, регистр, пробелы, 'canceled') | 90 | 90 | 90 |
| F07 | L1 | validity | customers | customers.birth_date неправдоподобна: позже даты регистрации или возраст > 120 лет | 20 | 20 | 20 |
| F08 | L2 | uniqueness | customers | Точный дубль клиента: вставлена копия строки с новым customer_id (обе строки — нарушители) | 25 | 50 | 25 |
| F09 | L2 | uniqueness | customers | Нечёткий дубль клиента: копия с email в другом регистре, другим городом и поздней регистрацией | 25 | 50 | 25 |
| F10 | L2 | consistency | orders | Нарушен порядок времён: shipped_at < ordered_at или delivered_at < shipped_at | 80 | 80 | 80 |
| F11 | L2 | consistency | orders | Статус противоречит датам: cancelled с датами доставки, delivered без delivered_at, new с shipped_at | 70 | 70 | 100 |
| F12 | L2 | accuracy | order_items | Выброс: order_items.unit_price умножена на 100; total_amount и платёж пересчитаны согласованно | 30 | 30 | 86 |
| F13 | L3 | referential_integrity | orders | orders.customer_id ссылается на несуществующего клиента | 50 | 50 | 50 |
| F14 | L3 | referential_integrity | order_items | order_items.product_id ссылается на несуществующий товар | 50 | 50 | 50 |
| F15 | L3 | consistency | orders | orders.total_amount не равна сумме quantity * unit_price по позициям (платёж совпадает с неверной суммой) | 100 | 100 | 172 |
| F16 | L3 | consistency | payments | payments.amount не совпадает с orders.total_amount | 60 | 60 | 60 |
| F17 | L3 | consistency | orders | Заказ в статусе paid/shipped/delivered без платежа (строка payments удалена) | 50 | 50 | 50 |
| F18 | L3 | consistency | orders | Заказ оформлен раньше регистрации клиента (ordered_at < customers.registered_at) | 60 | 60 | 60 |
| F19 | L3 | consistency | orders | Заказ без позиций (все строки order_items заказа удалены) | 40 | 40 | 88 |

Всего строк-нарушителей: 1058, атомарных изменений: 1287.

## Примеры изменений

### F01 — Обязательное поле customers.email пустое (NULL)

- `customers[1782].email`: `bikovanina@inbox.ru` → `None`
- `customers[983].email`: `majaorehova@bk.ru` → `None`
- `customers[1859].email`: `ninelteterina@inbox.ru` → `None`

### F02 — customers.city содержит заглушку вместо значения ('', ' ', 'N/A', '-', 'нет данных')

- `customers[129].city`: `Нижний Новгород` → `-`
- `customers[550].city`: `Нижний Новгород` → `-`
- `customers[1972].city`: `Пермь` → `нет данных`

### F03 — customers.email имеет невалидный формат (нет '@', двойной '@', пробел, домен без точки)

- `customers[807].email`: `bfedoseev@yandex.ru` → `bfedoseev@@yandex.ru`
- `customers[903].email`: `qshcherbakova@gmail.com` → `qshcherbakova@@gmail.com`
- `customers[400].email`: `lukashchukin@yandex.ru` → `lukashchukin@@yandex.ru`

### F04 — products.price неположительная (0 или отрицательная)

- `products[43].price`: `2725.0` → `-2725.0`
- `products[119].price`: `3910.0` → `-3910.0`
- `products[30].price`: `1751.0` → `-1751.0`

### F05 — order_items.quantity неположительное (0, -1, -2); total_amount и платёж пересчитаны согласованно

- `order_items[4989].quantity`: `5` → `0`
- `orders[2246].total_amount`: `13162.0` → `1412.0`
- `payments[1814].amount`: `13162.0` → `1412.0`
- `order_items[6361].quantity`: `3` → `0`
- `orders[2868].total_amount`: `20713.0` → `7165.0`
- `payments[2314].amount`: `20713.0` → `7165.0`
- `order_items[5596].quantity`: `3` → `-2`
- `orders[2524].total_amount`: `54766.0` → `29106.0`
- `payments[2044].amount`: `54766.0` → `29106.0`

### F06 — orders.status вне допустимого перечня (опечатки, регистр, пробелы, 'canceled')

- `orders[424].status`: `delivered` → `Delivered`
- `orders[3668].status`: `delivered` → `Delivered`
- `orders[5961].status`: `delivered` → `Delivered`

### F07 — customers.birth_date неправдоподобна: позже даты регистрации или возраст > 120 лет

- `customers[1160].birth_date`: `1964-12-23 00:00:00` → `1895-12-03 00:00:00`
- `customers[1863].birth_date`: `1983-12-08 00:00:00` → `1860-05-16 00:00:00`
- `customers[772].birth_date`: `2003-07-27 00:00:00` → `1862-10-07 00:00:00`

### F08 — Точный дубль клиента: вставлена копия строки с новым customer_id (обе строки — нарушители)

- insert `customers[2001]` (копия `675`)
- insert `customers[2002]` (копия `243`)
- insert `customers[2003]` (копия `57`)

### F09 — Нечёткий дубль клиента: копия с email в другом регистре, другим городом и поздней регистрацией

- insert `customers[2026]` (копия `1823`)
- insert `customers[2027]` (копия `1650`)
- insert `customers[2028]` (копия `587`)

### F10 — Нарушен порядок времён: shipped_at < ordered_at или delivered_at < shipped_at

- `orders[1660].shipped_at`: `2024-07-24 18:57:14` → `2024-07-23 17:14:33`
- `orders[3342].delivered_at`: `2024-02-01 16:53:39` → `2024-01-28 00:09:33`
- `orders[4148].shipped_at`: `2023-10-08 08:00:50` → `2023-10-05 04:25:43`

### F11 — Статус противоречит датам: cancelled с датами доставки, delivered без delivered_at, new с shipped_at

- `orders[4373].shipped_at`: `None` → `2024-11-14 03:30:39`
- `orders[4373].delivered_at`: `None` → `2024-11-15 03:30:39`
- `orders[4826].shipped_at`: `None` → `2023-06-22 23:37:33`
- `orders[4826].delivered_at`: `None` → `2023-06-24 23:37:33`
- `orders[2637].shipped_at`: `None` → `2024-02-20 15:35:46`
- `orders[2637].delivered_at`: `None` → `2024-02-29 15:35:46`

### F12 — Выброс: order_items.unit_price умножена на 100; total_amount и платёж пересчитаны согласованно

- `order_items[4153].unit_price`: `2502.0` → `250200.0`
- `orders[1884].total_amount`: `36649.0` → `1027441.0`
- `payments[1523].amount`: `36649.0` → `1027441.0`
- `order_items[7425].unit_price`: `1625.0` → `162500.0`
- `orders[3344].total_amount`: `20876.0` → `181751.0`
- `order_items[9736].unit_price`: `447.0` → `44700.0`
- `orders[4402].total_amount`: `37126.0` → `125632.0`
- `payments[3578].amount`: `37126.0` → `125632.0`

### F13 — orders.customer_id ссылается на несуществующего клиента

- `orders[3992].customer_id`: `1134` → `900000`
- `orders[4336].customer_id`: `1921` → `900001`
- `orders[2712].customer_id`: `1057` → `900002`

### F14 — order_items.product_id ссылается на несуществующий товар

- `order_items[9685].product_id`: `103` → `90000`
- `order_items[1582].product_id`: `30` → `90001`
- `order_items[1199].product_id`: `51` → `90002`

### F15 — orders.total_amount не равна сумме quantity * unit_price по позициям (платёж совпадает с неверной суммой)

- `orders[3638].total_amount`: `10264.0` → `6279.38`
- `orders[5695].total_amount`: `7894.0` → `11699.92`
- `payments[4600].amount`: `7894.0` → `11699.92`
- `orders[4145].total_amount`: `16470.0` → `8954.65`
- `payments[3371].amount`: `16470.0` → `8954.65`

### F16 — payments.amount не совпадает с orders.total_amount

- `payments[1461].amount`: `22798.0` → `22974.0`
- `payments[3379].amount`: `5562.0` → `5742.0`
- `payments[4192].amount`: `3942.0` → `1874.34`

### F17 — Заказ в статусе paid/shipped/delivered без платежа (строка payments удалена)

- delete `payments[1492]`
- delete `payments[10]`
- delete `payments[1407]`

### F18 — Заказ оформлен раньше регистрации клиента (ordered_at < customers.registered_at)

- `orders[1911].ordered_at`: `2024-06-18 05:42:17` → `2024-02-18 10:48:25`
- `orders[5236].ordered_at`: `2024-01-26 10:00:34` → `2023-04-14 01:10:11`
- `orders[4202].ordered_at`: `2024-01-01 02:41:01` → `2023-05-06 03:19:35`

### F19 — Заказ без позиций (все строки order_items заказа удалены)

- delete `order_items[3444]`
- delete `order_items[3445]`
- delete `order_items[2200]`
- delete `order_items[2201]`
- delete `order_items[12030]`
