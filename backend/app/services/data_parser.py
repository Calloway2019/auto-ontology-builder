"""Data parser - handles Excel, CSV, and database connections."""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import create_engine, inspect

logger = logging.getLogger(__name__)


class TableMeta:
    """Parsed table metadata."""

    def __init__(self, table_name: str, columns: List[Dict], row_count: int, sample_rows: List[Dict]):
        self.table_name = table_name
        self.columns = columns
        self.row_count = row_count
        self.sample_rows = sample_rows

    def to_dict(self) -> Dict:
        return {
            "table_name": self.table_name,
            "columns": self.columns,
            "row_count": self.row_count,
            "sample_rows": self.sample_rows,
        }


class DataParser:
    """Multi-format data parser for Excel, CSV, and database tables."""

    @staticmethod
    async def parse_excel(file_path: str) -> TableMeta:
        """Parse an Excel file and extract metadata."""
        table_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            df = pd.read_excel(file_path, engine="openpyxl")
        except Exception:
            df = pd.read_excel(file_path)

        return DataParser._build_table_meta(table_name, df)

    @staticmethod
    async def parse_csv(file_path: str, encoding: str = "utf-8") -> TableMeta:
        """Parse a CSV file and extract metadata."""
        table_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            df = pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding="gbk")

        return DataParser._build_table_meta(table_name, df)

    @staticmethod
    async def parse_database_table(
        connection_string: str,
        table_name: str,
    ) -> TableMeta:
        """Parse a database table and extract metadata."""
        engine = create_engine(connection_string)
        df = pd.read_sql_table(table_name, engine, schema=None)
        # Only read up to 10000 rows for analysis
        if len(df) > 10000:
            sample_df = df.head(10000)
        else:
            sample_df = df
        meta = DataParser._build_table_meta(table_name, sample_df)
        meta.row_count = len(df)
        engine.dispose()
        return meta

    @staticmethod
    def list_database_tables(connection_string: str) -> List[str]:
        """List all tables in a database."""
        engine = create_engine(connection_string)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        engine.dispose()
        return tables

    @staticmethod
    def _build_table_meta(table_name: str, df: pd.DataFrame) -> TableMeta:
        """Build TableMeta from a pandas DataFrame."""
        columns = []
        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)
            # Map pandas dtypes to simpler types
            if "int" in dtype:
                simple_type = "integer"
            elif "float" in dtype:
                simple_type = "float"
            elif "datetime" in dtype:
                simple_type = "datetime"
            elif "bool" in dtype:
                simple_type = "boolean"
            else:
                simple_type = "string"

            # Get sample values (non-null, up to 5)
            non_null = series.dropna()
            sample_values = [str(v) for v in non_null.head(5).tolist()]

            columns.append({
                "name": str(col),
                "dtype": simple_type,
                "sample_values": sample_values,
                "null_rate": round(float(series.isnull().mean()), 4),
                "unique_count": int(series.nunique()),
            })

        # Get sample rows (up to 5)
        sample_rows = []
        for _, row in df.head(5).iterrows():
            sample_row = {}
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    sample_row[str(col)] = None
                else:
                    sample_row[str(col)] = str(val)
            sample_rows.append(sample_row)

        return TableMeta(
            table_name=table_name,
            columns=columns,
            row_count=len(df),
            sample_rows=sample_rows,
        )

    @staticmethod
    def read_full_dataframe(file_path: str, source_type: str) -> pd.DataFrame:
        """Read the full DataFrame from a file for graph loading."""
        if source_type == "excel":
            try:
                return pd.read_excel(file_path, engine="openpyxl")
            except Exception:
                return pd.read_excel(file_path)
        elif source_type == "csv":
            try:
                return pd.read_csv(file_path, encoding="utf-8")
            except UnicodeDecodeError:
                return pd.read_csv(file_path, encoding="gbk")
        else:
            raise ValueError(f"Unsupported source type for file reading: {source_type}")
