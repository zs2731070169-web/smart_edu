from enum import Enum


class ErrorTypes(str, Enum):
    """Cypher 校验错误类别"""
    SYNTAX = "syntax"      # 语法错误(EXPLAIN 失败)
    SEMANTIC = "semantic"  # 语义错误(节点/关系/属性不存在)
    LOGIC = "logic"        # 逻辑错误(查询意图与 Cypher 不一致)
    NONE = "none"          # 无错误
