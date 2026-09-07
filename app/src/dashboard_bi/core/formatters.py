from typing import Optional, Final

DEVISE: Final[str] = "DH"

def format_montant(val: Optional[float], unit: str = "DH", decimals: int = 2) -> str:
    """Formate un montant avec séparateur français."""
    if val is None:
        return f"0,{ '0' * decimals } {unit}"
    if unit == "MMAD":
        val = val / 1_000_000
    elif unit == "KMAD":
        val = val / 1_000
    formatted = f"{val:,.{decimals}f}"
    # Remplacer . par , et vice versa pour format FR
    parts = formatted.split(".")
    if len(parts) == 2:
        return f"{parts[0].replace(',', ' ')}.{parts[1]} {unit}".replace(".", ",")
    return f"{formatted.replace(',', ' ')} {unit}"

def format_montant_mad(val: Optional[float]) -> str:
    return format_montant(val, unit="MAD", decimals=0)

def format_montant_mmad(val: Optional[float]) -> str:
    return format_montant(val, unit="MMAD", decimals=2)

def format_date(val: Optional[str]) -> str:
    """YYYY-MM-DD HH:MM:SS -> YYYY-MM-DD"""
    if not val or val == "-":
        return "-"
    return str(val).split(" ")[0]