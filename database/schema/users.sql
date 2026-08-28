CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    department VARCHAR(255),
    student_id VARCHAR(50),
    faculty_id VARCHAR(50),
    mobile VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    must_change_password TINYINT(1) DEFAULT 0,
    temp_password_created_at TIMESTAMP NULL,
    status VARCHAR(50) DEFAULT 'Active'
);
