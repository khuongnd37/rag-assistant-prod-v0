import streamlit as st
import hashlib
import os
import json
import time
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SimpleAuth:
    """Hệ thống xác thực đơn giản cho Streamlit RAG Application"""
    
    def __init__(self):
        self.users = self._load_users()
        self.session_timeout = 28800  # 8 giờ
        self.max_login_attempts = 5
    
    def _load_users(self) -> Dict[str, Dict]:
        """Tải users từ Kubernetes Secret"""
        users = {}
        
        # Đọc từ environment variable (Kubernetes Secret)
        users_json = os.getenv('STREAMLIT_USERS', '{}')
        try:
            users_data = json.loads(users_json)
            for username, password in users_data.items():
                users[username] = {
                    'password_hash': self._hash_password(password),
                    'name': username.title(),
                    'role': 'admin' if username == 'admin' else 'user',
                    'created_at': time.strftime("%Y-%m-%d")
                }
        except json.JSONDecodeError:
            # Fallback: tài khoản mặc định
            logger.warning("Sử dụng tài khoản mặc định")
            users['admin'] = {
                'password_hash': self._hash_password('admin123'),
                'name': 'Administrator',
                'role': 'admin',
                'created_at': time.strftime("%Y-%m-%d")
            }
        
        return users
    
    def _hash_password(self, password: str) -> str:
        """Hash mật khẩu với salt"""
        salt = "rag_system_2024_secure_salt"
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def _verify_credentials(self, username: str, password: str) -> bool:
        """Xác minh thông tin đăng nhập"""
        if username not in self.users:
            return False
        
        hashed_password = self._hash_password(password)
        return self.users[username]['password_hash'] == hashed_password
    
    def _is_session_valid(self) -> bool:
        """Kiểm tra session còn hiệu lực"""
        if not st.session_state.get('authenticated', False):
            return False
        
        login_time = st.session_state.get('login_timestamp', 0)
        current_time = time.time()
        
        # Kiểm tra timeout
        if current_time - login_time > self.session_timeout:
            self._clear_session()
            return False
        
        return True
    
    def _clear_session(self):
        """Xóa session data"""
        keys_to_clear = [
            'authenticated', 'username', 'user_info', 
            'login_timestamp', 'login_attempts'
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    def _show_login_form(self) -> bool:
        """Hiển thị form đăng nhập"""
        
        # CSS đơn giản cho login form
        st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            background-color: #f8f9fa;
        }
        .login-header {
            text-align: center;
            color: #1f77b4;
            margin-bottom: 2rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<h1 class="login-header">🔐 RAG System Login</h1>', unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            st.markdown("### 📝 Thông Tin Đăng Nhập")
            
            username = st.text_input(
                "👤 Tên đăng nhập", 
                placeholder="Nhập username"
            )
            
            password = st.text_input(
                "🔑 Mật khẩu", 
                type="password", 
                placeholder="Nhập password"
            )
            
            submitted = st.form_submit_button(
                "🚀 Đăng Nhập", 
                use_container_width=True
            )
            
            if submitted:
                if not username or not password:
                    st.error("⚠️ Vui lòng nhập đầy đủ thông tin!")
                    return False
                
                # Rate limiting
                login_attempts = st.session_state.get('login_attempts', 0)
                if login_attempts >= self.max_login_attempts:
                    st.error("🚫 Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau.")
                    return False
                
                if self._verify_credentials(username, password):
                    # Đăng nhập thành công
                    current_time = time.time()
                    user_info = self.users[username].copy()
                    user_info['last_login'] = time.strftime("%Y-%m-%d %H:%M:%S")
                    user_info['username'] = username
                    
                    # Lưu session
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user_info = user_info
                    st.session_state.login_timestamp = current_time
                    
                    # Xóa login attempts
                    if 'login_attempts' in st.session_state:
                        del st.session_state['login_attempts']
                    
                    st.success("✅ Đăng nhập thành công!")
                    time.sleep(1)
                    st.rerun()
                else:
                    # Đăng nhập thất bại
                    st.session_state.login_attempts = login_attempts + 1
                    st.error("❌ Tên đăng nhập hoặc mật khẩu không đúng!")
        
        # Thông tin demo
        with st.expander("ℹ️ Tài Khoản Demo"):
            st.markdown("""
            **Admin:** admin / admin123  
            **User:** phuongtra / phuongtra789
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    
    # ✅ METHOD CHÍNH - Đây là method được gọi từ main.py
    def require_authentication(self) -> Tuple[bool, Optional[Dict]]:
        """Method chính để yêu cầu xác thực - trả về tuple (is_authenticated, user_info)"""
        
        # Kiểm tra session còn hiệu lực
        if self._is_session_valid():
            user_info = st.session_state.get('user_info', {})
            return True, user_info
        
        # Hiển thị form đăng nhập nếu chưa xác thực
        self._show_login_form()
        return False, None
    
    def logout(self):
        """Đăng xuất người dùng"""
        self._clear_session()
        st.success("👋 Đã đăng xuất thành công!")
        time.sleep(1)
        st.rerun()
    
    def get_user_info(self) -> Dict:
        """Lấy thông tin user hiện tại"""
        return st.session_state.get('user_info', {})
    
    def get_username(self) -> str:
        """Lấy username hiện tại"""
        return st.session_state.get('username', 'Unknown')
    
    def is_authenticated(self) -> bool:
        """Kiểm tra trạng thái xác thực"""
        return self._is_session_valid()
