"""Stage 2: Entity extraction prompt."""

from typing import List, Dict


def build_entity_extraction_messages(
    stage1_result: Dict,
    tables_meta: List[Dict],
) -> List[Dict[str, str]]:
    """Build LLM messages for extracting entities from analyzed tables."""

    import json

    system_prompt = """You are an ontology engineer skilled in the Stanford Seven-Step Method for building domain ontologies.
Based on the prior schema analysis, you need to consolidate data tables into business entities and assign attributes.

Naming conventions:
- Entity name: English PascalCase (e.g., KitOrder, MaterialRequirement)
- Property name: keep original column name (camelCase or snake_case)
- Each entity must have exactly one primary key
- Merge tables that describe the same business object into one entity

重要：
- label 字段必须使用中文，description 字段必须使用中文描述。
- 每个属性的 description 也必须使用中文。
- 如果原始表中的列已经有业务含义描述（description 字段），请直接使用或基于其改写属性的 description，确保语义准确。
- 利用列的业务含义描述来判断哪些列应该作为属性、哪些应该作为主键、哪些用于关联。

Output strictly valid JSON, no extra text."""

    user_prompt = f"""Prior schema analysis:
```json
{json.dumps(stage1_result, ensure_ascii=False, indent=2)}
```

Original table structures (with column business descriptions if available):
```json
{json.dumps(tables_meta, ensure_ascii=False, indent=2)}
```

Please output entity definitions in this exact JSON format:
{{
  "entities": [
    {{
      "name": "EntityName",
      "label": "实体的中文名称",
      "description": "实体的业务含义描述（中文）",
      "source_tables": ["table1", "table2"],
      "primary_key": "key_column_name",
      "properties": [
        {{
          "name": "property_name",
          "type": "string|integer|float|date|datetime|boolean",
          "source_table": "table1",
          "source_column": "original_column_name",
          "is_key": false,
          "description": "属性描述（中文，优先使用原始列描述）"
        }}
      ]
    }}
  ]
}}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
