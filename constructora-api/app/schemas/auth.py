from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
