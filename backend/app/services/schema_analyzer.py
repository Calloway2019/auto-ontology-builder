"""Schema analyzer - rule-based pre-analysis to enrich table metadata."""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Common primary key column name patterns
PK_PATTERNS = ["id", "key", "no", "code", "number", "编号", "编码", "主键"]


class SchemaAnalyzer:
    """Rule-based pre-analysis of table schemas before LLM processing."""

    @staticmethod
    def analyze(tables_meta: List[Dict]) -> List[Dict]:
        """Enrich table metadata with rule-based analysis hints."""
        enriched = []
        all_column_names = {}  # {col_name: [table_names]}

        # Collect all column names across tables
        for table in tables_meta:
            for col in table["columns"]:
                col_name = col["name"].lower()
                if col_name not in all_column_names:
                    all_column_names[col_name] = []
                all_column_names[col_name].append(table["table_name"])

        for table in tables_meta:
            enriched_table = {**table}
            enriched_cols = []

            for col in table["columns"]:
                enriched_col = {**col}
                col_lower = col["name"].lower()

                # Primary key hint
                is_pk_candidate = (
                    col.get("null_rate", 0) == 0
                    and col.get("unique_count", 0) > 0
                    and col["unique_count"] == table["row_count"]
                    and any(pat in col_lower for pat in PK_PATTERNS)
                )
                enriched_col["pk_hint"] = is_pk_candidate

                # Foreign key hint: column name appears in other tables
                fk_tables = [
                    t for t in all_column_names.get(col_lower, [])
                    if t != table["table_name"]
                ]
                enriched_col["fk_hint"] = fk_tables if fk_tables else []

                # Cross-table match: similar column names in other tables
                cross_matches = []
                for other_table in tables_meta:
                    if other_table["table_name"] == table["table_name"]:
                        continue
                    for other_col in other_table["columns"]:
                        if other_col["name"].lower() == col_lower:
                            cross_matches.append({
                                "table": other_table["table_name"],
                                "column": other_col["name"],
                            })
                enriched_col["cross_table_matches"] = cross_matches

                enriched_cols.append(enriched_col)

            enriched_table["columns"] = enriched_cols
            enriched.append(enriched_table)

        return enriched
