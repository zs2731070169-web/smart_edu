from typing import List

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """
    抽取的实体
    """
    entity: str = Field(default_factory=list, description="实体")
    label: str = Field(default_factory=list, description="标签")


class ExtractEntities(BaseModel):
    """
    实体抽取结果
    """
    entities: List[Entity] = Field(default_factory=list, description="实体列表")


class ExtractEntitiesQuestion(BaseModel):
    """
    实体抽取问题
    """
    question: str = Field(default="", description="用户问题")
