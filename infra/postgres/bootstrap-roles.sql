\set ON_ERROR_STOP on

SELECT format('CREATE ROLE little_orbit_api LOGIN PASSWORD %L', :'api_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'little_orbit_api')
\gexec
SELECT format('CREATE ROLE little_orbit_worker LOGIN PASSWORD %L', :'worker_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'little_orbit_worker')
\gexec
SELECT format('CREATE ROLE little_orbit_media LOGIN PASSWORD %L', :'media_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'little_orbit_media')
\gexec
SELECT format('CREATE ROLE little_orbit_backup LOGIN PASSWORD %L', :'backup_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'little_orbit_backup')
\gexec

SELECT format('ALTER ROLE little_orbit_api PASSWORD %L', :'api_password') \gexec
SELECT format('ALTER ROLE little_orbit_worker PASSWORD %L', :'worker_password') \gexec
SELECT format('ALTER ROLE little_orbit_media PASSWORD %L', :'media_password') \gexec
SELECT format('ALTER ROLE little_orbit_backup PASSWORD %L', :'backup_password') \gexec

ALTER ROLE little_orbit_api NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE little_orbit_worker NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE little_orbit_media NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE little_orbit_backup NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE :"database_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database_name" TO
    little_orbit_api, little_orbit_worker, little_orbit_media, little_orbit_backup;
GRANT USAGE ON SCHEMA public TO
    little_orbit_api, little_orbit_worker, little_orbit_media, little_orbit_backup;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO
    little_orbit_api, little_orbit_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO
    little_orbit_api, little_orbit_worker;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO little_orbit_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO little_orbit_backup;

ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO little_orbit_api, little_orbit_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO little_orbit_api, little_orbit_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT SELECT ON TABLES TO little_orbit_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO little_orbit_backup;

SELECT 'GRANT SELECT, UPDATE ON public.attachment_jobs TO little_orbit_media'
WHERE to_regclass('public.attachment_jobs') IS NOT NULL
\gexec
SELECT 'GRANT SELECT, UPDATE ON public.note_attachments TO little_orbit_media'
WHERE to_regclass('public.note_attachments') IS NOT NULL
\gexec
SELECT 'GRANT SELECT, UPDATE ON public.attachment_storage_state TO little_orbit_media'
WHERE to_regclass('public.attachment_storage_state') IS NOT NULL
\gexec
SELECT 'GRANT SELECT, UPDATE ON public.couples TO little_orbit_media'
WHERE to_regclass('public.couples') IS NOT NULL
\gexec
SELECT 'GRANT SELECT, INSERT ON public.activity_events TO little_orbit_media'
WHERE to_regclass('public.activity_events') IS NOT NULL
\gexec
