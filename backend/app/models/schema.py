from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    references_table: Optional[str] = None
    references_column: Optional[str] = None
    sample_values: list[str] = field(default_factory=list)
    column_comment: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    row_count: Optional[int] = None
    foreign_keys: list[dict] = field(default_factory=list)


@dataclass
class SchemaMap:
    workspace_id: str
    tables: list[TableInfo]
    version: int = 1
