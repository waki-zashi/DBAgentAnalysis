CREATE TABLE addresses (
    id INTEGER,
    city VARCHAR,
    country VARCHAR,
    postal_code VARCHAR,
    state VARCHAR,
    street VARCHAR
);

CREATE TABLE books (
    id INTEGER,
    author VARCHAR,
    isbn VARCHAR,
    publication_year INTEGER,
    publisher VARCHAR,
    title VARCHAR
);

CREATE TABLE buildings (
    id INTEGER,
    code VARCHAR,
    floors INTEGER,
    name VARCHAR
);

CREATE TABLE clubs (
    id INTEGER,
    budget DECIMAL(14,2),
    description VARCHAR,
    establishment_date VARCHAR,
    name VARCHAR
);

CREATE TABLE fee_types (
    id INTEGER,
    amount DECIMAL(14,2),
    description VARCHAR,
    name VARCHAR
);

CREATE TABLE people (
    id INTEGER,
    address_id INTEGER,
    date_of_birth VARCHAR,
    email VARCHAR,
    first_name VARCHAR,
    gender VARCHAR,
    last_name VARCHAR,
    phone VARCHAR
);

CREATE TABLE library_cards (
    id INTEGER,
    expiry_date VARCHAR,
    issue_date VARCHAR,
    person_id INTEGER
);

CREATE TABLE book_loans (
    id INTEGER,
    book_id INTEGER,
    due_date VARCHAR,
    library_card_id INTEGER,
    loan_date VARCHAR,
    return_date VARCHAR
);

CREATE TABLE rooms (
    id INTEGER,
    building_id INTEGER,
    capacity INTEGER,
    number VARCHAR,
    type VARCHAR
);

CREATE TABLE departments (
    id INTEGER,
    budget DECIMAL(14,2),
    code VARCHAR,
    name VARCHAR,
    office_room_id INTEGER
);

CREATE TABLE courses (
    id INTEGER,
    code VARCHAR,
    credits INTEGER,
    department_id INTEGER,
    description VARCHAR,
    title VARCHAR
);

CREATE TABLE course_materials (
    id INTEGER,
    book_id INTEGER,
    course_id INTEGER,
    is_required BOOLEAN
);

CREATE TABLE course_prerequisites (
    id INTEGER,
    course_id INTEGER,
    prerequisite_course_id INTEGER
);

CREATE TABLE instructors (
    id INTEGER,
    department_id INTEGER,
    person_id INTEGER,
    rank VARCHAR,
    salary DECIMAL(14,2)
);

CREATE TABLE programs (
    id INTEGER,
    credits_required INTEGER,
    degree_level VARCHAR,
    department_id INTEGER,
    name VARCHAR
);

CREATE TABLE scholarships (
    id INTEGER,
    amount DECIMAL(14,2),
    name VARCHAR,
    provider VARCHAR,
    type VARCHAR
);

CREATE TABLE semesters (
    id INTEGER,
    end_date VARCHAR,
    season VARCHAR,
    start_date VARCHAR,
    year INTEGER
);

CREATE TABLE sections (
    id INTEGER,
    capacity INTEGER,
    course_id INTEGER,
    instructor_id INTEGER,
    number INTEGER,
    room_id INTEGER,
    semester_id INTEGER
);

CREATE TABLE assignments (
    id INTEGER,
    description VARCHAR,
    due_date VARCHAR,
    max_points INTEGER,
    section_id INTEGER,
    title VARCHAR
);

CREATE TABLE exams (
    id INTEGER,
    duration_minutes INTEGER,
    exam_date VARCHAR,
    max_points INTEGER,
    section_id INTEGER,
    title VARCHAR
);

CREATE TABLE schedules (
    id INTEGER,
    day_of_week VARCHAR,
    end_time VARCHAR,
    section_id INTEGER,
    start_time VARCHAR
);

CREATE TABLE students (
    id INTEGER,
    advisor_instructor_id INTEGER,
    enrollment_date VARCHAR,
    person_id INTEGER,
    program_id INTEGER,
    status VARCHAR
);

CREATE TABLE club_memberships (
    id INTEGER,
    club_id INTEGER,
    join_date VARCHAR,
    role VARCHAR,
    student_id INTEGER
);

CREATE TABLE enrollments (
    id INTEGER,
    grade_points DECIMAL(14,2),
    letter_grade VARCHAR,
    section_id INTEGER,
    student_id INTEGER
);

CREATE TABLE exam_results (
    id INTEGER,
    exam_id INTEGER,
    score INTEGER,
    student_id INTEGER
);

CREATE TABLE invoices (
    id INTEGER,
    due_date VARCHAR,
    issue_date VARCHAR,
    semester_id INTEGER,
    student_id INTEGER,
    total_amount DECIMAL(14,2)
);

CREATE TABLE invoice_items (
    id INTEGER,
    amount DECIMAL(14,2),
    fee_type_id INTEGER,
    invoice_id INTEGER
);

CREATE TABLE payments (
    id INTEGER,
    amount DECIMAL(14,2),
    invoice_id INTEGER,
    payment_date VARCHAR,
    payment_method VARCHAR
);

CREATE TABLE student_scholarships (
    id INTEGER,
    award_date VARCHAR,
    scholarship_id INTEGER,
    student_id INTEGER
);

CREATE TABLE submissions (
    id INTEGER,
    assignment_id INTEGER,
    feedback VARCHAR,
    grade_earned INTEGER,
    student_id INTEGER,
    submission_time VARCHAR
);
