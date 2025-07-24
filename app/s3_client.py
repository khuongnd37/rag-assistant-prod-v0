import boto3
import streamlit as st
import tempfile
import os
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config as BotoConfig
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class S3FileManager:
    """Quản lý file S3 cho VNG Cloud vStorage"""
    
    def __init__(self):
        """Khởi tạo S3 client với VNG Cloud vStorage configuration"""
        self.s3_client = None
        self.bucket_name = None
        self._init_s3_client()
    
    def _init_s3_client(self):
        """Khởi tạo S3 client tối ưu cho VNG Cloud"""
        try:
            # Lấy credentials từ environment variables
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_DEFAULT_REGION', 'ap-southeast-1')
            self.bucket_name = os.getenv('S3_BUCKET_NAME')
            s3_endpoint = os.getenv('S3_ENDPOINT_URL', 'https://hcm03.vstorage.vngcloud.vn')
            
            if not all([aws_access_key, aws_secret_key, self.bucket_name]):
                logger.warning("⚠️ VNG Cloud S3 credentials không đầy đủ")
                logger.info("Cần: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME")
                return
            
            # Cấu hình boto3 tối ưu cho VNG Cloud
            boto_config = BotoConfig(
                region_name=aws_region,
                signature_version='s3v4',  # Quan trọng cho VNG Cloud
                s3={
                    'addressing_style': 'virtual'
                },
                retries={
                    'max_attempts': 3,
                    'mode': 'adaptive'
                }
            )
            
            # Khởi tạo boto3 session
            session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # Khởi tạo S3 client cho VNG Cloud
            self.s3_client = session.client(
                's3',
                endpoint_url=s3_endpoint,
                config=boto_config
            )
            
            logger.info(f"✅ Kết nối VNG Cloud vStorage thành công")
            logger.info(f"   Endpoint: {s3_endpoint}")
            logger.info(f"   Bucket: {self.bucket_name}")
            
            # Test connection
            self._test_connection()
            
        except NoCredentialsError:
            logger.error("❌ Không tìm thấy VNG Cloud credentials")
            self.s3_client = None
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo VNG Cloud S3 client: {e}")
            self.s3_client = None
    
    def _test_connection(self):
        """Test kết nối VNG Cloud và quyền truy cập bucket"""
        try:
            if self.s3_client and self.bucket_name:
                # Test với list_objects_v2 (tương thích tốt với VNG Cloud)
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    MaxKeys=1
                )
                logger.info(f"✅ VNG Cloud bucket '{self.bucket_name}' accessible")
                    
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logger.error(f"❌ Bucket '{self.bucket_name}' không tồn tại trên VNG Cloud")
            elif error_code == 'AccessDenied':
                logger.error(f"❌ Không có quyền truy cập bucket '{self.bucket_name}'")
            else:
                logger.error(f"❌ Lỗi VNG Cloud: {error_code} - {e}")
            self.s3_client = None
        except Exception as e:
            logger.error(f"❌ Lỗi test connection VNG Cloud: {e}")
            self.s3_client = None
    
    def is_available(self) -> bool:
        """Kiểm tra VNG Cloud S3 service có sẵn sàng không"""
        return self.s3_client is not None and self.bucket_name is not None
    
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> List[Dict[str, Any]]:
        """Liệt kê files trong VNG Cloud bucket"""
        if not self.is_available():
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    file_path = obj['Key']
                    file_extension = Path(file_path).suffix.lower()
                    
                    # Chỉ lấy files có extension được hỗ trợ
                    if file_extension in ['.pdf', '.docx', '.txt']:
                        files.append({
                            'key': file_path,
                            'name': Path(file_path).name,
                            'size': obj['Size'],
                            'size_mb': obj['Size'] / (1024 * 1024),
                            'last_modified': obj['LastModified'],
                            'extension': file_extension,
                            'folder': str(Path(file_path).parent) if '/' in file_path else ''
                        })
            
            logger.info(f"✅ Tìm thấy {len(files)} files hỗ trợ trong VNG Cloud bucket")
            return sorted(files, key=lambda x: x['last_modified'], reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Lỗi liệt kê files VNG Cloud: {e}")
            return []
    
    def download_file(self, s3_key: str) -> Optional[str]:
        """Download file từ VNG Cloud về temporary location"""
        if not self.is_available():
            return None
        
        try:
            # Tạo temporary file với extension phù hợp
            file_extension = Path(s3_key).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_path = tmp_file.name
            
            logger.info(f"⬇️ Đang download {s3_key} từ VNG Cloud...")
            
            self.s3_client.download_file(
                Bucket=self.bucket_name,
                Key=s3_key,
                Filename=tmp_path
            )
            
            # Verify file size
            downloaded_size = os.path.getsize(tmp_path)
            logger.info(f"✅ Downloaded {s3_key} ({downloaded_size / (1024*1024):.2f}MB)")
            
            return tmp_path
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"❌ File không tồn tại trên VNG Cloud: {s3_key}")
            elif error_code == 'AccessDenied':
                logger.error(f"❌ Không có quyền đọc file: {s3_key}")
            else:
                logger.error(f"❌ Lỗi VNG Cloud: {error_code} - {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Lỗi download file từ VNG Cloud {s3_key}: {e}")
            return None
    
    def search_files(self, search_term: str, prefix: str = "") -> List[Dict[str, Any]]:
        """Tìm kiếm files theo tên"""
        all_files = self.list_files(prefix=prefix)
        
        if not search_term:
            return all_files
        
        # Tìm kiếm không phân biệt hoa thường
        search_term = search_term.lower()
        filtered_files = [
            file for file in all_files 
            if search_term in file['name'].lower() or search_term in file['key'].lower()
        ]
        
        return filtered_files