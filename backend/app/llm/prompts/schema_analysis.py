"""Stage 1: Table schema analysis prompt."""

from typing import List, Dict


def build_schema_analysis_messages(tables_meta: List[Dict]) -> List[Dict[str, str]]:
    """Build LLM messages for analyzing table schemas."""

    tables_desc = ""
    for i, table in enumerate(tables_meta, 1):
        tables_desc += f"\n### Table {i}: {table['table_name']}\n"
        tables_desc += f"- Row count: {table['row_count']}\n"
        tables_desc += f"- Columns ({len(table['columns'])}):\n"
        for col in table["columns"]:
            sample_str = ", ".join(str(v) for v in col.get("sample_values", [])[:5])
            tables_desc += (
                f"  - `{col['name']}` (type: {col['dtype']}, "
                f"null_rate: {col.get('null_rate', 0):.1%}, "
                f"unique_count: {col.get('unique_count', 0)}, "
                f"samples: [{sample_str}])\n"
            )

    system_prompt = """You are an expert database modeler and ontology designer.
Given multiple data table structures (column names, data types, sample data),
analyze each table to identify:
1. The business object each table represents
2. Primary key candidates (columns with high uniqueness, non-null, names containing Id/Key/No/Code)
3. Foreign key candidates (columns that likely reference other tables)
4. Tables that describe the same entity and could be merged (1:1 relationship)

Analysis principles:
- Focus on business semantics, not just table names
- If two tables have a 1:1 relationship describing the same business object, suggest merging
- Foreign key detection: similar column names + same data type + overlapping value ranges
- Primary key detection: high uniqueness + non-null + column name contains Id/Key/No/Code

重要：business_object 字段的描述请使用中文。

Output strictly valid JSON, no extra text."""

    user_prompt = f"""Below are {len(tables_meta)} data table structures:

{tables_desc}

Please output analysis results in this exact JSON format:
{{
  "tables": [
    {{
      "table_name": "original_table_name",
      "business_object": "Description of what business object this table represents",
      "primary_key_candidates": ["column_name"],
      "foreign_key_candidates": [
        {{
          "column": "column_in_this_table",
          "likely_references": "other_table_name",
          "referenced_column": "column_in_other_table",
          "confidence": 0.9
        }}
      ],
      "merge_with": "other_table_name or null",
      "merge_reason": "reason for merging or null"
    }}
  ]
}}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
