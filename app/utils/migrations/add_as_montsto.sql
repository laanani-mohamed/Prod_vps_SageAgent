-- Ajout de la colonne AS_MontSto (montant du stock Sage) à F_ARTSTOCK.
-- Export Sage correspondant : SELECT AR_ref, as_qtesto, DE_NO, AS_MontSto FROM F_ARTSTOCK
-- Idempotent : peut être relancé sans effet. Colonne NULL jusqu'à la prochaine ingestion.
-- Exécution : psql -d <base> -f add_as_montsto.sql
DO $$
DECLARE
    s text;
BEGIN
    FOREACH s IN ARRAY ARRAY['cross', 'rousseau', 'muliparts', 'health', 'mms'] LOOP
        EXECUTE format('ALTER TABLE %I.f_artstock ADD COLUMN IF NOT EXISTS as_montsto double precision', s);
    END LOOP;
END $$;
