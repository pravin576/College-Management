CREATE TABLE IF NOT EXISTS results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    student_name VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    semester VARCHAR(50) NOT NULL,
    internal_marks FLOAT NOT NULL,
    end_sem_marks FLOAT NOT NULL,
    total_marks FLOAT NOT NULL,
    percentage FLOAT NOT NULL,
    grade VARCHAR(10) NOT NULL,
    status VARCHAR(50) NOT NULL,
    document VARCHAR(255) DEFAULT '',
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);
