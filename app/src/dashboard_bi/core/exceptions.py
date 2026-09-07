class DashboardError(Exception):
    """Erreur de base du dashboard."""
    pass

class APIError(DashboardError):
    """Erreur de communication avec l'API."""
    pass

class AuthError(DashboardError):
    """Session expirée ou token invalide. Déclenche une déconnexion propre."""
    pass

class DataError(DashboardError):
    """Données invalides ou corrompues."""
    pass

class ValidationError(DashboardError):
    """Input utilisateur invalide."""
    pass