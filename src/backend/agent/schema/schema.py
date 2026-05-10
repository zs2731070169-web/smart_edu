from typing import List, Dict

from pydantic import BaseModel, Field

from backend.agent.schema.enums import ErrorTypes


class Entity(BaseModel):
    """
    抽取的实体
    """
    entity: str = Field(default="", description="实体")
    label: str = Field(default="", description="标签")


class EntityPairs(BaseModel):
    """
    实体抽取结果
    """
    entity_pairs: List[Entity] = Field(default_factory=list, description="实体列表")


class ValidateCypherResult(BaseModel):
    """
    校验Cypher语句返回结果
    """
    is_correct: bool = Field(default=True, description="校验结果是否正确")
    errors: List[Dict[str, str]] = Field(default_factory=list, description="错误信息列表")
    suggestion: str = Field(default="", description="改进建议")
    error_type: ErrorTypes = Field(default=ErrorTypes.NONE, description="错误类别")


class IntentResult(BaseModel):
    """
    意图识别结果
    """
    is_relevant: bool = Field(default=True, description="是否为知识查询类问题(False = 业务无关或对话型,直接回答)")
    direct_reply: str = Field(default="", description="业务无关 / 对话型问题的直接回答原文,知识查询类必须留空")
