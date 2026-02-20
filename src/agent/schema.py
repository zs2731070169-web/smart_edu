from typing import List, Dict

from pydantic import BaseModel, Field


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

class GenCypher(BaseModel):
    """
    构建Cypher查询语句
    """
    question: str = Field(default="", description="用户问题")
    entities: List[Entity] = Field(default_factory=list, description="实体列表")

class ValidateCypher(BaseModel):
    """
    校验Cypher语句调用参数
    """
    cypher: str = Field(default="", description="cypher语句")
    question: str = Field(default="", description="用户问题")
    entities: List[Entity] = Field(default="", description="实体列表")

class ValidateCypherResult(BaseModel):
    """
    校验Cypher语句返回结果
    """
    is_correct: bool = Field(default="", description="校验结果是否正确")
    errors: List[Dict[str, str]] = Field(default="", description="错误列表")
