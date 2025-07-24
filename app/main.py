import streamlit as st
import tempfile
import os
import time
from rag_pipeline import ImprovedRAG
from document_processor import DocumentProcessor
from vector_db import SimpleVectorDB
from config import Config
from auth import SimpleAuth
from s3_client import S3FileManager

# Cấu hình trang
st.set_page_config(
    page_title="RAG Assistant",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Khởi tạo authentication system
auth = SimpleAuth()

# ===== KIỂM TRA AUTHENTICATION TRƯỚC KHI LÀM GÌ KHÁC =====
is_authenticated, user_info = auth.require_authentication()

if not is_authenticated:
    st.stop()

# ===== CHỈ CHẠY KHI ĐÃ ĐĂNG NHẬP =====

# Header với thông tin user và logout
col1, col2, col3 = st.columns([4, 2, 1])

with col1:
    st.title("🤖 RAG Assistant")
    st.markdown("*Hệ thống hỏi đáp thông minh với dữ liệu doanh nghiệp*")

with col2:
    st.markdown(f"""
    **👤 Xin chào:** *{user_info.get('name', auth.get_username())}*
    
    **🕐 Đăng nhập:** *{user_info.get('last_login', 'Vừa đăng nhập')}*
    
    **👑 Vai trò:** *{user_info.get('role', 'User').title()}*
    """)

with col3:
    if st.button("🚪 Đăng Xuất", use_container_width=True, type="secondary", key="logout_btn"):
        auth.logout()

st.divider()

# Khởi tạo components (chỉ khi đã authenticated)
@st.cache_resource
def init_rag():
    """Khởi tạo RAG system"""
    if not Config.validate():
        st.error("❌ Cấu hình không hợp lệ!")
        st.stop()
    return ImprovedRAG()

@st.cache_resource
def init_db():
    """Khởi tạo Vector Database"""
    return SimpleVectorDB()

@st.cache_resource
def init_document_processor():
    """Khởi tạo DocumentProcessor"""
    return DocumentProcessor(
        chunk_size=int(os.getenv("chunk_size", "1000")),
        chunk_overlap=int(os.getenv("chunk_overlap", "200")),
        max_file_size_mb=50,
        enable_smart_splitting=True
    )

@st.cache_resource
def init_s3_manager():
    """Khởi tạo S3 File Manager"""
    return S3FileManager()

# Load components
try:
    with st.spinner("🔄 Đang khởi tạo hệ thống RAG..."):
        rag = init_rag()
        vector_db = init_db()
        document_processor = init_document_processor()
        s3_manager = init_s3_manager()

    # Health check
    health = vector_db.health_check()
    if health['healthy']:
        st.success(f"✅ Hệ thống sẵn sàng! Index: **{health['index_name']}**")
    else:
        st.warning(f"⚠️ Cảnh báo hệ thống: {health.get('error', 'Unknown issue')}")
    
    # S3 status check
    if s3_manager.is_available():
        st.success(f"✅ VNG Cloud S3 sẵn sàng! Bucket: **{s3_manager.bucket_name}**")
    else:
        st.info("ℹ️ VNG Cloud S3 không khả dụng - chỉ hỗ trợ upload file local")

except Exception as e:
    st.error(f"❌ Lỗi khởi tạo hệ thống: {str(e)}")
    st.info("💡 Vui lòng liên hệ quản trị viên hoặc thử lại sau.")
    st.stop()

# ===== HELPER FUNCTIONS =====
def process_uploaded_file(uploaded_file, file_size, source_type):
    """Xử lý file upload local"""
    with st.spinner("⚡ Đang xử lý file và tạo embeddings..."):
        tmp_path = None
        try:
            file_extension = os.path.splitext(uploaded_file.name)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            process_file_common(tmp_path, uploaded_file.name, file_size, source_type)
            
        except Exception as e:
            st.sidebar.error(f"❌ Lỗi xử lý file: {str(e)}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

def process_s3_files(selected_files):
    """Xử lý multiple files từ VNG Cloud S3"""
    total_files = len(selected_files)
    processed_count = 0
    
    # ✅ SỬA: Loại bỏ key parameter khỏi st.progress()
    main_progress = st.sidebar.progress(0)
    main_status = st.sidebar.empty()
    
    for i, file_info in enumerate(selected_files):
        main_status.text(f"Đang xử lý file {i+1}/{total_files}: {file_info['name']}")
        
        try:
            tmp_path = s3_manager.download_file(file_info['key'])
            
            if tmp_path:
                success = process_file_common(
                    tmp_path, 
                    file_info['name'], 
                    file_info['size_mb'], 
                    "vng_cloud_s3"
                )
                
                if success:
                    processed_count += 1
                
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
        except Exception as e:
            st.sidebar.error(f"❌ Lỗi xử lý {file_info['name']}: {e}")
        
        main_progress.progress((i + 1) / total_files)
    
    main_progress.empty()
    main_status.empty()
    
    if processed_count > 0:
        st.sidebar.success(f"🎉 Đã xử lý thành công {processed_count}/{total_files} files từ VNG Cloud S3!")
        st.sidebar.balloons()
    else:
        st.sidebar.error("❌ Không thể xử lý file nào từ VNG Cloud S3!")

def process_file_common(file_path, original_file_name, file_size_mb, source_type):
    """Hàm chung để xử lý tài liệu"""
    docs = []
    try:
        documents = document_processor.process_document(file_path)
        
        for doc in documents:
            docs.append({
                'title': doc.metadata.get('file_name', original_file_name),
                'content': doc.page_content,
                'source': doc.metadata.get('source', file_path),
                'metadata': doc.metadata
            })
        
        st.sidebar.success(f"✅ Đã xử lý thành công {len(docs)} chunks từ file")
        
    except Exception as process_error:
        st.sidebar.error(f"❌ Lỗi xử lý file: {str(process_error)}")
        return False
    
    if docs:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        for doc in docs:
            doc['metadata'].update({
                'uploaded_by': auth.get_username(),
                'uploaded_by_name': user_info.get('name', auth.get_username()),
                'upload_time': current_time,
                'file_size_mb': f"{file_size_mb:.2f}",
                'source_type': source_type
            })
        
        success_count = 0
        total_docs = len(docs)
        
        # ✅ SỬA: Loại bỏ key parameter khỏi st.progress()
        progress_bar = st.sidebar.progress(0)
        status_text = st.sidebar.empty()
        
        for i, doc in enumerate(docs):
            try:
                result = vector_db.add_document(
                    title=doc['title'],
                    content=doc['content'],
                    source=doc['source'],
                    metadata=doc['metadata']
                )
                if result:
                    success_count += 1
            except Exception as doc_error:
                st.sidebar.warning(f"⚠️ Lỗi document {i+1}: {str(doc_error)}")
            
            progress = (i + 1) / total_docs
            progress_bar.progress(progress)
            status_text.text(f"Xử lý: {i + 1}/{total_docs}")
        
        progress_bar.empty()
        status_text.empty()
        
        if success_count > 0:
            st.sidebar.success(f"🎉 Thành công! Đã upload {success_count}/{total_docs} documents")
            
            stats = document_processor.get_statistics([
                type('Document', (), {'page_content': doc['content'], 'metadata': doc['metadata']})()
                for doc in docs
            ])
            
            with st.sidebar.expander("📊 Thống kê xử lý"):
                st.write(f"📄 Tổng chunks: {stats['total_documents']}")
                st.write(f"📝 Tổng ký tự: {stats['total_characters']:,}")
                st.write(f"📏 Kích thước TB: {stats['average_chunk_size']:.0f}")
                st.write(f"🔍 Loại tài liệu: {list(stats['document_types'].keys())}")
            
            return True
        else:
            st.sidebar.error("❌ Không thể upload documents nào!")
            return False
    
    return False

# ===== SIDEBAR - DOCUMENT MANAGEMENT =====
st.sidebar.title("📁 Quản Lý Tài Liệu")
st.sidebar.markdown(f"*Đăng nhập bởi: **{user_info.get('name', auth.get_username())}***")

# Tabs cho Local Upload và S3 Browser
if s3_manager.is_available():
    upload_tab, s3_tab = st.sidebar.tabs(["📤 Upload Local", "☁️ VNG Cloud S3"])
else:
    upload_tab = st.sidebar.container()
    st.sidebar.info("ℹ️ VNG Cloud S3 không khả dụng - chỉ hỗ trợ upload file local")

# ===== TAB 1: LOCAL UPLOAD =====
with upload_tab:
    uploaded_file = st.file_uploader(
        "📤 Chọn file để upload",
        type=['pdf', 'docx', 'txt'],
        help="Hỗ trợ các định dạng: PDF, DOCX, TXT (tối đa 50MB)",
        key="local_file_uploader"
    )
    
    if uploaded_file:
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)
        st.info(f"""
        **📄 File:** {uploaded_file.name}
        **📊 Kích thước:** {file_size:.2f} MB
        **📋 Loại:** {uploaded_file.type}
        """)
        
        if st.button("🚀 Upload & Xử Lý", use_container_width=True, key="local_upload_btn"):
            process_uploaded_file(uploaded_file, file_size, "local")

# ===== TAB 2: VNG CLOUD S3 BROWSER =====
if s3_manager.is_available():
    with s3_tab:
        col1, col2 = st.columns(2)
        
        with col1:
            search_term = st.text_input(
                "🔍 Tìm kiếm",
                placeholder="Tên file...",
                key="s3_search_input"
            )
        
        with col2:
            folder_prefix = st.text_input(
                "📁 Thư mục",
                placeholder="documents/",
                help="Để trống để xem tất cả",
                key="s3_folder_prefix_input"
            )
        
        if st.button("🔄 Refresh", use_container_width=True, key="s3_refresh_btn"):
            st.cache_resource.clear()
            st.rerun()
        
        try:
            with st.spinner("📋 Đang tải danh sách files từ VNG Cloud S3..."):
                if search_term:
                    s3_files = s3_manager.search_files(search_term, folder_prefix)
                else:
                    s3_files = s3_manager.list_files(folder_prefix)
            
            if s3_files:
                st.write(f"**Tìm thấy {len(s3_files)} files:**")
                
                selected_files = []
                for i, file_info in enumerate(s3_files[:20]):
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            file_selected = st.checkbox(
                                f"**{file_info['name']}**",
                                key=f"s3_file_checkbox_{i}",
                                help=f"Path: {file_info['key']}\nModified: {file_info['last_modified'].strftime('%Y-%m-%d %H:%M')}"
                            )
                            
                            if file_selected:
                                selected_files.append(file_info)
                        
                        with col2:
                            st.write(f"{file_info['size_mb']:.1f}MB")
                        
                        with col3:
                            st.write(f"{file_info['extension']}")
                
                if selected_files:
                    st.write(f"**Đã chọn {len(selected_files)} files**")
                    
                    if st.button("☁️ Xử Lý Files từ VNG Cloud S3", use_container_width=True, key="s3_process_files_btn"):
                        process_s3_files(selected_files)
                        
            else:
                st.info("📂 Không tìm thấy files nào trong VNG Cloud S3")
                
        except Exception as e:
            st.error(f"❌ Lỗi tải files từ VNG Cloud S3: {e}")

# ===== MAIN CHAT INTERFACE =====

if 'messages' not in st.session_state:
    st.session_state.messages = []

if len(st.session_state.messages) == 0:
    st.info(f"""
    👋 **Chào mừng {user_info.get('name', auth.get_username())} đến với RAG Assistant!**
    
    🤖 Tôi có thể giúp bạn:
    - Trả lời câu hỏi dựa trên tài liệu đã upload
    - Cung cấp thông tin từ kiến thức chung
    - Phân tích và tóm tắt nội dung
    
    💡 **Gợi ý:** Hãy upload tài liệu của bạn ở sidebar để tôi có thể trả lời chính xác hơn!
    """)

# Hiển thị chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if "timestamp" in message:
            st.caption(f"⏰ {message['timestamp']}")
        
        if message["role"] == "assistant" and "sources" in message:
            if message["sources"]:
                with st.expander("📚 Nguồn tham khảo từ tài liệu"):
                    for i, doc in enumerate(message["sources"]):
                        st.write(f"**{i+1}. {doc['title']}**")
                        st.write(f"*Độ liên quan: {doc['score']:.4f}*")
                        
                        metadata = doc.get('metadata', {})
                        if 'uploaded_by_name' in metadata:
                            st.write(f"*📤 Upload bởi: {metadata['uploaded_by_name']} lúc {metadata.get('upload_time', 'unknown')} (Nguồn: {metadata.get('source_type', 'unknown')})*")
                        
                        st.write(f"📄 {doc['content'][:300]}...")
                        
                        if i < len(message["sources"]) - 1:
                            st.divider()

# Chat input
if prompt := st.chat_input("💬 Hỏi gì đó về dữ liệu hoặc bất kỳ chủ đề nào..."):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "timestamp": current_time,
        "username": auth.get_username()
    })
    
    with st.chat_message("user"):
        st.markdown(prompt)
        st.caption(f"⏰ {current_time}")
    
    with st.chat_message("assistant"):
        with st.spinner("🤔 Đang phân tích câu hỏi và tạo câu trả lời..."):
            result = rag.ask(prompt)
        
        st.markdown(result['answer'])
        
        strategy = result.get('strategy', 'unknown')
        strategy_info = {
            'rag_with_documents': "🔍 **Phương pháp:** Dựa trên tài liệu doanh nghiệp với độ tin cậy cao",
            'hybrid_approach': "🔀 **Phương pháp:** Kết hợp tài liệu doanh nghiệp và kiến thức chung",
            'general_knowledge': "🧠 **Phương pháp:** Dựa trên kiến thức chung (không tìm thấy tài liệu liên quan)"
        }
        
        if strategy in strategy_info:
            st.info(strategy_info[strategy])
        
        if result.get('sources'):
            with st.expander("📚 Nguồn tham khảo từ tài liệu"):
                for i, doc in enumerate(result['sources']):
                    st.write(f"**{i+1}. {doc['title']}**")
                    st.write(f"*Độ liên quan: {doc['score']:.4f}*")
                    
                    metadata = doc.get('metadata', {})
                    if 'uploaded_by_name' in metadata:
                        st.write(f"*📤 Upload bởi: {metadata['uploaded_by_name']} lúc {metadata.get('upload_time', 'unknown')} (Nguồn: {metadata.get('source_type', 'unknown')})*")
                    
                    st.write(f"📄 {doc['content'][:300]}...")
                    
                    if i < len(result['sources']) - 1:
                        st.divider()
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": result['answer'],
            "sources": result.get('sources', []),
            "strategy": strategy,
            "timestamp": current_time
        })

