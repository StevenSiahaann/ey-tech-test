-- ============================================================================
-- Conversational BI / Data Agent Security Roles
-- Strict read-only enforcement at database level
-- ============================================================================

DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'bi_readonly') THEN
      CREATE ROLE bi_readonly WITH LOGIN PASSWORD 'bi_readonly_secure_password';
   END IF;
END
$do$;

-- Revoke all administrative privileges
ALTER ROLE bi_readonly SET default_transaction_read_only = on;
ALTER ROLE bi_readonly SET statement_timeout = '10s';

-- Grant connection to target database
GRANT CONNECT ON DATABASE ey_bi TO bi_readonly;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO bi_readonly;

-- Grant SELECT on all current and future tables and views
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bi_readonly;

-- Ensure NO write or modification privileges can be used
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM bi_readonly;
