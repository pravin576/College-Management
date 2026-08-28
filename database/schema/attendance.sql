CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    student_name VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    status VARCHAR(50) NOT NULL,
    faculty_id VARCHAR(50),
    department VARCHAR(255) NOT NULL,
    year VARCHAR(50) DEFAULT 'First Year',
    semester VARCHAR(50) DEFAULT 'Semester 1',
    division VARCHAR(10) DEFAULT 'A',
    subject_code VARCHAR(50) DEFAULT '',
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);
