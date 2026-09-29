from pydantic import BaseModel

class ColumnInfo(BaseModel):
    name: str
    type: str
    dtype: str
    unique: int

class Overview(BaseModel):
    dataset_id: str
    filename: str
    file_type: str
    rows: int
    columns: int
    column_info: list[ColumnInfo]
    type_counts: dict[str, int]
