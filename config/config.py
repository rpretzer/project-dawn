"""
Configuration Management

Provides YAML-based configuration with environment variable overrides.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logging.warning("PyYAML not available. YAML config files will not be supported.")

from data_paths import data_root

logger = logging.getLogger(__name__)


class Config:
    """
    Configuration manager for Project Dawn
    
    Loads configuration from YAML file with environment variable overrides.
    """
    
    def __init__(self, config_data: Optional[Dict[str, Any]] = None):
        """
        Initialize configuration
        
        Args:
            config_data: Optional dictionary with configuration data
        """
        # Default configuration
        default_data_dir = str(data_root())
        default_vault_dir = str(data_root() / "vault")
        default_logs_dir = str(data_root() / "logs")
        
        self.node = {
            "identity_path": os.path.expanduser(f"{default_vault_dir}/node_identity.key"),
            "address": os.getenv("PROJECT_DAWN_ADDRESS", "ws://0.0.0.0:8000"),
            "data_root": os.getenv("PROJECT_DAWN_DATA_ROOT", default_data_dir),
        }
        
        self.security = {
            "trust_level_default": os.getenv("PROJECT_DAWN_TRUST_LEVEL", "UNKNOWN"),
            "reject_unknown": os.getenv("PROJECT_DAWN_REJECT_UNKNOWN", "false").lower() == "true",
            "audit_log_path": os.path.expanduser(f"{default_vault_dir}/audit.log"),
        }
        
        self.resilience = {
            "rate_limit": {
                "max_requests": int(os.getenv("PROJECT_DAWN_RATE_LIMIT_MAX", "100")),
                "time_window": float(os.getenv("PROJECT_DAWN_RATE_LIMIT_WINDOW", "60.0")),
            },
            "circuit_breaker": {
                "failure_threshold": int(os.getenv("PROJECT_DAWN_CB_THRESHOLD", "5")),
                "timeout": float(os.getenv("PROJECT_DAWN_CB_TIMEOUT", "60.0")),
            },
        }
        
        self.logging = {
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "format": os.getenv("LOG_FORMAT", "text"),
            "file": os.getenv("PROJECT_DAWN_LOG_FILE", os.path.expanduser(f"{default_logs_dir}/dawn.log")),
        }
        
        self.observability = {
            "metrics_port": int(os.getenv("PROJECT_DAWN_METRICS_PORT", "9090")),
            "enable_tracing": os.getenv("PROJECT_DAWN_ENABLE_TRACING", "false").lower() == "true",
        }
        
        # Override with provided config data
        if config_data:
            self._merge_config(config_data)
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        logger.debug("Config initialized")
    
    def _merge_config(self, config_data: Dict[str, Any]) -> None:
        """Merge configuration data into defaults"""
        def merge_dict(base: Dict, override: Dict) -> Dict:
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result
        
        if "node" in config_data:
            self.node = merge_dict(self.node, config_data["node"])
        if "security" in config_data:
            self.security = merge_dict(self.security, config_data["security"])
        if "resilience" in config_data:
            self.resilience = merge_dict(self.resilience, config_data["resilience"])
        if "logging" in config_data:
            self.logging = merge_dict(self.logging, config_data["logging"])
        if "observability" in config_data:
            self.observability = merge_dict(self.observability, config_data["observability"])
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides"""
        # Node config
        if os.getenv("PROJECT_DAWN_HOST"):
            host = os.getenv("PROJECT_DAWN_HOST")
            port = os.getenv("PROJECT_DAWN_WS_PORT", "8000")
            self.node["address"] = f"ws://{host}:{port}"
        
        # Security config
        if os.getenv("PROJECT_DAWN_TRUST_LEVEL"):
            self.security["trust_level_default"] = os.getenv("PROJECT_DAWN_TRUST_LEVEL")
        if os.getenv("PROJECT_DAWN_REJECT_UNKNOWN"):
            self.security["reject_unknown"] = os.getenv("PROJECT_DAWN_REJECT_UNKNOWN").lower() == "true"
        
        # Logging config
        if os.getenv("LOG_LEVEL"):
            self.logging["level"] = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_FORMAT"):
            self.logging["format"] = os.getenv("LOG_FORMAT")
        
        # Observability config
        if os.getenv("PROJECT_DAWN_METRICS_PORT"):
            self.observability["metrics_port"] = int(os.getenv("PROJECT_DAWN_METRICS_PORT"))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "node": self.node,
            "security": self.security,
            "resilience": self.resilience,
            "logging": self.logging,
            "observability": self.observability,
        }
    
    def validate(self) -> bool:
        """
        Validate configuration
        
        Returns:
            True if valid
        """
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging["level"].upper() not in valid_levels:
            logger.warning(f"Invalid log level: {self.logging['level']}, using INFO")
            self.logging["level"] = "INFO"
        
        # Validate log format
        if self.logging["format"] not in ["text", "json"]:
            logger.warning(f"Invalid log format: {self.logging['format']}, using text")
            self.logging["format"] = "text"
        
        # Validate trust level
        valid_trust_levels = ["UNTRUSTED", "UNKNOWN", "VERIFIED", "TRUSTED", "BOOTSTRAP"]
        if self.security["trust_level_default"].upper() not in valid_trust_levels:
            logger.warning(f"Invalid trust level: {self.security['trust_level_default']}, using UNKNOWN")
            self.security["trust_level_default"] = "UNKNOWN"
        
        # Validate ports
        if not (1 <= self.observability["metrics_port"] <= 65535):
            logger.warning(f"Invalid metrics port: {self.observability['metrics_port']}, using 9090")
            self.observability["metrics_port"] = 9090
        
        return True


# Global config instance
_config: Optional[Config] = None


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from file
    
    Args:
        config_path: Path to config file (default: data_root/config.yaml)
        
    Returns:
        Config instance
    """
    global _config
    
    if config_path is None:
        config_path = data_root() / "config.yaml"
    
    config_data = None
    
    # Try to load from YAML file if available
    if config_path.exists() and YAML_AVAILABLE:
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                config_data = yaml.safe_load(handle) or {}
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    # Create config instance
    _config = Config(config_data)
    _config.validate()
    
    return _config


def save_config(config: Config, config_path: Optional[Path] = None) -> None:
    """
    Save configuration to file
    
    Args:
        config: Config instance
        config_path: Path to save config file (default: data_root/config.yaml)
    """
    if not YAML_AVAILABLE:
        logger.error("PyYAML not available, cannot save YAML config")
        return
    
    if config_path is None:
        config_path = data_root() / "config.yaml"
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(config_path, "w", encoding="utf-8") as handle:
            yaml.dump(config.to_dict(), handle, default_flow_style=False, sort_keys=False)
        logger.info(f"Saved configuration to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save config to {config_path}: {e}")


def get_config() -> Config:
    """
    Get global configuration instance
    
    Returns:
        Config instance (loads if not already loaded)
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config) -> None:
    """Set global configuration instance"""
    global _config
    _config = config
