"""
Memory system configuration for Project Dawn
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import json


def get_memory_config(consciousness_id: str, base_config: Optional[Dict] = None) -> Dict[str, Any]:
    """Get memory configuration for a consciousness"""
    # Load from environment or config file
    config_path = os.getenv('MEMOS_CONFIG_PATH', 'config/memory.yaml')
    
    # Default configuration
    config = {
        "storage": {
            "vector_store": {
                "type": "chromadb",
                "persistent": True,
                "path": f"data/consciousness_{consciousness_id}/vector",
                "embedding_model": os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'),
                "embedding_dimension": int(os.getenv('EMBEDDING_DIM', '384')),
                "distance_metric": "cosine"
            },
            "relational_db": {
                "type": "sqlite",
                "path": f"data/consciousness_{consciousness_id}/memories/vault.db",
                "connection_pool_size": 5,
                "timeout": 30.0
            },
            "blob_storage": {
                "type": os.getenv('BLOB_STORAGE_TYPE', 'filesystem'),
                "path": f"data/consciousness_{consciousness_id}/memories/blobs",
                # S3 configuration (if using S3)
                "s3_bucket": os.getenv('S3_BUCKET'),
                "s3_region": os.getenv('S3_REGION', 'us-east-1'),
                "s3_access_key": os.getenv('S3_ACCESS_KEY'),
                "s3_secret_key": os.getenv('S3_SECRET_KEY')
            }
        },
        "policies": {
            "default_ttl": None,  # Memories don't expire by default
            "max_memory_size": 10 * 1024 * 1024,  # 10MB
            "access_control_model": "owner_based",
            "auto_archive_after": 30 * 24 * 3600,  # 30 days
            "compression_threshold": 1024 * 1024,   # 1MB
            "enable_pii_detection": True,
            "auto_redact": True,
            "strict_mode": os.getenv('MEMOS_STRICT_MODE', 'false').lower() == 'true',
            "cache_ttl": 300  # 5 minutes
        },
        "audit": {
            "backend": os.getenv('AUDIT_BACKEND', 'sqlite'),
            "path": f"data/consciousness_{consciousness_id}/memories/governance.db",
            "retention_days": 90,
            "elasticsearch_url": os.getenv('ELASTICSEARCH_URL'),
            "elasticsearch_index": os.getenv('ELASTICSEARCH_AUDIT_INDEX', 'memory-audit')
        },
        "transformation": {
            "enable_kv_cache": True,
            "kv_cache_ttl": 3600,  # 1 hour
            "enable_lora_distillation": os.getenv('ENABLE_LORA', 'true').lower() == 'true',
            "lora_rank": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.1,
            "model_name": os.getenv('LLM_MODEL', 'gpt2'),
            "tokenizer_name": os.getenv('TOKENIZER_MODEL', 'gpt2'),
            "device": os.getenv('TORCH_DEVICE', 'cpu'),
            "batch_size": 10
        },
        "optimization": {
            "hot_memory_threshold": 10,  # Access count
            "hot_memory_window": 3600,   # 1 hour
            "enable_predictive_loading": True,
            "cache_size_mb": int(os.getenv('MEMORY_CACHE_SIZE_MB', '512')),
            "enable_compression": True,
            "compression_algorithm": "zstd"
        },
        "scheduler": {
            "max_concurrent_operations": 10,
            "operation_timeout": 30.0,
            "retry_attempts": 3,
            "retry_delay": 1.0
        },
        "lifecycle": {
            "garbage_collection_interval": 3600,  # 1 hour
            "auto_archive_days": 30,
            "merge_detection_interval": 3600,  # 1 hour
            "merge_similarity_threshold": 0.8,
            "state_transition_cooldown": 300  # 5 minutes
        },
        "nlp_model": os.getenv('NLP_MODEL', 'local'),  # 'local', 'openai', 'anthropic'
        "nlp_config": {
            "openai_api_key": os.getenv('OPENAI_API_KEY'),
            "anthropic_api_key": os.getenv('ANTHROPIC_API_KEY'),
            "local_model_path": os.getenv('LOCAL_NLP_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
        }
    }
    
    # Try to load from file
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                    file_config = yaml.safe_load(f)
                else:
                    file_config = json.load(f)
                
                # Deep merge with defaults
                config = deep_merge(config, file_config)
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
    
    # Override with base_config if provided
    if base_config:
        config = deep_merge(config, base_config)
    
    # Ensure paths exist
    ensure_paths(config, consciousness_id)
    
    return config


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries"""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def ensure_paths(config: Dict, consciousness_id: str):
    """Ensure all configured paths exist"""
    # Vector store path
    if 'vector_store' in config.get('storage', {}) and config['storage']['vector_store'].get('type') == 'chromadb':
        path = Path(config['storage']['vector_store']['path'])
        path.mkdir(parents=True, exist_ok=True)
    
    # Relational DB path
    if 'relational_db' in config.get('storage', {}):
        path = Path(config['storage']['relational_db']['path']).parent
        path.mkdir(parents=True, exist_ok=True)
    
    # Blob storage path
    if 'blob_storage' in config.get('storage', {}) and config['storage']['blob_storage'].get('type') == 'filesystem':
        path = Path(config['storage']['blob_storage']['path'])
        path.mkdir(parents=True, exist_ok=True)
    
    # Audit path
    if 'audit' in config and config['audit'].get('backend') == 'sqlite':
        path = Path(config['audit']['path']).parent
        path.mkdir(parents=True, exist_ok=True)


