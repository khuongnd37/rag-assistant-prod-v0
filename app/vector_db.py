from opensearchpy import OpenSearch, RequestsHttpConnection
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import logging
from config import Config

logger = logging.getLogger(__name__)

class SimpleVectorDB:
    """Vector Database client cho VNG Cloud OpenSearch với index rag-assistant"""
    
    def __init__(self):
        self.config = Config.get_opensearch_config()
        self.index_name = Config.OPENSEARCH_INDEX
        
        # Kết nối OpenSearch
        self._init_client()
        
        # Load embedding model
        self._init_embedding()
    
    def _init_client(self):
        try:
            self.client = OpenSearch(
                hosts=self.config['hosts'],
                http_auth=self.config['http_auth'],
                use_ssl=self.config['use_ssl'],
                verify_certs=self.config['verify_certs'],
                ssl_show_warn=self.config['ssl_show_warn'],
                timeout=self.config['timeout'],
                connection_class=RequestsHttpConnection
            )
            info = self.client.info()
            logger.info(f"Kết nối OpenSearch thành công: {info.get('cluster_name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Lỗi kết nối OpenSearch: {e}")
            raise
    
    def _init_embedding(self):
        try:
            logger.info(f"Đang tải embedding model: {Config.EMBEDDING_MODEL}")
            self.embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL)
            logger.info("Embedding model đã sẵn sàng")
        except Exception as e:
            logger.error(f"Lỗi tải embedding model: {e}")
            raise
    
    def search(self, query: str, k: int = None) -> List[Dict[str, Any]]:
        k = k or Config.RAG_TOP_K
        try:
            query_vector = self.embedding_model.encode(query).tolist()
            search_body = {
                "size": k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_vector,
                            "k": k
                        }
                    }
                },
                "_source": ["content", "title", "source", "metadata"]
            }

            response = self.client.search(index=self.index_name, body=search_body)
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                results.append({
                    'content': source.get('content', source.get('text', '')),
                    'title': source.get('title', source.get('filename', 'Untitled')),
                    'source': source.get('source', ''),
                    'score': hit['_score'],
                    'metadata': source.get('metadata', {})
                })
                logger.info(f"[RESULT] {source.get('title')} | Score: {hit['_score']:.3f}")

            return results
        except Exception as e:
            logger.error(f"Lỗi tìm kiếm: {e}")
            return []
    
    def add_document(self, title: str, content: str, source: str = "", metadata: Dict = None):
        try:
            if not content.strip():
                logger.warning(f"⚠️ Bỏ qua chunk rỗng: {title}")
                return None

            embedding = self.embedding_model.encode(content)
            if embedding is None:
                logger.error(f"❌ Lỗi: embedding trả về None: {title}")
                return None

            embedding = embedding.tolist()

            if not isinstance(embedding, list) or not embedding:
                logger.error(f"❌ Embedding không hợp lệ (null hoặc empty list): {title}")
                return None

            doc = {
                'title': title,
                'content': content,
                'source': source,
                'embedding': embedding,
                'metadata': metadata or {}
            }
            response = self.client.index(index=self.index_name, body=doc)
            logger.info(f"✅ Đã thêm document: {title}")
            return response
        except Exception as e:
            logger.error(f"❌ Lỗi thêm document: {e}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        try:
            cluster_health = self.client.cluster.health()
            index_exists = self.client.indices.exists(index=self.index_name)
            return {
                'healthy': cluster_health.get('status') in ['green', 'yellow'] and index_exists,
                'cluster_status': cluster_health.get('status', 'unknown'),
                'index_exists': index_exists,
                'index_name': self.index_name
            }
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e)
            }
