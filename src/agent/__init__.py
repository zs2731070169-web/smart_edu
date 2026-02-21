import asyncio
import logging

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from agent.context import graph_schema, llm_gpt
from agent.prompts import agent_system_prompt
from agent.retrieval_tools import entities_align_async, query_cypher, validate_cypher, extract_entities
from config.config import AGENT_WITH_MEMORY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Agent")


async def gen_agent():
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
    agent = create_agent(
        model=llm_gpt,
        tools=[extract_entities, entities_align_async, validate_cypher, query_cypher],
        system_prompt=agent_system_prompt.format(schema=graph_schema),
        checkpointer=InMemorySaver() if AGENT_WITH_MEMORY else None
    )

    return agent

async def main():
    agent = await gen_agent()
    result = await agent.ainvoke(
        {
            "messages": [
                {"role": "user", "content": "以下关于方法调用的代码的执行结果是 public class test { public static void main(string args[]) { int i = 99; mb_operate(i); system.out.print(i + 100); } static int mb_operate(int i) { return i + 100; }}，这个题目我要学习哪些课程和知识点"}
            ]
        },
        config={
            "configurable": {"thread_id": 1}
        }
    )

    logger.info(f"智能体执行结果:{result['messages'][-1].content}")



if __name__ == '__main__':
    asyncio.run(main())
