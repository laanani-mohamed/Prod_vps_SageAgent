-- Profils directeur / collaborateur sur auth.users.
-- À exécuter juste AVANT de redémarrer SageAgent_api avec le nouveau code : l'API actuelle exige
-- encore le rôle "analyst", la nouvelle exige "directeur" ou "collaborateur".
--   psql ... -f /opt/SageAgent/app/utils/auth/migration_profils.sql && sudo systemctl restart SageAgent_api
BEGIN;

-- Code collaborateur Sage (F_COLLABORATEUR.co_no) : renseigné pour un collaborateur, NULL pour un directeur
ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS co_no integer;

-- Comptes existants (un par client) : accès complet, comme aujourd'hui
UPDATE auth.users SET roles = '{directeur}' WHERE roles = '{analyst}';

-- Un seul rôle par utilisateur ; un collaborateur a un co_no réel (> 0, 0 = "Non identifié") et un seul schéma.
-- COALESCE(..., false) : un CHECK qui vaut NULL est accepté par PostgreSQL (ex : co_no NULL → "co_no > 0" = NULL)
ALTER TABLE auth.users ALTER COLUMN roles SET DEFAULT '{directeur}';
ALTER TABLE auth.users ADD CONSTRAINT chk_profil CHECK (COALESCE(
       (roles = '{directeur}'     AND co_no IS NULL)
    OR (roles = '{collaborateur}' AND co_no > 0 AND cardinality(allowed_schemas) = 1),
    false
));

COMMIT;

-- Retour arrière (avec l'ancien code de l'API) :
--   ALTER TABLE auth.users DROP CONSTRAINT chk_profil;
--   UPDATE auth.users SET roles = '{analyst}' WHERE roles = '{directeur}';
--   ALTER TABLE auth.users ALTER COLUMN roles SET DEFAULT '{vendeur}';
--   ALTER TABLE auth.users DROP COLUMN co_no;
