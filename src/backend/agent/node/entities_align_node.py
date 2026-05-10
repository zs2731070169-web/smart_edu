import asyncio
import logging
from typing import List, Tuple

from langgraph.runtime import Runtime
from neo4j import Query

from backend.agent.context import EnvContext
from backend.agent.schema.schema import Entity
from backend.agent.state import OverallState
from backend.config.constants import THRESHOLD
from backend.core.client.llm_client import embedding_model
from backend.core.client.neo4j_client import driver
from backend.utils.thread_utils import thread_pool_executor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("entities_align")


async def entities_align(state: OverallState, runtime: Runtime[EnvContext]) -> dict:
    """通过混合检索进行实体对齐,返回对齐后的 (entity, label) 列表"""
    tid = runtime.context.get("thread_id", "-")
    entity_pairs: List[Entity] = state.get("entity_pairs") or []
    logger.info(f"[entities_align_node][{tid}] 入参 entity_pairs={entity_pairs}")

    if not entity_pairs:
        logger.info(f"[entities_align_node][{tid}] 实体列表为空,跳过对齐")
        return {"aligned_entities": []}

    pairs = [(p.entity, p.label) for p in entity_pairs]
    entities, labels = zip(*pairs)

    search_targets = [
        (entity, label)
        for entity, label in zip(entities, labels)
        if label not in ["Teacher", "Student", "Price"]
    ]
    logger.info(f"[entities_align_node][{tid}] 过滤后待检索实体: {search_targets}")

    if not search_targets:
        return {"aligned_entities": []}

    # 异步并发执行混合检索
    hybrid_search_results = await asyncio.gather(*[
        asyncio.wrap_future(
            thread_pool_executor.submit(
                _search_entity, entity=entity, label=label, top_k=1, threshold=THRESHOLD
            )
        ) for entity, label in search_targets
    ])

    aligned_entities: List[Tuple[str, str]] = [
        (result[0]['text'], result[0]['labels'][0])
        for result in hybrid_search_results
        if result
    ]
    logger.info(f"[entities_align_node][{tid}] 结果: {aligned_entities}")

    return {"aligned_entities": aligned_entities}


def _search_entity(entity: str,
                   label: str,
                   top_k: int = 3,
                   alpha: float = 0.5,
                   threshold: float = 0.6
                   ) -> list:
    """对单个实体进行线性混合检索"""
    logger.info(
        f"[混合检索] 入参 entity='{entity}', label='{label}', top_k={top_k}, alpha={alpha}, threshold={threshold}")

    query_vector = embedding_model.embed_query(entity)

    label_lower = label.lower()
    vector_index_name = f"{label_lower}_vector_index"
    fulltext_index_name = f"{label_lower}_fulltext_index"
    logger.info(f"[混合检索] 使用索引: vector='{vector_index_name}', fulltext='{fulltext_index_name}'")

    query = (
        """
        CALL {
            CALL db.index.vector.queryNodes($vector_index_name, $top_k * $effective_search_ratio, $query_vector)
            YIELD node, score
            WITH node, score LIMIT $top_k
            WITH collect({node: node, score: score}) AS nodes
            UNWIND nodes AS n
            WITH n.node AS node, n.score AS score
            RETURN node, score * $alpha AS score
            UNION
            CALL db.index.fulltext.queryNodes($fulltext_index_name, $query_text, {limit: $top_k})
            YIELD node, score
            WITH collect({node: node, score: score}) AS nodes, max(score) AS ft_index_max_score
            UNWIND nodes AS n
            WITH n.node AS node, (n.score / ft_index_max_score) AS rawScore
            RETURN node, rawScore * (1 - $alpha) AS score
        }
        WITH node, sum(score) AS score ORDER BY score DESC LIMIT $top_k
        RETURN node.`name` AS text, labels(node) AS labels, score, node {.*, `name`: Null, `embedding`: Null, id: Null } AS metadata
        """
    )

    run_params = {
        "vector_index_name": vector_index_name,
        "query_vector": query_vector,
        "fulltext_index_name": fulltext_index_name,
        "query_text": entity,
        "top_k": top_k,
        "effective_search_ratio": 1,
        "alpha": alpha,
    }

    with driver.session() as session:
        result = session.run(Query(text=query), run_params)
        records = result.data()

    logger.info(f"[混合检索] 原始结果({len(records)}条): {records}")

    retrieval_records = [record for record in records if record['score'] >= threshold]
    logger.info(f"[混合检索] 阈值过滤后({len(retrieval_records)}条): {retrieval_records}")
    return retrieval_records
