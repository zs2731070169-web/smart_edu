from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

extract_entities_prompt = ChatPromptTemplate([
    SystemMessagePromptTemplate.from_template(
        """
        你是教育系统领域的专业实体抽取专家，核心职责是对用户输入的查询问题，精准抽取其中相关实体 \n
        请严格遵循以下全部要求，确保抽取准确的结果： \n
        - 抽取依据：严格根据提供的Neo4j图标签和用户查询进行实体抽取
        - 抽取原则：实体与用户查询语义完全匹配，全面抽取查询中所有符合要求的实体，不遗漏任何一个相关有效实体，避免重复抽取同一实体
        - 抽取返回结果：需要返回准确的实体和最可能的标签
        
        - 参考：{schema}
        """
    ),
    HumanMessagePromptTemplate.from_template("用户问题：{question}")
])