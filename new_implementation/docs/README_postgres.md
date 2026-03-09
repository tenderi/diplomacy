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

## 4. Game IDs (why they are 7000+ and how to reset)

The **game number** you see (e.g. in the UI or API as `game_id`) is the database primary key `id` of the `games` table. When you create a game without passing a custom `game_id`, the backend sets `game_id = str(id)` after insert, so the displayed number is the auto-increment value.

- **Why 7000+?** PostgreSQL’s sequence for `games.id` advances on every insert (including from tests, restarts, or previous data). So after many creates (or a restored DB), the next id can be 7000+.

- **Make new games start from 1 (dev only):** Only do this when the `games` table is empty or you are okay with wiping it; otherwise you can get duplicate key errors.

```sql
-- Optional: clear all games (and dependent data) first
TRUNCATE games CASCADE;

-- Reset the sequence so the next game gets id = 1
ALTER SEQUENCE games_id_seq RESTART WITH 1;
```

After this, the next game you create will have `game_id` "1", then "2", and so on.

---

**Troubleshooting:**
- If you get "password authentication failed", double-check the password and user.
- If you get "database does not exist", create it as shown above.
- If you get "role does not exist", create the user as shown above.

---
