CREATE TABLE IF NOT EXISTS fees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    student_name VARCHAR(255) NOT NULL,
    department VARCHAR(255) NOT NULL,
    total_fees FLOAT NOT NULL,
    paid_fees FLOAT NOT NULL,
    pending_fees FLOAT NOT NULL,
    payment_date DATE,
    payment_status VARCHAR(50) NOT NULL,
    receipt_number VARCHAR(100),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);
