"""Configuration management for the fraud detection service."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class DormancyConfig:
    """Dormancy detection settings."""
    threshold_days: int = 180


@dataclass
class VelocityConfig:
    """Velocity spike detection settings."""
    window_minutes: int = 60
    threshold_count: int = 3


@dataclass
class RiskWeightsConfig:
    """Risk scoring weights (must sum to 1.0)."""
    dormancy: float = 0.30
    amount_anomaly: float = 0.25
    type_anomaly: float = 0.18
    velocity: float = 0.12
    location_anomaly: float = 0.15
    
    def __post_init__(self):
        total = (
            self.dormancy + 
            self.amount_anomaly + 
            self.type_anomaly + 
            self.velocity + 
            self.location_anomaly
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Risk weights must sum to 1.0, got {total}")


@dataclass
class RiskLevelsConfig:
    """Risk level classification thresholds."""
    low_max: int = 25
    medium_max: int = 50
    high_max: int = 75


@dataclass
class LocationsConfig:
    """Geographic location classifications."""
    domestic: list[str] = field(default_factory=lambda: [
        "Singapore", "Jakarta", "Bangkok", "Kuala Lumpur", "Manila",
        "Ho Chi Minh City", "Hanoi", "Bali", "Phuket", "Penang",
        "Cebu", "Chiang Mai", "Yangon", "Phnom Penh", "Brunei"
    ])
    international: list[str] = field(default_factory=lambda: [
        "London", "New York", "Dubai", "Tokyo", "Sydney",
        "Moscow", "Lagos", "Sao Paulo", "Paris", "Berlin",
        "Toronto", "Mumbai", "Beijing", "Shanghai", "Seoul"
    ])


@dataclass
class FraudDetectionConfig:
    """Main configuration class for the fraud detection service."""
    dormancy: DormancyConfig = field(default_factory=DormancyConfig)
    velocity: VelocityConfig = field(default_factory=VelocityConfig)
    risk_weights: RiskWeightsConfig = field(default_factory=RiskWeightsConfig)
    risk_levels: RiskLevelsConfig = field(default_factory=RiskLevelsConfig)
    locations: LocationsConfig = field(default_factory=LocationsConfig)
    
    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "FraudDetectionConfig":
        """Load configuration from a YAML file."""
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "FraudDetectionConfig":
        """Create configuration from a dictionary."""
        config = cls()
        
        if "dormancy" in data:
            config.dormancy = DormancyConfig(**data["dormancy"])
        
        if "velocity" in data:
            config.velocity = VelocityConfig(**data["velocity"])
        
        if "risk_weights" in data:
            config.risk_weights = RiskWeightsConfig(**data["risk_weights"])
        
        if "risk_levels" in data:
            config.risk_levels = RiskLevelsConfig(**data["risk_levels"])
        
        if "locations" in data:
            config.locations = LocationsConfig(**data["locations"])
        
        return config


# Global configuration instance
_config: Optional[FraudDetectionConfig] = None


def get_config() -> FraudDetectionConfig:
    """
    Get the current configuration.
    
    Returns the global config instance. If not loaded, returns default config.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config(config_path: Optional[str | Path] = None) -> FraudDetectionConfig:
    """
    Load configuration from file or use defaults.
    
    Looks for config in the following order:
    1. Explicitly provided path
    2. FRAUD_DETECTION_CONFIG environment variable
    3. config/config.yaml in the project root
    4. config/default_config.yaml in the project root
    5. Default values
    """
    global _config
    
    if config_path:
        _config = FraudDetectionConfig.from_yaml(config_path)
        return _config
    
    # Check environment variable
    env_path = os.environ.get("FRAUD_DETECTION_CONFIG")
    if env_path and Path(env_path).exists():
        _config = FraudDetectionConfig.from_yaml(env_path)
        return _config
    
    # Check for config files in project root
    project_root = Path(__file__).parent.parent
    
    custom_config = project_root / "config" / "config.yaml"
    if custom_config.exists():
        _config = FraudDetectionConfig.from_yaml(custom_config)
        return _config
    
    default_config = project_root / "config" / "default_config.yaml"
    if default_config.exists():
        _config = FraudDetectionConfig.from_yaml(default_config)
        return _config
    
    # Fall back to hardcoded defaults
    _config = FraudDetectionConfig()
    return _config


def reload_config(config_path: Optional[str | Path] = None) -> FraudDetectionConfig:
    """Force reload of the configuration."""
    global _config
    _config = None
    return load_config(config_path)
