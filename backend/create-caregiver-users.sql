
CREATE TABLE IF NOT EXISTS caregivers (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    care_home_name VARCHAR(200) NOT NULL,
    contact_number VARCHAR(30),
    role VARCHAR(30) NOT NULL DEFAULT 'caregiver'
        CHECK (role IN ('caregiver', 'care_home_manager')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS
    idx_caregivers_email_lower
    ON caregivers (LOWER(email));
