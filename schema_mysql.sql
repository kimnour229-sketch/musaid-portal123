-- =====================================================================
-- مخطط قاعدة بيانات MySQL لمنصة مساعد (Musaid Portal)
-- MySQL / MariaDB schema — mirrors the original SQLite schema 1:1
--
-- Conversion notes (SQLite -> MySQL):
--   * INTEGER PRIMARY KEY AUTOINCREMENT  -> INT AUTO_INCREMENT PRIMARY KEY
--   * TEXT ... UNIQUE                    -> VARCHAR(255) (MySQL cannot put a
--                                           UNIQUE index on an unbounded TEXT)
--   * Other TEXT (free-form bodies)      -> TEXT
--   * BOOLEAN DEFAULT 0                  -> TINYINT(1) DEFAULT 0
--   * TIMESTAMP DEFAULT CURRENT_TIMESTAMP-> DATETIME DEFAULT CURRENT_TIMESTAMP
--   * ENGINE=InnoDB (FK support) + utf8mb4 (full Arabic + emoji coverage)
--
-- The import script preserves the original primary-key values, so foreign
-- keys stay valid. Tables are created in FK-safe order.
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- 1) departments — الأقسام
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS departments (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    dept_name VARCHAR(255) NOT NULL,
    UNIQUE KEY uq_departments_dept_name (dept_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2) subjects — المواد
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(255) NOT NULL,
    is_shared    TINYINT(1) DEFAULT 0,
    UNIQUE KEY uq_subjects_subject_name (subject_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 3) teachers — المعلمون
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teachers (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email     VARCHAR(255) NOT NULL,
    password  VARCHAR(255) NOT NULL,
    UNIQUE KEY uq_teachers_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 4) course_structure — بنية المقررات (قسم + مادة + فصل)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS course_structure (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    dept_id    INT,
    subject_id INT,
    semester   INT NOT NULL,
    KEY idx_cs_dept (dept_id),
    KEY idx_cs_subject (subject_id),
    CONSTRAINT fk_cs_dept    FOREIGN KEY (dept_id)    REFERENCES departments (id),
    CONSTRAINT fk_cs_subject FOREIGN KEY (subject_id) REFERENCES subjects (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 5) handouts — الملخصات/المذكرات (مع عدّادات المشاهدة والتنزيل)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS handouts (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id     INT,
    subject_id     INT,
    dept_id        INT,
    semester       INT,
    title          TEXT,
    notes          TEXT,
    file_path      TEXT,
    upload_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
    view_count     INT DEFAULT 0,
    download_count INT DEFAULT 0,
    KEY idx_h_teacher (teacher_id),
    KEY idx_h_subject (subject_id),
    KEY idx_h_dept (dept_id),
    CONSTRAINT fk_h_teacher FOREIGN KEY (teacher_id) REFERENCES teachers (id),
    CONSTRAINT fk_h_subject FOREIGN KEY (subject_id) REFERENCES subjects (id),
    CONSTRAINT fk_h_dept    FOREIGN KEY (dept_id)    REFERENCES departments (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 6) notes — جدول قديم (legacy) — يُرحَّل للحفاظ على البيانات
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notes (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    title        TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    teacher_name TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    dept_id      INT NOT NULL,
    semester     VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
