"""Cypher generation prompt for QA engine."""

import json
from typing import Dict


def build_combined_intent_cypher_messages(
    question: str,
    ontology_summary: Dict,
    neo4j_schema: Dict,
    project_id: str = None,
) -> list[dict[str, str]]:
    """Build LLM messages that combine intent recognition and Cypher generation in one step."""

    project_rule = ""
    if project_id:
        project_rule = (
            f"\n6. IMPORTANT: All nodes have a ``_project_id`` property for data isolation. "
            f"You MUST add a WHERE clause ``n._project_id = '{project_id}'`` (or "
            f"equivalent inline property filter) on EVERY node pattern in your query "
            f"to restrict results to the current project. Do NOT omit this filter."
        )

    system_prompt = f"""You are a Neo4j knowledge graph question-answering expert.
Given a user's natural language question, the ontology schema, and the Neo4j database schema,
you need to: 1) analyze the user's intent, 2) generate the corresponding Cypher query.

Rules:
1. ONLY generate READ queries (MATCH, RETURN, WHERE, WITH, ORDER BY, LIMIT, OPTIONAL MATCH)
2. NEVER use CREATE, DELETE, SET, REMOVE, DROP, MERGE or any write operations
3. Always add LIMIT (default 100) to prevent returning too much data
4. Use parameterized values where possible
5. Handle null values with COALESCE where appropriate{project_rule}

Output strictly valid JSON, no extra text."""

    user_prompt = f"""Ontology schema:
```json
{json.dumps(ontology_summary, ensure_ascii=False, indent=2)}
```

Neo4j schema (node labels, properties, relationship types):
```json
{json.dumps(neo4j_schema, ensure_ascii=False, indent=2)}
```

User question: "{question}"

Please output in this exact JSON format:
{{
  "intent": "short_intent_name",
  "description": "What the user wants to know",
  "entities_involved": ["Entity1", "Entity2"],
  "cypher": "MATCH (n:Label) WHERE ... RETURN ... LIMIT 100",
  "params": {{}},
  "explanation": "Brief explanation of what this query does"
}}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_cypher_generation_messages(
    question: str,
    intent_result: Dict,
    neo4j_schema: Dict,
) -> list[dict[str, str]]:
    """Build LLM messages for generating Cypher query from intent (legacy 3-step)."""

    system_prompt = """You are a Neo4j Cypher expert. Generate a Cypher query to answer the user's question.

Rules:
1. ONLY generate READ queries (MATCH, RETURN, WHERE, WITH, ORDER BY, LIMIT, OPTIONAL MATCH)
2. NEVER use CREATE, DELETE, SET, REMOVE, DROP, MERGE or any write operations
3. Always add LIMIT (default 100) to prevent returning too much data
4. Use parameterized values where possible
5. Handle null values with COALESCE where appropriate

Output strictly valid JSON with the Cypher query, no extra text."""

    user_prompt = f"""User question: "{question}"

Intent analysis:
```json
{json.dumps(intent_result, ensure_ascii=False, indent=2)}
```

Neo4j schema (node labels, properties, relationship types):
```json
{json.dumps(neo4j_schema, ensure_ascii=False, indent=2)}
```

Please output in this exact JSON format:
{{
  "cypher": "MATCH (n:Label) WHERE ... RETURN ... LIMIT 100",
  "params": {{}},
  "explanation": "Brief explanation of what this query does"
}}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
