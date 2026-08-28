CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(255) NOT NULL,
    department VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    uploaded_by VARCHAR(255) NOT NULL,
    upload_date DATE NOT NULL,
    semester VARCHAR(50) DEFAULT 'All',
    subject VARCHAR(255) DEFAULT 'All'
);
