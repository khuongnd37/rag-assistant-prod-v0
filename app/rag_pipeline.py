from typing import Dict, Any, List
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from vector_db import SimpleVectorDB
from config import Config
import logging

logger = logging.getLogger(__name__)

class ImprovedRAG:
    """RAG Pipeline - Improved for better response quality"""

    def __init__(self):
        self._init_llm()
        self._init_vector_db()
        self._init_prompts()
        logger.info("RAG Pipeline is ready")

    def _init_llm(self):
        try:
            self.llm = Ollama(
                model=Config.OLLAMA_MODEL,
                base_url=Config.OLLAMA_URL,
                temperature=0.2,
                timeout=120
            )
            logger.info(f"Testing Ollama connection: {Config.OLLAMA_URL}")
            test_response = self.llm.invoke("Hello")

            if test_response and len(test_response.strip()) > 0:
                logger.info(f"Ollama connected successfully: {Config.OLLAMA_MODEL}")
                logger.info(f"Test response: {test_response[:50]}...")
            else:
                logger.warning("Ollama returned empty response")
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            raise ConnectionError(f"Cannot connect to Ollama: {str(e)}")

    def _init_vector_db(self):
        try:
            logger.info("Initializing Vector Database...")
            self.vector_db = SimpleVectorDB()
            logger.info("Vector Database is ready")
        except Exception as e:
            logger.error(f"Failed to init Vector DB: {e}")
            raise

    def _init_prompts(self):
        self.rag_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful AI assistant.

TASK:
- Answer questions with relevant and complete information
- Use context from documents if available
- Add common knowledge if needed

RULES:
1. Use context from documents
2. Add general knowledge if needed
3. Answer clearly and accurately
4. Include examples if possible
5. Reply in Vietnamese

FORMAT:
- Start with a direct answer
- Expand using document info
- Add external knowledge if needed
- Conclude if needed"""),

            ("user", """DOCUMENT CONTEXT:
{context}

QUESTION: {question}

Answer the question using the documents above and general knowledge if needed.

ANSWER:""")
        ])

        self.general_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a general AI assistant with wide knowledge.

TASK:
- Answer questions based on general knowledge
- Provide useful and accurate information

RULES:
1. Reply in Vietnamese
2. Answer clearly and logically
3. Include examples if possible
4. Admit if information is uncertain"""),

            ("user", """QUESTION: {question}

Please answer based on general knowledge.

ANSWER:""")
        ])

        logger.info("Prompt templates initialized")

    def _create_smart_context(self, docs: List[Dict], max_length: int = 3000) -> str:
        if not docs:
            return ""

        context_parts = []
        current_length = 0

        for i, doc in enumerate(docs):
            if current_length >= max_length:
                break

            remaining_space = max_length - current_length
            if remaining_space < 200:
                break

            content = doc['content']
            if len(content) > remaining_space - 100:
                content = content[:remaining_space - 100] + "..."

            context_part = f"""[Doc {i+1}: {doc['title']}]
{content}
Score: {doc['score']:.3f}
---"""

            context_parts.append(context_part)
            current_length += len(context_part)

        return "\n\n".join(context_parts)

    def ask(self, question: str) -> Dict[str, Any]:
        try:
            logger.info(f"Received question: {question[:50]}...")

            docs = self.vector_db.search(question, k=Config.RAG_TOP_K)
            logger.info(f"Found {len(docs)} related documents")

            threshold = getattr(Config, 'RAG_SCORE_THRESHOLD', 0.75)
            high_quality_docs = [doc for doc in docs if doc['score'] >= threshold]

            if high_quality_docs:
                logger.info(f"Using RAG with {len(high_quality_docs)} high-score docs")
                return self._rag_response(question, high_quality_docs)
            else:
                logger.info("No relevant docs found above score threshold, using general knowledge")
                return self._general_response(question)

        except Exception as e:
            logger.error(f"RAG pipeline error: {e}")
            return {
                'answer': f"Sorry, an error occurred: {str(e)}",
                'sources': [],
                'success': False,
                'strategy': 'error'
            }

    def _rag_response(self, question: str, docs: List[Dict]) -> Dict[str, Any]:
        try:
            context = self._create_smart_context(docs)
            rag_chain = self.rag_prompt | self.llm | StrOutputParser()

            logger.info("Generating RAG answer...")
            answer = rag_chain.invoke({
                "context": context,
                "question": question
            })

            return {
                'answer': answer,
                'sources': docs,
                'success': True,
                'strategy': 'rag_with_documents'
            }

        except Exception as e:
            logger.error(f"RAG response error: {e}")
            return self._general_response(question)

    def _general_response(self, question: str) -> Dict[str, Any]:
        try:
            general_chain = self.general_prompt | self.llm | StrOutputParser()

            logger.info("Generating general knowledge answer...")
            answer = general_chain.invoke({"question": question})

            return {
                'answer': answer,
                'sources': [],
                'success': True,
                'strategy': 'general_knowledge'
            }

        except Exception as e:
            logger.error(f"General response error: {e}")
            return {
                'answer': "Xin loi, toi khong the tra loi do loi ky thuat.",
                'sources': [],
                'success': False,
                'strategy': 'error'
            }
