-- agent_db_role.sql -- the lead agent's read-only database role (agent_shell.sh `sql`).
--
-- Idempotent; upgrade.sh applies it after every start, as the database owner, so
-- tables and columns added by later migrations are covered. The role logs in only
-- through the container's local socket (`docker compose exec`); it has no password.
--
-- It can SELECT every table except the columns in the deny list below. A new
-- column on a listed table is granted only by the next run of this file, which
-- re-grants every column not denied: add a sensitive column to the list in the
-- same change that creates it.

DO $$
BEGIN
    CREATE ROLE diplomacy_agent LOGIN;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END
$$;

ALTER ROLE diplomacy_agent SET default_transaction_read_only = on;
ALTER ROLE diplomacy_agent SET statement_timeout = '30s';

DO $$
DECLARE
    deny constant jsonb := '{
        "users": ["email", "password_hash"],
        "password_reset_tokens": ["*"],
        "link_codes": ["code"],
        "games": ["join_password_hash"],
        "messages": ["text"],
        "bot_outbox": ["message", "payload"],
        "idempotency_keys": ["response_json"]
    }';
    t text;
    cols text;
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO diplomacy_agent', current_database());
    GRANT USAGE ON SCHEMA public TO diplomacy_agent;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO diplomacy_agent;
    -- Tables the owner (the role running this) creates later.
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO diplomacy_agent;

    FOR t IN SELECT jsonb_object_keys(deny) LOOP
        CONTINUE WHEN to_regclass(format('public.%I', t)) IS NULL;
        EXECUTE format('REVOKE SELECT ON public.%I FROM diplomacy_agent', t);
        CONTINUE WHEN deny -> t ? '*';
        SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position)
          INTO cols
          FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = t
           AND NOT (deny -> t ? column_name);
        IF cols IS NOT NULL THEN
            EXECUTE format('GRANT SELECT (%s) ON public.%I TO diplomacy_agent', cols, t);
        END IF;
    END LOOP;
END
$$;
