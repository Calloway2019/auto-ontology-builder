"""Ontology builder - 4-stage LLM pipeline for automatic ontology construction."""

import json
import logging
from typing import List, Dict, Optional, Callable, Awaitable

from app.llm.client import llm_client
from app.llm.prompts.schema_analysis import build_schema_analysis_messages
from app.llm.prompts.entity_extraction import build_entity_extraction_messages
from app.llm.prompts.relation_discovery import build_relation_discovery_messages
from app.llm.prompts.ontology_refinement import build_ontology_refinement_messages

logger = logging.getLogger(__name__)

# Ontology building requires large JSON outputs - use higher token limit
ONTOLOGY_MAX_TOKENS = 16384

# Progress callback type: (stage, progress, message, stage_summary, stage_detail)
ProgressCallback = Optional[Callable[[str, float, str, str, Dict], Awaitable[None]]]


class OntologyBuilder:
    """Build ontology from table metadata using 4-stage LLM pipeline."""

    @staticmethod
    async def build(
        tables_meta: List[Dict],
        domain_hint: str = "",
        on_progress: ProgressCallback = None,
    ) -> Dict:
        reasoning_log = []

        # Stage 1: Schema analysis
        if on_progress:
            await on_progress("stage1", 0.0, "正在分析数据表结构...", "", {})
        logger.info("Ontology build - Stage 1: Schema analysis")

        messages = build_schema_analysis_messages(tables_meta)
        stage1_result = await llm_client.chat_completion_json(messages, temperature=0.1, max_tokens=ONTOLOGY_MAX_TOKENS)
        reasoning_log.append({"stage": "schema_analysis", "result": stage1_result})

        tables_analyzed = len(stage1_result.get("tables", []))
        stage1_summary = f"分析了 {tables_analyzed} 张数据表"
        stage1_detail = {
            "tables": [
                {
                    "name": t.get("table_name", ""),
                    "business_object": t.get("business_object", ""),
                    "column_count": len(t.get("columns", [])),
                }
                for t in stage1_result.get("tables", [])
            ]
        }
        if on_progress:
            await on_progress("stage1", 1.0, "模式分析完成", stage1_summary, stage1_detail)

        # Stage 2: Entity extraction
        if on_progress:
            await on_progress("stage2", 0.0, "正在抽取实体...", "", {})
        logger.info("Ontology build - Stage 2: Entity extraction")

        messages = build_entity_extraction_messages(stage1_result, tables_meta)
        stage2_result = await llm_client.chat_completion_json(messages, temperature=0.1, max_tokens=ONTOLOGY_MAX_TOKENS)
        reasoning_log.append({"stage": "entity_extraction", "result": stage2_result})

        entities = stage2_result.get("entities", [])
        total_props = sum(len(e.get("properties", [])) for e in entities)
        stage2_summary = f"抽取了 {len(entities)} 个实体，共 {total_props} 个属性"
        stage2_detail = {
            "entities": [
                {
                    "name": e.get("name", ""),
                    "label": e.get("label", ""),
                    "primary_key": e.get("primary_key", ""),
                    "prop_count": len(e.get("properties", [])),
                }
                for e in entities
            ]
        }
        if on_progress:
            await on_progress("stage2", 1.0, "实体抽取完成", stage2_summary, stage2_detail)

        # Stage 3: Relation discovery
        if on_progress:
            await on_progress("stage3", 0.0, "正在发现关系...", "", {})
        logger.info("Ontology build - Stage 3: Relation discovery")

        messages = build_relation_discovery_messages(stage1_result, stage2_result)
        stage3_result = await llm_client.chat_completion_json(messages, temperature=0.1, max_tokens=ONTOLOGY_MAX_TOKENS)
        reasoning_log.append({"stage": "relation_discovery", "result": stage3_result})

        relations = stage3_result.get("relations", [])
        stage3_summary = f"发现了 {len(relations)} 个关系"
        stage3_detail = {
            "relations": [
                {
                    "name": r.get("name", ""),
                    "label": r.get("label", ""),
                    "source": r.get("source_entity", ""),
                    "target": r.get("target_entity", ""),
                }
                for r in relations
            ]
        }
        if on_progress:
            await on_progress("stage3", 1.0, "关系发现完成", stage3_summary, stage3_detail)

        # Stage 4: Ontology refinement
        if on_progress:
            await on_progress("stage4", 0.0, "正在优化本体...", "", {})
        logger.info("Ontology build - Stage 4: Ontology refinement")

        messages = build_ontology_refinement_messages(
            stage2_result, stage3_result, domain_hint
        )
        ontology = await llm_client.chat_completion_json(messages, temperature=0.1, max_tokens=ONTOLOGY_MAX_TOKENS)
        reasoning_log.append({"stage": "ontology_refinement", "result": "see final output"})

        final_entities = len(ontology.get("entities", []))
        final_relations = len(ontology.get("relations", []))
        stage4_summary = f"优化完成，最终 {final_entities} 个实体 {final_relations} 个关系"
        stage4_detail = {
            "domain": ontology.get("domain", ""),
            "description": ontology.get("description", ""),
            "entity_count": final_entities,
            "relation_count": final_relations,
        }
        if on_progress:
            await on_progress("completed", 1.0, "本体构建完成", stage4_summary, stage4_detail)

        logger.info(
            "Ontology build complete: %d entities, %d relations",
            final_entities,
            final_relations,
        )

        return {
            "ontology": ontology,
            "reasoning_log": reasoning_log,
        }
