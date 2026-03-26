from typing import Dict, Any, List, Optional

from pydantic import Field, BaseModel


class NodeRelation(BaseModel):
    start_label: str = Field(default="", description="开始节点标签")
    end_label: str = Field(default="", description="结束节点标签")
    relation_label: str = Field(default="", description="节点之间的关系")
    properties: List[Dict[str, Any]] = Field(default=None, description="节点和关系的属性属性")


class Node(BaseModel):
    label: str = Field(default="", description="节点标签")
    properties: List[Dict[str, Any]] = Field(default=None, description="节点属性")


class FullIndex(BaseModel):
    index_name: str = Field(default="", description="索引名称")
    label: str = Field(default="", description="节点标签")
    property: str = Field(default="", description="索引属性")

class VectorIndex(BaseModel):
    index_name: str = Field(default="", description="索引名称")
    label: str = Field(default="", description="节点标签")
    text_property: str = Field(default="", description="向量文本属性")
    id_property: str = Field(default="", description="向量id属性")

