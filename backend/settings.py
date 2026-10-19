"""Backend-only configuration: defaults < TOML < local TOML < environment."""
import os
import tomllib
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]

class ModelSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['deepseek', 'openai-compatible'] = 'deepseek'
    api_base: str = 'https://api.deepseek.com'
    name: str = Field(default='deepseek-flash', min_length=1, max_length=100)
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(''))
    timeout_seconds: float = Field(default=40, gt=0, le=300)
    max_attempts: int = Field(default=2, ge=1, le=3)
    max_tokens: int = Field(default=8192, ge=256, le=32768)

    @field_validator('api_base')
    @classmethod
    def valid_base(cls, value):
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('API base must be an HTTPS URL without credentials or query parameters')
        if url.path.rstrip('/').endswith('/chat/completions'):
            raise ValueError('Specify a base URL, not the full chat/completions endpoint')
        return value.rstrip('/')

    @property
    def configured(self):
        return bool(self.api_key.get_secret_value().strip())

def load_settings():
    path = Path(os.getenv('CAIHE_CONFIG_FILE', str(ROOT / 'config.toml')))
    values = {}
    for file in (path, path.with_name('config.local.toml')):
        if not file.exists():
            if file == path and 'CAIHE_CONFIG_FILE' in os.environ:
                raise ValueError('模型配置文件不存在，请检查 CAIHE_CONFIG_FILE')
            continue
        try:
            # utf-8-sig also accepts files saved by Windows PowerShell with a BOM.
            raw = tomllib.loads(file.read_text(encoding='utf-8-sig'))
            if set(raw) - {'model'} or not isinstance(raw.get('model', {}), dict):
                raise ValueError('Invalid model configuration section')
            values.update(raw.get('model', {}))
        except (OSError, UnicodeError, ValueError):
            # TOML and Pydantic exceptions can include credentials: never expose them.
            raise ValueError('模型配置文件无法读取或 TOML 格式有误，请检查 [model] 配置；配置内容未输出') from None
    overrides = {'MODEL_API_BASE':'api_base', 'MODEL_NAME':'name',
                 'MODEL_API_KEY':'api_key', 'DEEPSEEK_API_KEY':'api_key'}
    for env, field in overrides.items():
        if env in os.environ:
            values[field] = os.environ[env].strip()
    try:
        return ModelSettings.model_validate(values)
    except ValidationError:
        raise ValueError('模型配置无效：请检查字段名、HTTPS 基址、模型名称、超时、重试次数和输出长度；配置内容未输出') from None
