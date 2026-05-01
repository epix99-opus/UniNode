from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from uninode.storage import connect

PASSWORD_ITERATIONS = 210_000


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email address")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return RegisterRequest.validate_email(value)


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str


class AuthResponse(BaseModel):
    user: UserResponse
    token: str


def hash_password(password: str, salt: bytes | None = None) -> str:
    password_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt,
        PASSWORD_ITERATIONS,
    )
    return ":".join(
        [
            "pbkdf2_sha256",
            str(PASSWORD_ITERATIONS),
            base64.b64encode(password_salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected_digest = encoded_hash.split(":", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        base64.b64decode(salt),
        int(iterations),
    )
    return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), expected_digest)


def make_token() -> str:
    return secrets.token_urlsafe(32)


def create_auth_router(database_path: Path) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    def get_current_user(authorization: str | None = Header(default=None)) -> UserResponse:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
            )

        token = authorization.removeprefix("Bearer ").strip()
        with connect(database_path) as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email, users.display_name
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            )
        return UserResponse(id=row["id"], email=row["email"], display_name=row["display_name"])

    @router.post(
        "/register",
        response_model=AuthResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def register(payload: RegisterRequest) -> AuthResponse:
        token = make_token()
        try:
            with connect(database_path) as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (email, display_name, password_hash)
                    VALUES (?, ?, ?)
                    """,
                    (
                        payload.email,
                        payload.display_name.strip(),
                        hash_password(payload.password),
                    ),
                )
                user_id = cursor.lastrowid
                connection.execute(
                    "INSERT INTO sessions (token, user_id) VALUES (?, ?)",
                    (token, user_id),
                )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                ) from exc
            raise

        return AuthResponse(
            user=UserResponse(
                id=int(user_id),
                email=payload.email,
                display_name=payload.display_name.strip(),
            ),
            token=token,
        )

    @router.post("/login", response_model=AuthResponse)
    def login(payload: LoginRequest) -> AuthResponse:
        with connect(database_path) as connection:
            row = connection.execute(
                """
                SELECT id, email, display_name, password_hash
                FROM users
                WHERE email = ?
                """,
                (payload.email,),
            ).fetchone()

            if row is None or not verify_password(payload.password, row["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )

            token = make_token()
            connection.execute(
                "INSERT INTO sessions (token, user_id) VALUES (?, ?)",
                (token, row["id"]),
            )

        return AuthResponse(
            user=UserResponse(id=row["id"], email=row["email"], display_name=row["display_name"]),
            token=token,
        )

    @router.get("/me", response_model=UserResponse)
    def me(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        return current_user

    return router
