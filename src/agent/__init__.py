from langchain.agents import create_agent


def agent():
    """
    检索智能体
    agent执行流程：
    1. 接收用户查询问题
    2. 执行实体抽取工具
    3. 执行实体对齐工具
    4. 执行cypher生成工具
    5. 执行cypher校验工具
    6. 执行cypher纠错工具
    7. 执行cypher语句进行检索
    8. 大模型接收检索结果，并返回给用户
    :return:
    """
    create_agent(

    )