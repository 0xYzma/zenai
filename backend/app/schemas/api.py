from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ConnectionCreate(BaseModel):
    host: str
    port: int = 5432
    db_name: str
    username: str
    password: str
    read_only_role: Optional[str] = None


class ConnectionResponse(BaseModel):
    id: str
    workspace_id: str
    host: str
    port: int
    db_name: str
    status: str
    created_at: datetime


class IntrospectRequest(BaseModel):
    tables: Optional[list[str]] = None  # None = all tables


class IntrospectResponse(BaseModel):
    workspace_id: str
    tables_embedded: int
    total_columns: int
    version: int
    status: str


class SchemaTableResponse(BaseModel):
    name: str
    columns: list[dict]
    row_count: Optional[int]
    foreign_keys: list[dict]


class SchemaResponse(BaseModel):
    workspace_id: str
    version: int
    tables: list[SchemaTableResponse]


class ConnectionTestResponse(BaseModel):
    connected: bool
    message: str
    table_count: Optional[int] = None
    tables: Optional[list[dict]] = None
