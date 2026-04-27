"""Graph manager - dynamic Neo4j operations based on ontology definition."""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase
from app.config import settings

logger = logging.getLogger(__name__)


class GraphManager:
    """Manage Neo4j knowledge graph with dynamic Cypher based on ontology."""

    def __init__(self):
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return self._driver

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def verify_connection(self) -> dict:
        """Test Neo4j connectivity."""
        try:
            async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                result = await session.run("RETURN 1 AS n")
                record = await result.single()
                return {"status": "connected", "result": record["n"]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def create_schema(self, ontology: Dict):
        """Create constraints and indexes based on ontology definition."""
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for entity in ontology.get("entities", []):
                label = entity["name"]
                pk = entity.get("primary_key", "")
                if pk:
                    # Create uniqueness constraint
                    cypher = (
                        f"CREATE CONSTRAINT IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.{pk} IS UNIQUE"
                    )
                    try:
                        await session.run(cypher)
                        logger.info("Created constraint for %s.%s", label, pk)
                    except Exception as e:
                        logger.warning("Constraint creation failed for %s: %s", label, e)

    async def clear_graph(self):
        """Clear all nodes and relationships in the database."""
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            await session.run("MATCH (n) DETACH DELETE n")
            logger.info("Graph cleared")

    async def load_entity_data(
        self,
        entity_def: Dict,
        data_rows: List[Dict],
        batch_size: int = 500,
    ) -> int:
        """Load entity nodes from data rows based on entity definition."""
        label = entity_def["name"]
        pk = entity_def.get("primary_key", "")
        properties = entity_def.get("properties", [])
        prop_names = [p["name"] for p in properties]

        # Filter out rows where primary key is null (Neo4j MERGE cannot handle null keys)
        if pk:
            original_count = len(data_rows)
            data_rows = [r for r in data_rows if r.get(pk) is not None
                         and not (isinstance(r.get(pk), float) and r.get(pk) != r.get(pk))]
            filtered = original_count - len(data_rows)
            if filtered > 0:
                logger.warning("Filtered %d rows with null primary key '%s' for entity %s",
                               filtered, pk, label)

        if not data_rows:
            logger.warning("No valid rows to load for entity %s", label)
            return 0

        total_loaded = 0
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for i in range(0, len(data_rows), batch_size):
                batch = data_rows[i:i + batch_size]
                # Build dynamic SET clause
                set_parts = []
                for prop in prop_names:
                    set_parts.append(f"n.{prop} = row.{prop}")
                set_clause = ", ".join(set_parts)

                if pk:
                    cypher = (
                        f"UNWIND $rows AS row "
                        f"MERGE (n:{label} {{{pk}: row.{pk}}}) "
                        f"SET {set_clause}"
                    )
                else:
                    cypher = (
                        f"UNWIND $rows AS row "
                        f"CREATE (n:{label}) "
                        f"SET {set_clause}"
                    )

                # Clean data: convert NaN/None to null
                clean_batch = []
                for row in batch:
                    clean_row = {}
                    for key, val in row.items():
                        if key in prop_names:
                            if val is None or (isinstance(val, float) and val != val):
                                clean_row[key] = None
                            else:
                                clean_row[key] = val
                    clean_batch.append(clean_row)

                await session.run(cypher, rows=clean_batch)
                total_loaded += len(clean_batch)
                logger.info("Loaded %d/%d nodes for %s", total_loaded, len(data_rows), label)

        return total_loaded

    async def load_relation_data(
        self,
        relation_def: Dict,
        batch_size: int = 500,
    ) -> int:
        """Load relationships based on relation definition (data already in nodes)."""
        rel_type = relation_def["name"]
        source_label = relation_def["source_entity"]
        target_label = relation_def["target_entity"]
        source_key = relation_def["source_key"]
        target_key = relation_def["target_key"]

        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Pre-check: verify both sides have matching key values
            check_src = f"MATCH (a:{source_label}) WHERE a.{source_key} IS NOT NULL RETURN count(a) AS cnt"
            check_tgt = f"MATCH (b:{target_label}) WHERE b.{target_key} IS NOT NULL RETURN count(b) AS cnt"
            src_result = await session.run(check_src)
            src_record = await src_result.single()
            src_count = src_record["cnt"] if src_record else 0
            tgt_result = await session.run(check_tgt)
            tgt_record = await tgt_result.single()
            tgt_count = tgt_record["cnt"] if tgt_record else 0

            if src_count == 0:
                logger.warning("No %s nodes have non-null %s — skipping relation %s", source_label, source_key, rel_type)
                return 0
            if tgt_count == 0:
                logger.warning("No %s nodes have non-null %s — skipping relation %s", target_label, target_key, rel_type)
                return 0

            logger.info("Relation %s pre-check: %s.%s has %d values, %s.%s has %d values",
                        rel_type, source_label, source_key, src_count, target_label, target_key, tgt_count)

            # Use toString() to handle type mismatches (e.g., int vs string)
            cypher = (
                f"MATCH (a:{source_label}), (b:{target_label}) "
                f"WHERE toString(a.{source_key}) = toString(b.{target_key}) "
                f"AND a.{source_key} IS NOT NULL "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"RETURN count(r) AS cnt"
            )
            logger.info("Executing relation Cypher: %s", cypher)
            result = await session.run(cypher)
            record = await result.single()
            count = record["cnt"] if record else 0

            if count == 0:
                # Diagnose: sample values from both sides
                diag_src = await session.run(
                    f"MATCH (a:{source_label}) WHERE a.{source_key} IS NOT NULL "
                    f"RETURN DISTINCT toString(a.{source_key}) AS v LIMIT 3"
                )
                src_vals = [rec["v"] async for rec in diag_src]
                diag_tgt = await session.run(
                    f"MATCH (b:{target_label}) WHERE b.{target_key} IS NOT NULL "
                    f"RETURN DISTINCT toString(b.{target_key}) AS v LIMIT 3"
                )
                tgt_vals = [rec["v"] async for rec in diag_tgt]
                logger.warning(
                    "Relation %s created 0 relationships. Value mismatch? "
                    "%s.%s samples=%s, %s.%s samples=%s",
                    rel_type, source_label, source_key, src_vals,
                    target_label, target_key, tgt_vals
                )
            else:
                logger.info("Created %d relationships of type %s", count, rel_type)
            return count

    async def execute_cypher(self, cypher: str, params: Dict = None) -> List[Dict]:
        """Execute a read-only Cypher query and return results."""
        # Security check: only allow read operations
        write_ops = re.compile(
            r"\b(CREATE|DELETE|DETACH|SET|REMOVE|DROP|MERGE)\b", re.IGNORECASE
        )
        if write_ops.search(cypher):
            raise ValueError("Write operations are not allowed in query mode")

        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(cypher, params or {})
            records = []
            async for record in result:
                records.append(dict(record))
            return records

    async def get_graph_stats(self, label_map: Dict[str, str] = None) -> Dict:
        """Get graph statistics."""
        stats = {"total_nodes": 0, "total_edges": 0, "node_types": {}, "edge_types": {}}
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Node count by label
            result = await session.run(
                "MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt"
            )
            async for record in result:
                label_list = record["labels"]
                label = label_list[0] if label_list else "Unknown"
                cnt = record["cnt"]
                display = label_map.get(label, label) if label_map else label
                stats["node_types"][label] = {"count": cnt, "label": display}
                stats["total_nodes"] += cnt

            # Relationship count by type
            result = await session.run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt"
            )
            async for record in result:
                rel_type = record["type"]
                cnt = record["cnt"]
                display = label_map.get(rel_type, rel_type) if label_map else rel_type
                stats["edge_types"][rel_type] = {"count": cnt, "label": display}
                stats["total_edges"] += cnt

        return stats

    async def get_graph_visualization(
        self,
        limit: int = 500,
        node_types: List[str] = None,
        rel_types: List[str] = None,
        label_map: Dict[str, str] = None,
    ) -> Dict:
        """Get graph data for visualization."""
        nodes = []
        edges = []
        node_ids = set()
        _lm = label_map or {}

        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Fetch nodes with relationships
            cypher = "MATCH (a)-[r]->(b) RETURN a, r, b LIMIT $limit"
            result = await session.run(cypher, limit=limit)

            async for record in result:
                a = record["a"]
                b = record["b"]
                r = record["r"]

                a_label = list(a.labels)[0] if a.labels else "Unknown"
                b_label = list(b.labels)[0] if b.labels else "Unknown"

                # Filter by type if specified
                if node_types and a_label not in node_types and b_label not in node_types:
                    continue
                if rel_types and r.type not in rel_types:
                    continue

                a_id = str(a.element_id)
                b_id = str(b.element_id)

                if a_id not in node_ids:
                    node_ids.add(a_id)
                    props = dict(a)
                    display_label = (
                        props.get("name", "") or props.get("Name", "")
                        or props.get("title", "") or props.get("Title", "")
                        or str(list(props.values())[0]) if props else a_label
                    )
                    nodes.append({
                        "id": a_id,
                        "label": str(display_label)[:50],
                        "type": a_label,
                        "type_label": _lm.get(a_label, a_label),
                        "properties": {k: str(v) if v is not None else None for k, v in props.items()},
                    })

                if b_id not in node_ids:
                    node_ids.add(b_id)
                    props = dict(b)
                    display_label = (
                        props.get("name", "") or props.get("Name", "")
                        or props.get("title", "") or props.get("Title", "")
                        or str(list(props.values())[0]) if props else b_label
                    )
                    nodes.append({
                        "id": b_id,
                        "label": str(display_label)[:50],
                        "type": b_label,
                        "type_label": _lm.get(b_label, b_label),
                        "properties": {k: str(v) if v is not None else None for k, v in props.items()},
                    })

                edges.append({
                    "id": str(r.element_id),
                    "source": a_id,
                    "target": b_id,
                    "type": r.type,
                    "type_label": _lm.get(r.type, r.type),
                    "label": _lm.get(r.type, r.type),
                    "properties": dict(r),
                })

        return {"nodes": nodes, "edges": edges}

    async def get_neo4j_schema(self) -> Dict:
        """Get Neo4j schema info for Cypher generation."""
        schema = {"node_labels": {}, "relationship_types": []}
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Get node labels and their properties
            result = await session.run(
                "CALL db.schema.nodeTypeProperties() "
                "YIELD nodeLabels, propertyName, propertyTypes"
            )
            async for record in result:
                labels = record["nodeLabels"]
                label = labels[0] if labels else "Unknown"
                prop = record["propertyName"]
                prop_types = record["propertyTypes"]
                if label not in schema["node_labels"]:
                    schema["node_labels"][label] = []
                schema["node_labels"][label].append({
                    "name": prop,
                    "types": prop_types,
                })

            # Get relationship types
            result = await session.run(
                "CALL db.schema.relTypeProperties() "
                "YIELD relType"
            )
            rel_types_set = set()
            async for record in result:
                rel_type = record["relType"]
                # Clean format: :`TYPE_NAME`
                rel_type = rel_type.strip(":`")
                rel_types_set.add(rel_type)
            schema["relationship_types"] = list(rel_types_set)

        return schema


# Global singleton
graph_manager = GraphManager()
