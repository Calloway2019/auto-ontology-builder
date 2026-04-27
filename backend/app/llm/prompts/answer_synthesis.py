"""Answer synthesis prompt for QA engine."""

import json
from typing import Any


def build_answer_synthesis_messages(
    question: str,
    cypher: str,
    query_result: Any,
) -> list[dict[str, str]]:
    """Build LLM messages for synthesizing natural language answer."""

    # Truncate large results
    result_str = json.dumps(query_result, ensure_ascii=False, default=str)
    if len(result_str) > 8000:
        result_str = result_str[:8000] + "\n... (results truncated)"

    system_prompt = """You are a data analysis assistant. Given a user's question and the query results
from a knowledge graph, synthesize a clear, helpful natural language answer.

Guidelines:
- 请始终使用中文回答
- If results are tabular, format as a markdown table
- Highlight key findings and numbers
- If no results found, explain possible reasons
- Be concise but informative"""

    user_prompt = f"""User question: "{question}"

Cypher query executed: {cypher}

Query results:
```json
{result_str}
```

Please provide a clear, natural language answer to the user's question based on the query results."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
