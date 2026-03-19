# app/agents/rag_agent.py

from app.services.vector_service import VectorService

class RAGAgent:
    def __init__(self):
        self.vector_service = VectorService()

    def run(self, query: str):
        results = self.vector_service.search(query)

        docs = []
        for i in range(len(results["documents"][0])):
            docs.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i]
            })

        return docs
if __name__ == "__main__":
    agent = RAGAgent()
    query = "请推荐腾讯游戏开发的岗位"
    results = agent.run(query)
    for doc in results:
        print(f"文本: {doc['text']}")
        print(f"元数据: {doc['metadata']}")
        print("-" * 50)