# ===== SIDEBAR CONTROLS =====
st.sidebar.markdown("---")

with st.sidebar.expander("📁 Quản lý tài liệu"):
    if st.button("🔍 Kiểm tra hệ thống", use_container_width=True, key="system_health_check_btn"):
        try:
            processor_status = "✅ Sẵn sàng" if document_processor else "❌ Lỗi"
            st.write(f"DocumentProcessor: {processor_status}")
            
            health = vector_db.health_check()
            db_status = "✅ Kết nối" if health['healthy'] else f"❌ {health.get('error', 'Lỗi')}"
            st.write(f"Vector Database: {db_status}")
            
            s3_status = "✅ Kết nối" if s3_manager.is_available() else "❌ Không khả dụng"
            st.write(f"VNG Cloud S3: {s3_status}")
            
            if document_processor:
                st.write(f"Chunk size: {document_processor.chunk_size}")
                st.write(f"Chunk overlap: {document_processor.chunk_overlap}")
                st.write(f"Max file size: {document_processor.max_file_size_mb}MB")
                
        except Exception as e:
            st.error(f"Lỗi kiểm tra: {e}")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("🗑️ Xóa Chat", use_container_width=True, key="clear_chat_history_btn"):
        st.session_state.messages = []
        st.rerun()

with col2:
    if st.button("🔄 Refresh", use_container_width=True, key="main_app_refresh_btn"):
        st.rerun()

