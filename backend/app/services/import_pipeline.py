"""Import pipeline - orchestrates end-to-end data import flow."""

import json
import logging
from typing import Dict, List
import pandas as pd

from app.services.data_parser import DataParser
from app.services.ontology_builder import OntologyBuilder
from app.services.graph_manager import graph_manager

logger = logging.getLogger(__name__)


class ImportPipeline:
    """Orchestrate end-to-end data import: parse → build ontology → load graph."""

    @staticmethod
    async def load_data_to_graph(
        ontology: Dict,
        datasources: List[Dict],
        project_id: str = None,
    ) -> Dict:
        """
        Load data into Neo4j based on ontology definition.

        Args:
            ontology: The ontology definition dict
            datasources: List of datasource dicts with file_path and source_type

        Returns:
            Dict with total_nodes and total_relations counts
        """
        total_nodes = 0
        total_relations = 0

        # Build a map of table_name -> DataFrame
        table_dfs: Dict[str, pd.DataFrame] = {}
        for ds in datasources:
            try:
                df = DataParser.read_full_dataframe(ds["file_path"], ds["source_type"])
                table_dfs[ds["name"]] = df
                logger.info("Loaded DataFrame for %s: %d rows", ds["name"], len(df))
            except Exception as e:
                logger.error("Failed to read datasource %s: %s", ds["name"], e)

        # Create schema (constraints/indexes)
        await graph_manager.create_schema(ontology, project_id=project_id)

        # Load entities
        for entity in ontology.get("entities", []):
            try:
                source_tables = entity.get("source_tables", [])
                properties = entity.get("properties", [])

                # Merge data from source tables
                merged_rows = []
                for table_name in source_tables:
                    if table_name not in table_dfs:
                        logger.warning("Table %s not found in datasources", table_name)
                        continue
                    df = table_dfs[table_name]

                    for _, row in df.iterrows():
                        data_row = {}
                        for prop in properties:
                            if prop.get("source_table") == table_name:
                                col_name = prop.get("source_column", prop["name"])
                                if col_name in df.columns:
                                    val = row.get(col_name)
                                    if pd.isna(val):
                                        val = None
                                    elif isinstance(val, pd.Timestamp):
                                        val = val.isoformat()
                                    data_row[prop["name"]] = val
                        if data_row:
                            merged_rows.append(data_row)

                if merged_rows:
                    count = await graph_manager.load_entity_data(entity, merged_rows, project_id=project_id)
                    total_nodes += count
                    logger.info("Loaded %d nodes for entity %s", count, entity["name"])
                else:
                    logger.warning("No data rows found for entity %s", entity["name"])
            except Exception as e:
                logger.error("Failed to load entity %s: %s", entity["name"], e)

        # Load relationships
        for relation in ontology.get("relations", []):
            try:
                # Validate relation keys exist in entity properties
                src_entity_name = relation.get("source_entity", "")
                tgt_entity_name = relation.get("target_entity", "")
                src_key = relation.get("source_key", "")
                tgt_key = relation.get("target_key", "")

                src_entity = next((e for e in ontology.get("entities", []) if e["name"] == src_entity_name), None)
                tgt_entity = next((e for e in ontology.get("entities", []) if e["name"] == tgt_entity_name), None)

                if src_entity:
                    src_prop_names = [p["name"] for p in src_entity.get("properties", [])]
                    if src_key not in src_prop_names:
                        logger.warning("Relation %s: source_key '%s' not in %s properties %s",
                                       relation["name"], src_key, src_entity_name, src_prop_names)
                if tgt_entity:
                    tgt_prop_names = [p["name"] for p in tgt_entity.get("properties", [])]
                    if tgt_key not in tgt_prop_names:
                        logger.warning("Relation %s: target_key '%s' not in %s properties %s",
                                       relation["name"], tgt_key, tgt_entity_name, tgt_prop_names)

                count = await graph_manager.load_relation_data(relation, project_id=project_id)
                total_relations += count
                logger.info("Loaded %d relations for %s", count, relation["name"])
            except Exception as e:
                logger.error("Failed to load relation %s: %s", relation["name"], e)

        return {"total_nodes": total_nodes, "total_relations": total_relations}
