import os
import logging
from typing import Dict, Any

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    """Cấu hình cho RAG system với VNG Cloud OpenSearch, Ollama và S3"""
    
    # OpenSearch
    OPENSEARCH_URL = 'https://khuongnd3-opens-107444-344gj-hcm03.vdb-opensearch.vngcloud.vn:9200'
    OPENSEARCH_USER = 'master-user'
    OPENSEARCH_PASS = 'Broken@123'
    OPENSEARCH_INDEX = 'rag-assistant'
    
    # Cấu hình Ollama
    OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://ollama.ollama.svc.cluster.local:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:7b')
    
    # Cấu hình embedding
    EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
    EMBEDDING_DIM = 384
    
    # Cài đặt RAG
    RAG_TOP_K = int(os.getenv('RAG_TOP_K', '5'))
    
    # ✅ Cấu hình VNG Cloud S3
    S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', 'https://hcm03.vstorage.vngcloud.vn')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'ai-data')  # Thay đổi với tên bucket thực tế
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'hcm03')
    
    @classmethod
    def get_opensearch_config(cls) -> Dict[str, Any]:
        """Lấy cấu hình cho OpenSearch"""
        return {
            'hosts': [{'host': 'khuongnd3-opens-107444-344gj-hcm03.vdb-opensearch.vngcloud.vn', 'port': 9200}],
            'http_auth': (cls.OPENSEARCH_USER, cls.OPENSEARCH_PASS),
            'use_ssl': True,
            'verify_certs': True,
            'ssl_show_warn': False,
            'timeout': 60
        }
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration với logging chi tiết"""
        required = [
            ('OPENSEARCH_URL', cls.OPENSEARCH_URL),
            ('OPENSEARCH_USER', cls.OPENSEARCH_USER),
            ('OPENSEARCH_PASS', cls.OPENSEARCH_PASS),
            ('OLLAMA_URL', cls.OLLAMA_URL),
            ('S3_BUCKET_NAME', cls.S3_BUCKET_NAME),
            ('AWS_ACCESS_KEY_ID', cls.AWS_ACCESS_KEY_ID),
            ('AWS_SECRET_ACCESS_KEY', cls.AWS_SECRET_ACCESS_KEY)
        ]
        
        missing_configs = []
        for config_name, config_value in required:
            if not config_value:
                missing_configs.append(config_name)
            else:
                logger.info(f"✅ {config_name}: {config_value}")
        
        if missing_configs:
            logger.error(f"❌ Thiếu cấu hình: {missing_configs}")
            return False
        
        logger.info("✅ Configuration validation passed")
        return True
