# Diplomacy Server: PostgreSQL Setup

## Requirements
- PostgreSQL server installed and running
- Superuser access to create users and databases

## 1. Create the Database User and Database

Open a terminal and run:

```bash
sudo -u postgres psql
```

Then, in the PostgreSQL prompt:

```sql
-- Create the user (if not exists)
CREATE USER diplomacy_user WITH PASSWORD 'password';

-- Create the database (if not exists)
CREATE DATABASE diplomacy_db OWNER diplomacy_user;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE diplomacy_db TO diplomacy_user;

-- (Optional) If you need to reset the password:
ALTER USER diplomacy_user WITH PASSWORD 'password';

\q
```

## 2. Verify Connection

Test the connection from your shell:

```bash
psql -U diplomacy_user -h localhost -d diplomacy_db
```

If you see a prompt, the connection works.

## 3. Run Alembic Migrations

From your project root:

```bash
alembic upgrade head
```

This will apply all migrations and set up the schema.

---

**Troubleshooting:**
- If you get "password authentication failed", double-check the password and user.
- If you get "database does not exist", create it as shown above.
- If you get "role does not exist", create the user as shown above.

---
