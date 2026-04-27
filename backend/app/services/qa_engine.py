"""QA Engine - 2-step reasoning: Intent+Cypher → Answer."""

import re
import time
import json
import logging
from typing import Dict, Optional

from app.llm.client import llm_client
from app.llm.prompts.cypher_generation import build_combined_intent_cypher_messages
from app.llm.prompts.answer_synthesis import build_answer_synthesis_messages
from app.services.graph_manager import graph_manager

logger = logging.getLogger(__name__)


class QAEngine:
    """Knowledge graph question-answering engine with 2-step reasoning."""

    @staticmethod
    async def answer(
        question: str,
        ontology: Dict,
        context: str = "",
    ) -> Dict:
        """
        Process a natural language question through the 2-step pipeline.
        Step 1: Combined intent recognition + Cypher generation (single LLM call)
        Step 2: Execute Cypher + synthesize answer

        Returns:
            Dict with keys: question, intent, generated_cypher, raw_result, answer, confidence, latency_ms
        """
        start_time = time.time()
        result = {
            "question": question,
            "intent": "",
            "generated_cypher": "",
            "raw_result": None,
            "answer": "",
            "confidence": 0.0,
            "latency_ms": 0,
        }

        try:
            # Build ontology summary
            ontology_summary = {
                "domain": ontology.get("domain", ""),
                "entities": [
                    {
                        "name": e["name"],
                        "label": e.get("label", ""),
                        "properties": [p["name"] for p in e.get("properties", [])],
                    }
                    for e in ontology.get("entities", [])
                ],
                "relations": [
                    {
                        "name": r["name"],
                        "label": r.get("label", ""),
                        "source": r["source_entity"],
                        "target": r["target_entity"],
                    }
                    for r in ontology.get("relations", [])
                ],
                "query_patterns": ontology.get("query_patterns", []),
            }

            # Step 1: Combined intent recognition + Cypher generation
            logger.info("QA Step 1: Combined intent + Cypher for: %s", question[:100])
            neo4j_schema = await graph_manager.get_neo4j_schema()
            combined_messages = build_combined_intent_cypher_messages(
                question, ontology_summary, neo4j_schema
            )
            combined_result = await llm_client.chat_completion_json(combined_messages)

            result["intent"] = combined_result.get("intent", "unknown")
            cypher = combined_result.get("cypher", "")
            params = combined_result.get("params", {})

            # Security validation
            write_ops = re.compile(
                r"\b(CREATE|DELETE|DETACH|SET|REMOVE|DROP)\b", re.IGNORECASE
            )
            if write_ops.search(cypher):
                raise ValueError("Generated Cypher contains write operations")

            result["generated_cypher"] = cypher

            # Step 2: Execute Cypher and synthesize answer
            logger.info("QA Step 2: Execute and synthesize")
            try:
                graph_result = await graph_manager.execute_cypher(cypher, params)
                # Convert Neo4j types to JSON-serializable
                clean_result = json.loads(json.dumps(graph_result, default=str))
                result["raw_result"] = clean_result
            except Exception as e:
                logger.warning("Cypher execution failed: %s, attempting repair", e)
                # Retry with error context
                repair_result = await QAEngine._retry_cypher(
                    question, cypher, str(e), neo4j_schema
                )
                if repair_result is not None:
                    result["generated_cypher"] = repair_result["cypher"]
                    graph_result = await graph_manager.execute_cypher(
                        repair_result["cypher"], repair_result.get("params", {})
                    )
                    clean_result = json.loads(json.dumps(graph_result, default=str))
                    result["raw_result"] = clean_result
                else:
                    result["raw_result"] = []
                    result["answer"] = f"Query execution failed: {e}"
                    result["latency_ms"] = int((time.time() - start_time) * 1000)
                    return result

            # Synthesize natural language answer
            answer_messages = build_answer_synthesis_messages(
                question, result["generated_cypher"], result["raw_result"]
            )
            answer = await llm_client.chat_completion(answer_messages, max_tokens=8192)
            result["answer"] = answer
            result["confidence"] = 0.85 if result["raw_result"] else 0.3

        except Exception as e:
            logger.error("QA pipeline failed: %s", str(e))
            result["answer"] = f"Processing failed: {str(e)}"
            result["confidence"] = 0.0

        result["latency_ms"] = int((time.time() - start_time) * 1000)
        return result

    @staticmethod
    async def _retry_cypher(
        question: str,
        failed_cypher: str,
        error_msg: str,
        neo4j_schema: Dict,
    ) -> Optional[Dict]:
        """Attempt to repair a failed Cypher query."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a Neo4j Cypher expert. The previous Cypher query failed. "
                    "Please fix it based on the error message. "
                    "Output strictly valid JSON with keys: cypher, params, explanation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original question: {question}\n\n"
                    f"Failed Cypher: {failed_cypher}\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Neo4j schema: {json.dumps(neo4j_schema, ensure_ascii=False)}\n\n"
                    "Please provide a corrected Cypher query."
                ),
            },
        ]
        try:
            return await llm_client.chat_completion_json(messages)
        except Exception:
            return None
