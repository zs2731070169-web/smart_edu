# 创建图
import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph

from backend.agent.context import EnvContext
from backend.agent.node.answer_node import answer
from backend.agent.node.entities_align_node import entities_align
from backend.agent.node.extract_entities_node import extract_entities
from backend.agent.node.generate_cypher_node import generate_cypher
from backend.agent.node.intent_node import intent_identify
from backend.agent.node.query_cypher_node import query_cypher
from backend.agent.node.validate_cypher_node import validate_cypher
from backend.agent.schema.schema import ValidateCypherResult
from backend.agent.state import OverallState
from backend.config.constants import MAX_CORRECT_LOOPS
from backend.config.settings import AGENT_WITH_MEMORY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")

graph_builder = StateGraph(state_schema=OverallState, context_schema=EnvContext)

graph_builder.add_node('intent_node', intent_identify)
graph_builder.add_node('extract_entities_node', extract_entities)
graph_builder.add_node('entities_align_node', entities_align)
graph_builder.add_node('generate_cypher_node', generate_cypher)
graph_builder.add_node('validate_cypher_node', validate_cypher)
graph_builder.add_node('query_cypher_node', query_cypher)
graph_builder.add_node('answer_node', answer)

graph_builder.set_entry_point("intent_node")


def route_intent_check(state: OverallState) -> str:
    """
        意图识别后的路由：
        - 业务无关 / 对话型 (is_relevant=False) → 直达 answer_node 转述 intent_reply
        - 知识查询且明确 → 走主流程 extract → align → ... → answer_node
        所有出口统一经过 answer_node 进行流式回复。
        """
    if not state.get("is_relevant"):
        return "direct"
    return "continue"


graph_builder.add_conditional_edges(
    "intent_node",
    route_intent_check,
    {"continue": "extract_entities_node", "direct": "answer_node"},
)
graph_builder.add_edge("extract_entities_node", "entities_align_node")
graph_builder.add_edge("entities_align_node","generate_cypher_node")
graph_builder.add_edge("generate_cypher_node", "validate_cypher_node")


def route_validate_cypher(state: OverallState) -> str:
    validates: list[ValidateCypherResult] = state.get("validates") or []
    has_error = any(not validate.is_correct for validate in validates)
    if not has_error:
        return "query_cypher"
    correct_count = state.get("correct_count", 0) or 0
    if correct_count >= MAX_CORRECT_LOOPS:
        logger.warning(
            f"HQL 纠错回路达到上限 {MAX_CORRECT_LOOPS} 次,仍未通过校验,转交 answer_node 兜底"
        )
        return "answer"
    return "generate_cypher"


graph_builder.add_conditional_edges(
    "validate_cypher_node",
    route_validate_cypher,
    {
        "query_cypher": "query_cypher_node",
        "generate_cypher": "generate_cypher_node",
        "answer": "answer_node",
    },
)

graph_builder.add_edge("query_cypher_node", "answer_node")
graph_builder.add_edge("answer_node", END)

graph = graph_builder.compile(
    checkpointer=InMemorySaver() if AGENT_WITH_MEMORY else None,
    debug=False,
)

if __name__ == '__main__':
    print(graph.get_graph().draw_mermaid())
