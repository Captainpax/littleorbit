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

ALTER ROLE :"owner_role"
    LOGIN INHERIT SUPERUSER CREATEDB CREATEROLE REPLICATION BYPASSRLS
    CONNECTION LIMIT -1 VALID UNTIL 'infinity';
ALTER ROLE :"owner_role" RESET ALL;
ALTER ROLE little_orbit_api
    LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT -1 VALID UNTIL 'infinity';
ALTER ROLE little_orbit_api RESET ALL;
ALTER ROLE little_orbit_worker
    LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT -1 VALID UNTIL 'infinity';
ALTER ROLE little_orbit_worker RESET ALL;
ALTER ROLE little_orbit_media
    LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT -1 VALID UNTIL 'infinity';
ALTER ROLE little_orbit_media RESET ALL;
ALTER ROLE little_orbit_backup
    LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT -1 VALID UNTIL 'infinity';
ALTER ROLE little_orbit_backup RESET ALL;

SELECT DISTINCT format(
           'ALTER ROLE %I IN DATABASE %I RESET ALL',
           role_value.rolname,
           database_value.datname
       )
  FROM pg_db_role_setting role_setting
  JOIN pg_roles role_value ON role_value.oid = role_setting.setrole
  JOIN pg_database database_value ON database_value.oid = role_setting.setdatabase
 WHERE role_value.rolname = ANY(ARRAY[
           :'owner_role', 'little_orbit_api', 'little_orbit_worker',
           'little_orbit_media', 'little_orbit_backup'
       ])
\gexec

SELECT DISTINCT format('REVOKE %I FROM %I', parent.rolname, child.rolname)
  FROM pg_auth_members membership
  JOIN pg_roles parent ON parent.oid = membership.roleid
  JOIN pg_roles child ON child.oid = membership.member
 WHERE parent.rolname = ANY(ARRAY[
           :'owner_role', 'little_orbit_api', 'little_orbit_worker',
           'little_orbit_media', 'little_orbit_backup'
       ])
    OR child.rolname = ANY(ARRAY[
           :'owner_role', 'little_orbit_api', 'little_orbit_worker',
           'little_orbit_media', 'little_orbit_backup'
       ])
\gexec

SELECT DISTINCT format(
           'REVOKE ALL PRIVILEGES ON DATABASE %I FROM %s',
           database_value.datname,
           CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                ELSE quote_ident(pg_get_userbyid(item.grantee)) END
       )
  FROM pg_database database_value
 CROSS JOIN LATERAL aclexplode(COALESCE(
           database_value.datacl,
           acldefault('d', database_value.datdba)
       )) item
 WHERE database_value.datname = :'database_name'
   AND item.grantee <> database_value.datdba
\gexec

SELECT DISTINCT format(
           'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM %s',
           namespace_value.nspname,
           CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                ELSE quote_ident(pg_get_userbyid(item.grantee)) END
       )
  FROM pg_namespace namespace_value
 CROSS JOIN LATERAL aclexplode(COALESCE(
           namespace_value.nspacl,
           acldefault('n', namespace_value.nspowner)
       )) item
 WHERE namespace_value.nspname = 'public'
   AND item.grantee <> namespace_value.nspowner
\gexec

SELECT DISTINCT format(
           'REVOKE ALL PRIVILEGES ON %s %I.%I FROM %s',
           CASE WHEN object_value.relkind = 'S' THEN 'SEQUENCE' ELSE 'TABLE' END,
           namespace_value.nspname,
           object_value.relname,
           CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                ELSE quote_ident(pg_get_userbyid(item.grantee)) END
       )
  FROM pg_class object_value
  JOIN pg_namespace namespace_value ON namespace_value.oid = object_value.relnamespace
 CROSS JOIN LATERAL aclexplode(COALESCE(
           object_value.relacl,
           acldefault(
               CASE WHEN object_value.relkind = 'S' THEN 'S'::"char" ELSE 'r'::"char" END,
               object_value.relowner
           )
       )) item
 WHERE namespace_value.nspname = 'public'
   AND object_value.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
   AND item.grantee <> object_value.relowner
\gexec

SELECT DISTINCT format(
           'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I '
           'REVOKE ALL PRIVILEGES ON %s FROM %s',
           pg_get_userbyid(default_value.defaclrole),
           namespace_value.nspname,
           CASE default_value.defaclobjtype
               WHEN 'r' THEN 'TABLES'
               WHEN 'S' THEN 'SEQUENCES'
           END,
           CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                ELSE quote_ident(pg_get_userbyid(item.grantee)) END
       )
  FROM pg_default_acl default_value
  JOIN pg_namespace namespace_value ON namespace_value.oid = default_value.defaclnamespace
 CROSS JOIN LATERAL aclexplode(default_value.defaclacl) item
 WHERE namespace_value.nspname = 'public'
   AND default_value.defaclobjtype IN ('r', 'S')
   AND item.grantee <> default_value.defaclrole
\gexec

GRANT CONNECT ON DATABASE :"database_name" TO PUBLIC;
GRANT CONNECT ON DATABASE :"database_name" TO
    little_orbit_api, little_orbit_worker, little_orbit_media, little_orbit_backup;
GRANT USAGE ON SCHEMA public TO PUBLIC;
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
