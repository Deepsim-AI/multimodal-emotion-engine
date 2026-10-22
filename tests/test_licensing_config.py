"""R2, R3 — LicensingConfig + TrialConfig tests (TASK_MEE_015)."""
from __future__ import annotations

import os
import pytest

from mee.licensing.config import LicensingConfig, TrialConfig, DEFAULT_LICENSE_SERVER


def test_default_server_url(monkeypatch):
    monkeypatch.delenv("MEE_LICENSE_SERVER", raising=False)
    cfg = LicensingConfig()
    assert cfg.server_url == DEFAULT_LICENSE_SERVER


def test_server_url_env_override(monkeypatch):
    monkeypatch.setenv("MEE_LICENSE_SERVER", "http://localhost:9999")
    cfg = LicensingConfig()
    assert cfg.server_url == "http://localhost:9999"


def test_license_key_env_override(monkeypatch):
    monkeypatch.setenv("MEE_LICENSE_KEY", "KG-ABCDEF12-34567890-12345678-90ABCDEF")
    cfg = LicensingConfig()
    assert cfg.license_key == "KG-ABCDEF12-34567890-12345678-90ABCDEF"


def test_license_key_none_when_unset(monkeypatch):
    monkeypatch.delenv("MEE_LICENSE_KEY", raising=False)
    cfg = LicensingConfig()
    assert cfg.license_key is None


def test_home_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MEE_HOME", str(tmp_path / "custom"))
    cfg = LicensingConfig()
    assert cfg.home_dir_resolved == tmp_path / "custom"


def test_state_dir_created(tmp_path, monkeypatch):
    monkeypatch.setenv("MEE_HOME", str(tmp_path))
    cfg = LicensingConfig()
    sd = cfg.state_dir
    assert sd.is_dir()
    assert sd == tmp_path / "licenses"


def test_explicit_config_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MEE_LICENSE_SERVER", "http://should-not-be-used")
    cfg = LicensingConfig(server_url="http://explicit:1234", home_dir=tmp_path)
    assert cfg.server_url == "http://explicit:1234"
    assert cfg.home_dir_resolved == tmp_path


# ------------------------------------------------------------------
# R31, R32 — TrialConfig
# ------------------------------------------------------------------

def test_trial_days_default(monkeypatch):
    monkeypatch.delenv("MEE_TRIAL_DAYS", raising=False)
    tc = TrialConfig()
    assert tc.trial_days == 14


def test_trial_days_env_override(monkeypatch):
    monkeypatch.setenv("MEE_TRIAL_DAYS", "30")
    tc = TrialConfig()
    assert tc.trial_days == 30


def test_get_trial_days_precedence_feature_over_env(monkeypatch):
    monkeypatch.setenv("MEE_TRIAL_DAYS", "21")
    tc = TrialConfig()
    # Plan feature wins (R31 precedence level 1).
    assert tc.get_trial_days(features={"trial_period_days": "45"}) == 45


def test_get_trial_days_env_over_default(monkeypatch):
    monkeypatch.setenv("MEE_TRIAL_DAYS", "21")
    tc = TrialConfig()
    assert tc.get_trial_days() == 21


def test_get_trial_days_default(monkeypatch):
    monkeypatch.delenv("MEE_TRIAL_DAYS", raising=False)
    tc = TrialConfig()
    assert tc.get_trial_days() == 14


def test_get_trial_days_feature_non_int_falls_back(monkeypatch):
    monkeypatch.setenv("MEE_TRIAL_DAYS", "21")
    tc = TrialConfig()
    assert tc.get_trial_days(features={"trial_period_days": "not-a-number"}) == 21


def test_can_trial_default_true():
    tc = TrialConfig()
    assert tc.can_trial() is True
    assert tc.can_trial(features={}) is True


def test_can_trial_disabled_by_feature():
    tc = TrialConfig()
    assert tc.can_trial(features={"trial_enabled": False}) is False
    assert tc.can_trial(features={"trial_enabled": "false"}) is False


def test_can_trial_enabled_by_feature():
    tc = TrialConfig()
    assert tc.can_trial(features={"trial_enabled": True}) is True
