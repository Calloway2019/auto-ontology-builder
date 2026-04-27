"""Intent recognition prompt for QA engine."""

import json
from typing import Dict


def build_intent_recognition_messages(
    question: str,
    ontology_summary: Dict,
) -> list[dict[str, str]]:
    """Build LLM messages for recognizing user question intent."""

    system_prompt = """You are a knowledge graph question-answering assistant.
Given a user's natural language question and the ontology schema of a knowledge graph,
identify the query intent, involved entities, filters, and traversal path.

Output strictly valid JSON, no extra text."""

    user_prompt = f"""Ontology schema:
```json
{json.dumps(ontology_summary, ensure_ascii=False, indent=2)}
```

User question: "{question}"

Please output intent analysis in this exact JSON format:
{{
  "intent": "short_intent_name",
  "description": "What the user wants to know",
  "entities_involved": ["Entity1", "Entity2"],
  "filters": [
    {{
      "entity": "EntityName",
      "property": "property_name",
      "operator": "=|>|<|>=|<=|CONTAINS|IN",
      "value": "filter_value"
    }}
  ],
  "traversal_path": ["Entity1", "RELATION", "Entity2", "RELATION2", "Entity3"],
  "aggregation": "none|count|sum|avg|max|min|top_n",
  "limit": 100
}}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
