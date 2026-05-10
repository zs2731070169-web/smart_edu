from typing import List, Tuple

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from backend.agent.schema.schema import Entity, ValidateCypherResult


class OverallState(TypedDict, total=False):
    # 对话历史, add_messages会自动把节点返回的的messages字典转Message对象并进行追加
    messages: Annotated[List[AnyMessage], add_messages]
    # 用户原始问题
    question: str

    # 意图识别结果
    is_relevant: bool
    intent_reply: str

    # 实体抽取与对齐
    entity_pairs: List[Entity]
    aligned_entities: List[Tuple[str, str]]

    # Cypher 生成 / 校验回路 / 查询
    cypher: str
    validates: List[ValidateCypherResult]
    correct_count: int
    query_results: list
