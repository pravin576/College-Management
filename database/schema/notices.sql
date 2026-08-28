CREATE TABLE IF NOT EXISTS notices (
    id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    department VARCHAR(255) NOT NULL,
    target_role VARCHAR(50) DEFAULT 'All',
    priority VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    attachment VARCHAR(255),
    author VARCHAR(255)
);
