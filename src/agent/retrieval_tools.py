import logging

from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI
from neo4j import GraphDatabase

from agent.prompts import extract_entities_prompt
from agent.schema import Entities, ExtractEntities
from config.config import NEO4J_CONFIG, EMBEDDINGS_MODEL, NEWCOIN_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrievalTools")


class Retriever:

    def __init__(self):
        # 加载neo4j驱动
        self.driver = GraphDatabase.driver(**NEO4J_CONFIG)
        logger.info("Neo4j 驱动初始化成功")

        # 加载neo4j图
        self.graph = Neo4jGraph(
            url=NEO4J_CONFIG["uri"],
            username=NEO4J_CONFIG["auth"][0],
            password=NEO4J_CONFIG["auth"][1]
        )
        logger.info("Neo4j 图加载完成")

        # 加载向量模型
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDINGS_MODEL,
            encode_kwargs={"normalize_embeddings": True}
        )
        logger.info("embedding 模型加载完成")

        # 获取设备
        # self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # 加载实体抽取模型
        # self.nlp_deberta_tokenizer = AutoTokenizer.from_pretrained(NLP_DEBERTA_MODEL)
        # self.nlp_deberta_model = AutoModelForTokenClassification.from_pretrained(NLP_DEBERTA_MODEL).to(self.device)
        # self.nlp_deberta_model.eval()

        self.llm_gpt = ChatOpenAI(
            model="gpt-5.2",
            base_url=NEWCOIN_CONFIG["url"],
            api_key=NEWCOIN_CONFIG["api_key"],
        )
        logger.info("gpt-5.2 模型加载完成")

        self.llm_opus = ChatOpenAI(
            model="claude-opus-4-6",
            base_url=NEWCOIN_CONFIG["url"],
            api_key=NEWCOIN_CONFIG["api_key"]
        )
        logger.info("claude-opus-4-6 模型加载完成")



    # @tool(
    #     name="实体抽取",
    #     description="从输入的文本中抽取实体，并返回实体列表"
    # )
    # def extract_entity(self, question: str) -> str:
    #     """
    #     执行实体抽取工具
    #     :param question:
    #     :return:
    #     """
    #
    #     # 基础模型加载
    #     inputs = self.nlp_deberta_tokenizer(
    #         question,
    #         padding=True,
    #         return_tensors="pt"
    #     )
    #     # 模型输入加载到GPU
    #     inputs_tensor = {k: v.to(self.device) for k, v in inputs.items()}
    #     # 执行模型推理
    #     with torch.no_grad():
    #         outputs = self.nlp_deberta_model(**inputs_tensor)
    #
    #     print(outputs.logits)
    #     # 获取模型预测结果
    #     """
    #     batch_size:指的是一次模型前向传播中输入的句子数量
    #     sequence_length:一句话的token数量
    #     num_labels：每个token的分数列表，维度对齐
    #     (batch_size=1, sequence_length=4, num_labels=3)
    #     [
    #       [   # 第一句话
    #         [类别1分数, 类别2分数, 类别3分数],  ← token1
    #         [类别1分数, 类别2分数, 类别3分数],  ← token2
    #         [类别1分数, 类别2分数, 类别3分数],  ← token3
    #         [类别1分数, 类别2分数, 类别3分数],  ← token4
    #       ]
    #     ]
    #     (2, 4, 3)
    #     [
    #       [  # 第1句话
    #         [x,x,x],
    #         [x,x,x],
    #         [x,x,x],
    #         [x,x,x],
    #       ],
    #       [  # 第2句话
    #         [x,x,x],
    #         [x,x,x],
    #         [x,x,x],
    #         [x,x,x],
    #       ]
    #     ]
    #     """
    #     # 获取最后一个维度（每个token的分数列表）的最大分数
    #     model_predictions = outputs.logits.argmax(dim=-1).tolist()
    #     final_predictions = []
    #     entity = ""
    #     # 遍历输入和预测结果
    #     for tokens, prediction in zip(question, model_predictions[0]):
    #         if 0 not in model_predictions[0]:
    #             final_predictions.append(entity)
    #         elif prediction == 1:
    #             entity += tokens
    #         elif prediction == 0:
    #             final_predictions.append(entity)
    #             entity = ""
    #
    #
    #     print(final_predictions)

    @tool(
        name_or_callable="实体抽取",
        description="从输入的文本中抽取实体，并返回实体列表和相关图标签",
        return_direct=False,
        args_schema=Entities
    )
    def extract_entities(self, question: str) -> str:
        """
        执行实体抽取工具
        :param question:
        :return:
        """
        prompt = extract_entities_prompt.invoke({"question": question, "schema": self.graph.get_structured_schema})

        llm_output = (self.llm_gpt
                      .with_structured_output(schema=Entities)
                      .invoke(prompt))

        logger.info(f"实体: {llm_output.entities}, 标签: {llm_output.label}")

        return llm_output

    @tool(
        name_or_callable="实体对齐",
        description="对实体进行对齐，并返回对齐后的实体列表和标签列表",
        return_direct=False
    )
    def entities_align(self, question: str, entities: ExtractEntities):
        """
        实体对齐
        1. 获取实体和标签列表
        2. 进行异步混合检索
        3.
        :param question:
        :param entities:
        :param labels:
        :return:
        """






if __name__ == '__main__':
    # retriever = Retriever()
    # retriever.extract_entities("马云创办了阿里巴巴")
