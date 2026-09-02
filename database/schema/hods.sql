CREATE TABLE IF NOT EXISTS hods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    department VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    qualification VARCHAR(255) NOT NULL,
    experience VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    contact VARCHAR(50) NOT NULL,
    faculty_id VARCHAR(50),
    status VARCHAR(50) DEFAULT 'Active'
);
