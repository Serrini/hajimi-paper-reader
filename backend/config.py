import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Debug mode
    DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1')

    # LLM Configuration
    LLM_API_URL = os.getenv('LLM_API_URL', 'https://api.openai.com/v1')
    LLM_API_KEY = os.getenv('LLM_API_KEY', '')
    LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o')
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.1'))
    # max_tokens 为空或 0 时不限制
    _max_tokens = os.getenv('LLM_MAX_TOKENS', '').strip()
    LLM_MAX_TOKENS = int(_max_tokens) if _max_tokens else None

    # Local Storage Configuration
    BASE_USER_DIR = os.path.expanduser('~/.hajimi_paper_reader')
    DATA_DIR = os.getenv('DATA_DIR', os.path.join(BASE_USER_DIR, 'data'))
    LOCAL_STORAGE_DIR = os.path.join(DATA_DIR, 'storage')
    SQLITE_DB_PATH = os.path.join(DATA_DIR, 'agent.db')
    JWT_SECRET_FILE = os.path.join(DATA_DIR, '.jwt_secret')
    
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)

    @classmethod
    def get_db_url(cls):
        return f"sqlite:///{cls.SQLITE_DB_PATH}"

    @classmethod
    def get_jwt_secret(cls):
        configured_secret = (os.getenv('JWT_SECRET') or '').strip()
        if configured_secret:
            return configured_secret

        if os.path.exists(cls.JWT_SECRET_FILE):
            with open(cls.JWT_SECRET_FILE, 'r', encoding='utf-8') as f:
                persisted_secret = f.read().strip()
            if persisted_secret:
                return persisted_secret

        generated_secret = secrets.token_hex(32)
        with open(cls.JWT_SECRET_FILE, 'w', encoding='utf-8') as f:
            f.write(generated_secret)
        return generated_secret

    @classmethod
    def get_llm_config(cls):
        from api.deps import current_user_settings
        settings = current_user_settings.get() or {}
        
        api_url = (settings.get('llm_api_url') or "").strip() or None
        api_key = (settings.get('llm_api_key') or "").strip() or None
        model = (settings.get('llm_model') or "").strip() or None

        if not api_url:
            api_url = cls.LLM_API_URL
        if not api_key:
            api_key = cls.LLM_API_KEY
        if not model:
            model = cls.LLM_MODEL
        
        if not api_key:
            raise ValueError("缺少大模型 API Key，请在用户设置或环境变量中配置。")

        return {
            'api_url': api_url,
            'api_key': api_key,
            'model': model,
            'temperature': cls.LLM_TEMPERATURE,
            'max_tokens': cls.LLM_MAX_TOKENS
        }
