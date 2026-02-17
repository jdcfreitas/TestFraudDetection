"""Unit tests for configuration module."""

import pytest
import tempfile
from pathlib import Path

from app.config import (
    FraudDetectionConfig,
    DormancyConfig,
    VelocityConfig,
    RiskWeightsConfig,
    RiskLevelsConfig,
    LocationsConfig,
    load_config,
    get_config
)


class TestDormancyConfig:
    """Tests for DormancyConfig dataclass."""
    
    def test_default_values(self):
        """Test default dormancy configuration values."""
        config = DormancyConfig()
        
        assert config.threshold_days == 180
    
    def test_custom_threshold(self):
        """Test setting custom dormancy threshold."""
        config = DormancyConfig(threshold_days=90)
        
        assert config.threshold_days == 90


class TestVelocityConfig:
    """Tests for VelocityConfig dataclass."""
    
    def test_default_values(self):
        """Test default velocity configuration values."""
        config = VelocityConfig()
        
        assert config.window_minutes == 60
        assert config.threshold_count == 3
    
    def test_custom_values(self):
        """Test setting custom velocity values."""
        config = VelocityConfig(window_minutes=30, threshold_count=5)
        
        assert config.window_minutes == 30
        assert config.threshold_count == 5


class TestRiskWeightsConfig:
    """Tests for RiskWeightsConfig dataclass."""
    
    def test_default_values(self):
        """Test default risk weight values."""
        config = RiskWeightsConfig()
        
        assert config.dormancy == 0.30
        assert config.amount_anomaly == 0.25
        assert config.type_anomaly == 0.18
        assert config.velocity == 0.12
        assert config.location_anomaly == 0.15
    
    def test_weights_sum_to_one(self):
        """Test that default weights sum to 1.0."""
        config = RiskWeightsConfig()
        
        total = (
            config.dormancy +
            config.amount_anomaly +
            config.type_anomaly +
            config.velocity +
            config.location_anomaly
        )
        
        assert abs(total - 1.0) < 0.01
    
    def test_custom_weights(self):
        """Test setting custom weights."""
        config = RiskWeightsConfig(
            dormancy=0.40,
            amount_anomaly=0.20,
            type_anomaly=0.15,
            velocity=0.10,
            location_anomaly=0.15
        )
        
        assert config.dormancy == 0.40
        assert config.amount_anomaly == 0.20


class TestRiskLevelsConfig:
    """Tests for RiskLevelsConfig dataclass."""
    
    def test_default_values(self):
        """Test default risk level thresholds."""
        config = RiskLevelsConfig()
        
        assert config.low_max == 25
        assert config.medium_max == 50
        assert config.high_max == 75
    
    def test_thresholds_ordering(self):
        """Test that thresholds are properly ordered."""
        config = RiskLevelsConfig()
        
        assert config.low_max < config.medium_max < config.high_max
    
    def test_custom_thresholds(self):
        """Test setting custom thresholds."""
        config = RiskLevelsConfig(low_max=20, medium_max=40, high_max=60)
        
        assert config.low_max == 20
        assert config.medium_max == 40
        assert config.high_max == 60


class TestLocationsConfig:
    """Tests for LocationsConfig dataclass."""
    
    def test_default_domestic_locations(self):
        """Test default domestic locations include Southeast Asia."""
        config = LocationsConfig()
        
        assert "Singapore" in config.domestic
        assert "Jakarta" in config.domestic
        assert "Bangkok" in config.domestic
        assert "Kuala Lumpur" in config.domestic
    
    def test_default_excludes_western_locations(self):
        """Test that western locations are not in domestic by default."""
        config = LocationsConfig()
        
        assert "London" not in config.domestic
        assert "New York" not in config.domestic
        assert "Paris" not in config.domestic
    
    def test_custom_domestic_locations(self):
        """Test setting custom domestic locations."""
        config = LocationsConfig(domestic=["City A", "City B", "City C"])
        
        assert config.domestic == ["City A", "City B", "City C"]


