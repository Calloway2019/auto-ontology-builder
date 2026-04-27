"""Stage 3: Relation discovery prompt."""

from typing import Dict
import json


def build_relation_discovery_messages(
    stage1_result: Dict,
    stage2_result: Dict,
) -> list[dict[str, str]]:
    """Build LLM messages for discovering relations between entities."""

    system_prompt = """You are an ontology engineer. Based on the identified entities and schema analysis,
discover relationships between entities.

Relationship detection criteria:
- Foreign key associations (column references between tables)
- Common attributes (shared column names across entities)
- Business logic (hierarchical, dependency, association relationships)

Naming conventions:
- Relationship type: UPPER_SNAKE_CASE (e.g., HAS_PLAN, REQUIRES, BELONGS_TO)
- Each relationship must specify source and target entities with their join keys
- Infer cardinality: 1:1, 1:N, N:M

重要：label 字段必须使用中文，description 字段必须使用中文描述。

Output strictly valid JSON, no extra text."""

    user_prompt = f"""Schema analysis (foreign keys):
```json
{json.dumps(stage1_result, ensure_ascii=False, indent=2)}
```

Identified entities:
```json
{json.dumps(stage2_result, ensure_ascii=False, indent=2)}
```

Please output relation definitions in this exact JSON format:
{{
  "relations": [
    {{
      "name": "RELATION_NAME",
      "label": "关系的中文名称",
      "source_entity": "SourceEntityName",
      "target_entity": "TargetEntityName",
      "source_key": "column_in_source_entity",
      "target_key": "column_in_target_entity",
      "cardinality": "1:N",
      "description": "关系的业务含义描述（中文）"
    }}
  ]
}}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