with st.sidebar.expander("ℹ️ Thông tin hệ thống"):
    st.markdown(f"""
    **OpenSearch Index:** {Config.OPENSEARCH_INDEX}
    **Ollama Model:** {Config.OLLAMA_MODEL}
    **Embedding:** {Config.EMBEDDING_MODEL}
    **Current User:** {auth.get_username()}
    **User Role:** {user_info.get('role', 'User').title()}
    **S3 Endpoint:** {Config.S3_ENDPOINT_URL}
    **S3 Bucket:** {Config.S3_BUCKET_NAME or 'Không cấu hình'}
    """)

with st.sidebar.expander("📊 Hoạt động của tôi"):
    user_messages = [msg for msg in st.session_state.messages if msg.get('username') == auth.get_username()]
    st.metric("Số câu hỏi đã hỏi", len([msg for msg in user_messages if msg['role'] == 'user']))
    st.metric("Số câu trả lời nhận được", len([msg for msg in user_messages if msg['role'] == 'assistant']))
    
    if user_messages:
        strategies = [msg.get('strategy', 'unknown') for msg in user_messages if msg['role'] == 'assistant']
        strategy_counts = {}
        for strategy in strategies:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        if strategy_counts:
            st.markdown("**Phương pháp trả lời:**")
            for strategy, count in strategy_counts.items():
                strategy_names = {
                    'rag_with_documents': '📄 Từ tài liệu',
                    'hybrid_approach': '🔀 Kết hợp',
                    'general_knowledge': '🧠 Kiến thức chung'
                }
                name = strategy_names.get(strategy, strategy)
                st.write(f"{name}: {count}")

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; color: #666; font-size: 0.8em;">
    <p>🔒 RAG System v2.0</p>
    <p>Enterprise AI Assistant</p>
    <p>with VNG Cloud S3 Integration</p>
</div>
""", unsafe_allow_html=True)