def validate_config(config: Dict) -> List[str]:
    """Validate configuration and return list of issues"""
    issues = []
    
    # Check required fields
    if 'storage' not in config:
        issues.append("Missing 'storage' configuration")
    
    # Check storage backends
    storage = config.get('storage', {})
    if not any(k in storage for k in ['vector_store', 'relational_db']):
        issues.append("At least one storage backend must be configured")
    
    # Check memory size limits
    policies = config.get('policies', {})
    max_size = policies.get('max_memory_size', 0)
    if max_size < 1024:  # Less than 1KB
        issues.append(f"max_memory_size too small: {max_size}")
    
    # Check transformation config if enabled
    transform = config.get('transformation', {})
    if transform.get('enable_lora_distillation') and not transform.get('model_name'):
        issues.append("LoRA distillation enabled but no model_name specified")
    
    return issues


def get_development_config(consciousness_id: str) -> Dict[str, Any]:
    """Get development/testing configuration"""
    return {
        "storage": {
            "vector_store": {
                "type": "chromadb",
                "persistent": False,  # In-memory for testing
                "path": f"/tmp/test_consciousness_{consciousness_id}/vector"
            },
            "relational_db": {
                "type": "sqlite",
                "path": ":memory:"  # In-memory database
            },
            "blob_storage": {
                "type": "filesystem",
                "path": f"/tmp/test_consciousness_{consciousness_id}/blobs"
            }
        },
        "policies": {
            "default_ttl": 3600,  # 1 hour for testing
            "max_memory_size": 1024 * 1024,  # 1MB for testing
            "access_control_model": "permissive",
            "enable_pii_detection": False,  # Faster for testing
            "auto_redact": False
        },
        "transformation": {
            "enable_kv_cache": False,  # Disable for testing
            "enable_lora_distillation": False
        },
        "optimization": {
            "hot_memory_threshold": 2,  # Lower threshold for testing
            "cache_size_mb": 64  # Smaller cache for testing
        }
    }


def get_production_config(consciousness_id: str) -> Dict[str, Any]:
    """Get production-optimized configuration"""
    return get_memory_config(consciousness_id, {
        "storage": {
            "vector_store": {
                "persistent": True,
                "embedding_model": os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002'),
                "embedding_dimension": 1536
            },
            "blob_storage": {
                "type": "s3" if os.getenv('S3_BUCKET') else "filesystem"
            }
        },
        "policies": {
            "strict_mode": True,
            "enable_pii_detection": True,
            "auto_redact": True
        },
        "audit": {
            "backend": "elasticsearch" if os.getenv('ELASTICSEARCH_URL') else "sqlite"
        },
        "transformation": {
            "device": "cuda" if os.getenv('CUDA_VISIBLE_DEVICES') else "cpu"
        },
        "optimization": {
            "cache_size_mb": 2048,
            "enable_compression": True
        }
    })