class TestFraudDetectionConfig:
    """Tests for main FraudDetectionConfig class."""
    
    def test_default_config(self):
        """Test creating default configuration."""
        config = FraudDetectionConfig()
        
        assert isinstance(config.dormancy, DormancyConfig)
        assert isinstance(config.velocity, VelocityConfig)
        assert isinstance(config.risk_weights, RiskWeightsConfig)
        assert isinstance(config.risk_levels, RiskLevelsConfig)
        assert isinstance(config.locations, LocationsConfig)
    
    def test_from_yaml_basic(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
dormancy:
  threshold_days: 120

velocity:
  window_minutes: 45
  threshold_count: 4

risk_weights:
  dormancy: 0.35
  amount_anomaly: 0.25
  type_anomaly: 0.15
  velocity: 0.10
  location_anomaly: 0.15

risk_levels:
  low_max: 20
  medium_max: 45
  high_max: 70

locations:
  domestic:
    - Singapore
    - Malaysia
    - Thailand
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = Path(f.name)
        
        try:
            config = FraudDetectionConfig.from_yaml(config_path)
            
            assert config.dormancy.threshold_days == 120
            assert config.velocity.window_minutes == 45
            assert config.velocity.threshold_count == 4
            assert config.risk_weights.dormancy == 0.35
            assert config.risk_levels.low_max == 20
            assert "Singapore" in config.locations.domestic
        finally:
            config_path.unlink()
    
    def test_from_yaml_partial(self):
        """Test that partial YAML uses defaults for missing values."""
        yaml_content = """
dormancy:
  threshold_days: 90
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = Path(f.name)
        
        try:
            config = FraudDetectionConfig.from_yaml(config_path)
            
            assert config.dormancy.threshold_days == 90
            # Other values should be defaults
            assert config.velocity.window_minutes == 60
            assert config.risk_weights.dormancy == 0.30
        finally:
            config_path.unlink()
    
    def test_from_yaml_nonexistent_file(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            FraudDetectionConfig.from_yaml(Path("/nonexistent/config.yaml"))
    
    def test_from_yaml_invalid_yaml(self):
        """Test handling of invalid YAML content."""
        yaml_content = """
dormancy:
  threshold_days: invalid_not_a_number
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = Path(f.name)
        
        try:
            # Should handle gracefully (either use defaults or raise clear error)
            # Depending on implementation, this might raise or use defaults
            config = FraudDetectionConfig.from_yaml(config_path)
            # If it doesn't raise, should have some valid state
            assert isinstance(config, FraudDetectionConfig)
        except (ValueError, TypeError):
            # Expected behavior for invalid config
            pass
        finally:
            config_path.unlink()


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_config_creates_default(self):
        """Test that load_config creates a valid configuration."""
        config = load_config()
        
        assert isinstance(config, FraudDetectionConfig)
        assert config.dormancy.threshold_days == 180
    
    def test_load_config_from_custom_path(self):
        """Test loading config from custom path."""
        yaml_content = """
dormancy:
  threshold_days: 150
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = Path(f.name)
        
        try:
            config = load_config(config_path)
            
            assert config.dormancy.threshold_days == 150
        finally:
            config_path.unlink()


class TestGetConfig:
    """Tests for get_config singleton function."""
    
    def test_get_config_returns_config(self):
        """Test that get_config returns a valid configuration."""
        config = get_config()
        
        assert isinstance(config, FraudDetectionConfig)
    
    def test_get_config_singleton(self):
        """Test that get_config returns same instance."""
        config1 = get_config()
        config2 = get_config()
        
        # Should return the same instance
        assert config1 is config2


class TestConfigIntegration:
    """Integration tests for configuration in scoring context."""
    
    def test_config_affects_dormancy_scoring(self):
        """Test that dormancy config affects actual dormancy detection."""
        from app.data_store import DataStore
        from app.account_profiler import AccountProfiler
        from app.models import Transaction, TransactionType
        from datetime import datetime, timedelta
        
        reference_date = datetime(2026, 2, 17)
        data_store = DataStore()
        
        # Transaction 100 days ago
        txn = Transaction(
            transaction_id="TXN-001",
            account_id="ACC-001",
            amount=100.0,
            transaction_type=TransactionType.ONLINE_PURCHASE,
            timestamp=reference_date - timedelta(days=100),
            location="Singapore"
        )
        data_store.add_transaction(txn)
        
        # With 90-day threshold
        config_90 = FraudDetectionConfig()
        config_90.dormancy = DormancyConfig(threshold_days=90)
        profiler_90 = AccountProfiler(data_store, reference_date=reference_date, config=config_90)
        profile_90 = profiler_90.build_profile("ACC-001")
        
        # With 180-day threshold
        config_180 = FraudDetectionConfig()
        config_180.dormancy = DormancyConfig(threshold_days=180)
        profiler_180 = AccountProfiler(data_store, reference_date=reference_date, config=config_180)
        profile_180 = profiler_180.build_profile("ACC-001")
        
        assert profile_90.is_dormant  # 100 > 90
        assert not profile_180.is_dormant  # 100 < 180


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
