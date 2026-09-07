"""
api/auth/schemas.py

Modèles Pydantic pour l'authentification et les utilisateurs.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    allowed_schemas: List[str]
    roles: List[str]

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    allowed_schemas: List[str]
    roles: List[str] = ["vendeur"]

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre.")
        return v

class UserInDB(UserBase):
    id: int
    hashed_password: str
    is_active: bool

class UserResponse(UserBase):
    id: int
    is_active: bool

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Payload extrait et validé du JWT."""
    username: str
    roles: List[str]
    allowed_schemas: List[str]

class RefreshTokenRequest(BaseModel):
    refresh_token: str
