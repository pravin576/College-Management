CREATE TABLE IF NOT EXISTS students (
    id VARCHAR(50) PRIMARY KEY,
    roll_number VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    mobile VARCHAR(50) NOT NULL,
    gender VARCHAR(20) NOT NULL,
    dob DATE NOT NULL,
    department VARCHAR(255) NOT NULL,
    year VARCHAR(50) DEFAULT 'First Year',
    semester VARCHAR(50) NOT NULL,
    division VARCHAR(10) NOT NULL,
    admission_year VARCHAR(10) NOT NULL,
    address TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'Active',
    photo VARCHAR(255) DEFAULT ''
);
