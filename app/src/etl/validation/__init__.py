"""
etl/validation — Package de validation des données ETL.

Modules :
  val_files_names     → Présence des fichiers requis
  val_files_sizes     → Fichiers non-vides
  val_schema_quality  → Validation qualité avancée (schéma, types, NOT NULL)
"""
from etl.validation.val_files_names import validate_files
from etl.validation.val_files_sizes import validate_sizes
from etl.validation.val_schema_quality import validate_schema_quality

__all__ = ["validate_files", "validate_sizes", "validate_schema_quality"]
