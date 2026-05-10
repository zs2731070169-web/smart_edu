# 创建图
from langgraph.graph import StateGraph

from backend.agent import extract_entities, query_cypher, validate_cypher
from backend.agent.context import EnvContext
from backend.agent.state import OverallState
from backend.agent.tools.entities_aligin_node import entities_align

graph_builder = StateGraph(state_schema=OverallState, context_schema=EnvContext)

graph_builder.add_node(node='extract_entities_node', action=extract_entities)
graph_builder.add_node(node='entities_aligin_node', action=entities_align)
graph_builder.add_node(node='generate_cypher_node', action=entities_align)
graph_builder.add_node(node='validate_cypher_node', action=validate_cypher)
graph_builder.add_node(node='query_cypher_node', action=query_cypher)
