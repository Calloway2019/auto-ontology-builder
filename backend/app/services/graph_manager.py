"""Graph manager - dynamic Neo4j operations based on ontology definition."""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase
from app.config import settings

logger = logging.getLogger(__name__)


class GraphManager:
    """Manage Neo4j knowledge graph with dynamic Cypher based on ontology.

    All node data is tagged with ``_project_id`` so that multiple projects
    can coexist in the same Neo4j Community database without interfering
    with each other.
    """

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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def create_schema(self, ontology: Dict, project_id: str = None):
        """Create indexes based on ontology definition.

        Old single-property UNIQUE constraints are dropped because we now
        use ``(pk, _project_id)`` as the logical composite key per node.
        """
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Drop old single-property UNIQUE constraints that conflict
            try:
                result = await session.run(
                    "SHOW CONSTRAINTS YIELD name, type, properties "
                    "WHERE type = 'UNIQUENESS' AND size(properties) = 1 "
                    "RETURN name"
                )
                names = [rec["name"] async for rec in result]
                for name in names:
                    await session.run(f"DROP CONSTRAINT {name} IF EXISTS")
                    logger.info("Dropped old single-property constraint: %s", name)
            except Exception as e:
                logger.warning("Failed to clean old constraints: %s", e)

            for entity in ontology.get("entities", []):
                label = entity["name"]
                pk = entity.get("primary_key", "")

                # Index on primary key for fast MERGE / lookup
                if pk:
                    try:
                        await session.run(
                            f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.{pk})"
                        )
                    except Exception as e:
                        logger.warning("Index on %s.%s failed: %s", label, pk, e)

                # Index on _project_id for per-project filtering
                try:
                    await session.run(
                        f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n._project_id)"
                    )
                except Exception as e:
                    logger.warning("Index on %s._project_id failed: %s", label, e)

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    async def clear_graph(self, project_id: str = None):
        """Clear graph data for a specific project, or all data if no project_id."""
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            if project_id:
                # Only delete nodes belonging to this project
                while True:
                    result = await session.run(
                        "MATCH (n {_project_id: $pid}) "
                        "WITH n LIMIT 10000 "
                        "DETACH DELETE n "
                        "RETURN count(*) AS deleted",
                        pid=project_id,
                    )
                    record = await result.single()
                    deleted = record["deleted"] if record else 0
                    if deleted == 0:
                        break
                    logger.info("Deleted %d nodes for project %s", deleted, project_id)
                logger.info("Graph cleared for project %s", project_id)
            else:
                # Full clear (legacy fallback)
                try:
                    result = await session.run("SHOW CONSTRAINTS YIELD name RETURN name")
                    names = [rec["name"] async for rec in result]
                    for name in names:
                        await session.run(f"DROP CONSTRAINT {name} IF EXISTS")
                except Exception as e:
                    logger.warning("Failed to drop constraints: %s", e)

                try:
                    result = await session.run(
                        "SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP' RETURN name"
                    )
                    names = [rec["name"] async for rec in result]
                    for name in names:
                        await session.run(f"DROP INDEX {name} IF EXISTS")
                except Exception as e:
                    logger.warning("Failed to drop indexes: %s", e)

                while True:
                    result = await session.run(
                        "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) AS deleted"
                    )
                    record = await result.single()
                    deleted = record["deleted"] if record else 0
                    if deleted == 0:
                        break
                    logger.info("Deleted %d nodes in batch", deleted)
                logger.info("Graph fully cleared")

    # ------------------------------------------------------------------
    # Entity loading
    # ------------------------------------------------------------------

    async def load_entity_data(
        self,
        entity_def: Dict,
        data_rows: List[Dict],
        project_id: str = None,
        batch_size: int = 500,
    ) -> int:
        """Load entity nodes. Each node is tagged with ``_project_id``."""
        label = entity_def["name"]
        pk = entity_def.get("primary_key", "")
        properties = entity_def.get("properties", [])
        prop_names = [p["name"] for p in properties]

        # Filter rows with null primary key
        if pk:
            original_count = len(data_rows)
            data_rows = [
                r for r in data_rows
                if r.get(pk) is not None
                and not (isinstance(r.get(pk), float) and r.get(pk) != r.get(pk))
            ]
            filtered = original_count - len(data_rows)
            if filtered > 0:
                logger.warning(
                    "Filtered %d rows with null pk '%s' for entity %s",
                    filtered, pk, label,
                )

        if not data_rows:
            logger.warning("No valid rows to load for entity %s", label)
            return 0

        total_loaded = 0
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for i in range(0, len(data_rows), batch_size):
                batch = data_rows[i : i + batch_size]

                # Build SET clause
                set_parts = [f"n.{prop} = row.{prop}" for prop in prop_names]
                if project_id:
                    set_parts.append("n._project_id = row._project_id")
                set_clause = ", ".join(set_parts)

                if pk and project_id:
                    # MERGE on (pk + _project_id) so different projects are isolated
                    cypher = (
                        f"UNWIND $rows AS row "
                        f"MERGE (n:{label} {{{pk}: row.{pk}, _project_id: row._project_id}}) "
                        f"SET {set_clause}"
                    )
                elif pk:
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

                # Clean data
                clean_batch = []
                for row in batch:
                    clean_row = {}
                    for key, val in row.items():
                        if key in prop_names:
                            if val is None or (isinstance(val, float) and val != val):
                                clean_row[key] = None
                            else:
                                clean_row[key] = val
                    if project_id:
                        clean_row["_project_id"] = project_id
                    clean_batch.append(clean_row)

                await session.run(cypher, rows=clean_batch)
                total_loaded += len(clean_batch)
                logger.info("Loaded %d/%d nodes for %s", total_loaded, len(data_rows), label)

        return total_loaded

    # ------------------------------------------------------------------
    # Relation loading  (performance-optimised)
    # ------------------------------------------------------------------

    async def load_relation_data(
        self,
        relation_def: Dict,
        project_id: str = None,
        batch_size: int = 500,
    ) -> int:
        """Load relationships using direct property matching with indexes.

        Key performance improvements over previous implementation:
        1. Creates indexes on join keys before matching.
        2. Uses direct property-map matching ``{key: k}`` instead of
           ``toString()`` comparisons, enabling index utilisation.
        3. Filters by ``_project_id`` so only in-project matches are
           considered.
        """
        rel_type = relation_def["name"]
        source_label = relation_def["source_entity"]
        target_label = relation_def["target_entity"]
        source_key = relation_def["source_key"]
        target_key = relation_def["target_key"]

        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # ---- 1. Create indexes on join keys ----
            for lbl, key in [(source_label, source_key), (target_label, target_key)]:
                try:
                    await session.run(
                        f"CREATE INDEX IF NOT EXISTS FOR (n:{lbl}) ON (n.{key})"
                    )
                except Exception as e:
                    logger.warning("Index creation for %s.%s failed: %s", lbl, key, e)

            # Wait for indexes to come online
            try:
                await session.run("CALL db.awaitIndexes(300)")
            except Exception as e:
                logger.warning("Await indexes: %s", e)

            # ---- 2. Pre-check node counts ----
            pid_where = " AND a._project_id = $pid" if project_id else ""
            pid_params = {"pid": project_id} if project_id else {}

            src_result = await session.run(
                f"MATCH (a:{source_label}) "
                f"WHERE a.{source_key} IS NOT NULL{pid_where} "
                f"RETURN count(a) AS cnt",
                **pid_params,
            )
            src_count = (await src_result.single())["cnt"]

            tgt_where = pid_where.replace("a.", "b.")
            tgt_result = await session.run(
                f"MATCH (b:{target_label}) "
                f"WHERE b.{target_key} IS NOT NULL{tgt_where} "
                f"RETURN count(b) AS cnt",
                **pid_params,
            )
            tgt_count = (await tgt_result.single())["cnt"]

            if src_count == 0:
                logger.warning("No %s nodes with non-null %s — skip %s",
                               source_label, source_key, rel_type)
                return 0
            if tgt_count == 0:
                logger.warning("No %s nodes with non-null %s — skip %s",
                               target_label, target_key, rel_type)
                return 0

            logger.info(
                "Relation %s: %s.%s=%d nodes, %s.%s=%d nodes",
                rel_type, source_label, source_key, src_count,
                target_label, target_key, tgt_count,
            )

            # ---- 3. Get distinct source keys ----
            keys_cypher = (
                f"MATCH (a:{source_label}) "
                f"WHERE a.{source_key} IS NOT NULL{pid_where} "
                f"RETURN DISTINCT a.{source_key} AS key"
            )
            keys_result = await session.run(keys_cypher, **pid_params)
            all_keys = [rec["key"] async for rec in keys_result]

            # ---- 4. Batch create relationships (direct matching, NO toString) ----
            total_count = 0
            total_batches = (len(all_keys) + batch_size - 1) // batch_size

            for i in range(0, len(all_keys), batch_size):
                batch_keys = all_keys[i : i + batch_size]

                if project_id:
                    cypher = (
                        f"UNWIND $keys AS k "
                        f"MATCH (a:{source_label} {{{source_key}: k, _project_id: $pid}}) "
                        f"MATCH (b:{target_label} {{{target_key}: k, _project_id: $pid}}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) "
                        f"RETURN count(r) AS cnt"
                    )
                    result = await session.run(cypher, keys=batch_keys, pid=project_id)
                else:
                    cypher = (
                        f"UNWIND $keys AS k "
                        f"MATCH (a:{source_label} {{{source_key}: k}}) "
                        f"MATCH (b:{target_label} {{{target_key}: k}}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) "
                        f"RETURN count(r) AS cnt"
                    )
                    result = await session.run(cypher, keys=batch_keys)

                record = await result.single()
                batch_count = record["cnt"] if record else 0
                total_count += batch_count
                logger.info(
                    "Relation %s batch %d/%d: %d rels (total %d)",
                    rel_type, i // batch_size + 1, total_batches,
                    batch_count, total_count,
                )

            if total_count == 0:
                # Diagnostic
                diag_src = await session.run(
                    f"MATCH (a:{source_label}) WHERE a.{source_key} IS NOT NULL{pid_where} "
                    f"RETURN DISTINCT a.{source_key} AS v LIMIT 3",
                    **pid_params,
                )
                src_vals = [rec["v"] async for rec in diag_src]
                diag_tgt = await session.run(
                    f"MATCH (b:{target_label}) WHERE b.{target_key} IS NOT NULL{tgt_where} "
                    f"RETURN DISTINCT b.{target_key} AS v LIMIT 3",
                    **pid_params,
                )
                tgt_vals = [rec["v"] async for rec in diag_tgt]
                logger.warning(
                    "Relation %s: 0 rels. Samples: %s.%s=%s (type=%s), %s.%s=%s (type=%s)",
                    rel_type,
                    source_label, source_key, src_vals,
                    type(src_vals[0]).__name__ if src_vals else "?",
                    target_label, target_key, tgt_vals,
                    type(tgt_vals[0]).__name__ if tgt_vals else "?",
                )
            else:
                logger.info("Created %d relationships of type %s", total_count, rel_type)

            return total_count

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def execute_cypher(self, cypher: str, params: Dict = None) -> List[Dict]:
        """Execute a read-only Cypher query and return results."""
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

    async def get_graph_stats(
        self, label_map: Dict[str, str] = None, project_id: str = None
    ) -> Dict:
        """Get graph statistics, optionally scoped to a project."""
        stats = {"total_nodes": 0, "total_edges": 0, "node_types": {}, "edge_types": {}}
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Nodes
            if project_id:
                result = await session.run(
                    "MATCH (n {_project_id: $pid}) "
                    "RETURN labels(n) AS labels, count(n) AS cnt",
                    pid=project_id,
                )
            else:
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

            # Edges
            if project_id:
                result = await session.run(
                    "MATCH (a {_project_id: $pid})-[r]->(b) "
                    "RETURN type(r) AS type, count(r) AS cnt",
                    pid=project_id,
                )
            else:
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
        limit: int = 100,
        node_types: List[str] = None,
        rel_types: List[str] = None,
        label_map: Dict[str, str] = None,
        project_id: str = None,
    ) -> Dict:
        """Get graph data for visualization, scoped to a project."""
        nodes = []
        edges = []
        node_ids = set()
        _lm = label_map or {}

        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            if project_id:
                cypher = (
                    "MATCH (a {_project_id: $pid})-[r]->(b) "
                    "RETURN a, r, b LIMIT $limit"
                )
                result = await session.run(cypher, pid=project_id, limit=limit)
            else:
                cypher = "MATCH (a)-[r]->(b) RETURN a, r, b LIMIT $limit"
                result = await session.run(cypher, limit=limit)

            async for record in result:
                a = record["a"]
                b = record["b"]
                r = record["r"]

                a_label = list(a.labels)[0] if a.labels else "Unknown"
                b_label = list(b.labels)[0] if b.labels else "Unknown"

                if node_types and a_label not in node_types and b_label not in node_types:
                    continue
                if rel_types and r.type not in rel_types:
                    continue

                a_id = str(a.element_id)
                b_id = str(b.element_id)

                if a_id not in node_ids:
                    node_ids.add(a_id)
                    props = {k: v for k, v in dict(a).items() if k != "_project_id"}
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
                        "properties": {
                            k: str(v) if v is not None else None
                            for k, v in props.items()
                        },
                    })

                if b_id not in node_ids:
                    node_ids.add(b_id)
                    props = {k: v for k, v in dict(b).items() if k != "_project_id"}
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
                        "properties": {
                            k: str(v) if v is not None else None
                            for k, v in props.items()
                        },
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
            result = await session.run(
                "CALL db.schema.nodeTypeProperties() "
                "YIELD nodeLabels, propertyName, propertyTypes"
            )
            async for record in result:
                labels = record["nodeLabels"]
                label = labels[0] if labels else "Unknown"
                prop = record["propertyName"]
                prop_types = record["propertyTypes"]
                # Hide internal _project_id from QA schema
                if prop == "_project_id":
                    continue
                if label not in schema["node_labels"]:
                    schema["node_labels"][label] = []
                schema["node_labels"][label].append({
                    "name": prop,
                    "types": prop_types,
                })

            result = await session.run(
                "CALL db.schema.relTypeProperties() YIELD relType"
            )
            rel_types_set = set()
            async for record in result:
                rel_type = record["relType"]
                rel_type = rel_type.strip(":`")
                rel_types_set.add(rel_type)
            schema["relationship_types"] = list(rel_types_set)

        return schema


# Global singleton
graph_manager = GraphManager()
