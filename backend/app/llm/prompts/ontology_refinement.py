"""Stage 4: Ontology refinement prompt."""

from typing import Dict
import json


def build_ontology_refinement_messages(
    entities: Dict,
    relations: Dict,
    domain_hint: str = "",
) -> list[dict[str, str]]:
    """Build LLM messages for refining and validating the ontology."""

    system_prompt = """You are an ontology auditor. Please review the following ontology definition and:
1. Check naming consistency and correctness
2. Identify any missing relationships
3. Verify entity granularity (not too coarse, not too fine)
4. Generate typical query patterns (what questions users might ask)
5. Provide a domain description

重要：所有 label 和 description 字段必须使用中文。domain 和 description 使用中文。query_patterns 中的 example_questions 必须是中文问题。

Output the complete refined ontology as strictly valid JSON, no extra text."""

    user_prompt = f"""Domain hint: {domain_hint or 'Auto-detected from data'}

Entity definitions:
```json
{json.dumps(entities, ensure_ascii=False, indent=2)}
```

Relation definitions:
```json
{json.dumps(relations, ensure_ascii=False, indent=2)}
```

Please output the complete refined ontology in this exact JSON format:
{{
  "version": 1,
  "domain": "检测到的领域名称（中文）",
  "description": "本体的整体描述（中文）",
  "entities": [
    ... (refined entity definitions, same structure as input)
  ],
  "relations": [
    ... (refined relation definitions, same structure as input)
  ],
  "query_patterns": [
    {{
      "intent": "intent_name",
      "description": "查询模式的中文描述",
      "example_questions": ["示例中文问题1", "示例中文问题2"],
      "entry_entity": "StartEntityName",
      "entry_filter": "filter_property_name"
    }}
  ]
}}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
