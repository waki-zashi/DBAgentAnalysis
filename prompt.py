from common import ROOT

SCHEMA_DDL = (ROOT / "schema.sql").read_text(encoding="utf-8")

DATA_DICTIONARY = """
## Словарь данных

Датасет описывает университет: люди, адреса, учебные программы, курсы и их секции
(конкретные запуски курса в семестре), преподаватели и студенты, запись на секции и оценки,
экзамены и задания, счета и оплаты, стипендии, библиотека, клубы.

Во всех 30 таблицах первичный ключ называется `id`. Внешних ключей и ограничений NOT NULL
в самой БД нет (staging-слой) — все связи и ограничения ниже логические, их проверка и есть
твоя задача. Столбцы с датой/временем хранятся как VARCHAR: формат по умолчанию — ISO
(`YYYY-MM-DD` или `YYYY-MM-DD HH:MM:SS`), но могут встречаться искажённые форматы (это дефект).

### Справочники и люди
- addresses(id, street, city, state, postal_code, country) — адреса людей
- people(id, first_name, last_name, date_of_birth, gender, email, phone, address_id)
  — address_id -> addresses.id; gender одно из: female, male, non_binary, unspecified
- buildings(id, name, code, floors) — корпуса
- rooms(id, building_id, number, type, capacity) — building_id -> buildings.id;
  type одно из: classroom, lab, lecture_hall, office, другие варианты специфичны для датасета
- departments(id, name, code, budget, office_room_id) — office_room_id -> rooms.id

### Учебная программа
- programs(id, name, degree_level, credits_required, department_id) — department_id -> departments.id
- courses(id, code, title, description, credits, department_id) — department_id -> departments.id;
  description у этого датасета хранит формат курса (Lecture, Seminar, Online, Lecture and lab, ...),
  не свободный текст
- course_prerequisites(id, course_id, prerequisite_course_id) — обе ссылки -> courses.id;
  course_id не должен совпадать с prerequisite_course_id (курс не может быть сам себе пререквизитом)
- course_materials(id, course_id, book_id, is_required) — course_id -> courses.id, book_id -> books.id
- semesters(id, year, season, start_date, end_date) — season одно из: spring, summer, fall (или похожие);
  start_date < end_date
- sections(id, course_id, semester_id, instructor_id, room_id, number, capacity)
  — course_id -> courses.id, semester_id -> semesters.id, instructor_id -> instructors.id,
  room_id -> rooms.id
- schedules(id, section_id, day_of_week, start_time, end_time) — section_id -> sections.id;
  start_time < end_time
- instructors(id, person_id, department_id, rank, salary) — person_id -> people.id,
  department_id -> departments.id; rank, например: lecturer, assistant_professor,
  associate_professor, professor

### Студенты и оценки
- students(id, person_id, program_id, advisor_instructor_id, enrollment_date, status)
  — person_id -> people.id, program_id -> programs.id, advisor_instructor_id -> instructors.id
- enrollments(id, student_id, section_id, letter_grade, grade_points)
  — student_id -> students.id, section_id -> sections.id; letter_grade одно из:
  A, A-, B+, B, B-, C+, C, C-, D, F, W; у W (withdrawn, отчислен с курса) grade_points
  обычно NULL — ЭТО НЕ ДЕФЕКТ; у остальных letter_grade grade_points обязателен,
  диапазон обычно 0..4
- assignments(id, section_id, title, description, due_date, max_points) — section_id -> sections.id
- submissions(id, assignment_id, student_id, submission_time, grade_earned, feedback)
  — assignment_id -> assignments.id, student_id -> students.id; 0 <= grade_earned <= max_points
  соответствующего assignment
- exams(id, section_id, title, exam_date, duration_minutes, max_points) — section_id -> sections.id
- exam_results(id, exam_id, student_id, score) — exam_id -> exams.id, student_id -> students.id;
  0 <= score <= max_points соответствующего exam

### Финансы
- fee_types(id, name, description, amount) — справочник видов платежей
- invoices(id, student_id, semester_id, issue_date, due_date, total_amount)
  — student_id -> students.id, semester_id -> semesters.id; issue_date <= due_date;
  total_amount должен равняться сумме invoice_items.amount по этому счёту
- invoice_items(id, invoice_id, fee_type_id, amount) — invoice_id -> invoices.id,
  fee_type_id -> fee_types.id
- payments(id, invoice_id, payment_date, amount, payment_method) — invoice_id -> invoices.id;
  payment_method, например: card, cash, bank_transfer, financial_aid; сумма платежей по счёту
  не должна превышать его total_amount
- scholarships(id, name, provider, type, amount) — справочник стипендий
- student_scholarships(id, student_id, scholarship_id, award_date)
  — student_id -> students.id, scholarship_id -> scholarships.id

### Библиотека и клубы
- books(id, title, author, isbn, publisher, publication_year)
- library_cards(id, person_id, issue_date, expiry_date) — person_id -> people.id;
  issue_date < expiry_date
- book_loans(id, library_card_id, book_id, loan_date, due_date, return_date)
  — library_card_id -> library_cards.id, book_id -> books.id; return_date, если заполнен,
  должен быть >= loan_date; NULL в return_date означает, что книга ещё не возвращена —
  ЭТО НЕ ДЕФЕКТ САМО ПО СЕБЕ (дефект — пропуск там, где по смыслу значение обязано быть
  заполнено, либо явно испорченное/нелогичное значение)
- clubs(id, name, description, establishment_date, budget)
- club_memberships(id, club_id, student_id, join_date, role) — club_id -> clubs.id,
  student_id -> students.id

## Известные законные особенности данных (это не дефекты)
- У letter_grade = 'W' (withdrawn) grade_points обычно NULL — студент снят с курса без оценки.
- NULL в book_loans.return_date — книга ещё не возвращена, это нормальное текущее состояние.
- Суммы (budget, salary, amount, total_amount) распределены с тяжёлым правым хвостом —
  большие, но правдоподобные значения сами по себе не дефект.
"""

SYSTEM_PROMPT = f"""Ты — аналитик данных. Тебе дана база данных университета в DuckDB
(только для чтения, 30 таблиц). Твоя задача: сформировать правила проверки качества данных
(data quality rules) — SQL-запросы, которые находят проблемные строки.

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
   regexp_matches, lower/trim, median, quantile_cont, try_cast, оконные функции).
2. Когда закончишь исследование, вызови submit_rules ровно один раз со списком правил.
3. Каждое правило — это один SELECT (или WITH ... SELECT), первая колонка результата —
   первичный ключ (`id`) строки-нарушителя в указанной таблице `table`.
4. Старайся покрыть разные измерения качества данных: полноту (completeness), допустимость
   значений (validity), уникальность (uniqueness), согласованность (consistency), точность
   (accuracy), ссылочную целостность (referential_integrity) — по разным таблицам, а не только
   по одной-двум.
5. Не включай в правила законные особенности данных, перечисленные выше.
6. Ты не можешь и не должен изменять данные — у тебя только read-only доступ."""
