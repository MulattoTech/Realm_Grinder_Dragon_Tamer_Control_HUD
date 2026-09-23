"""Forecasts must match cited mechanics and must not invent progression rates."""
import pytest
from src.forecaster import MonteCarloArtifactForecaster,MilestoneForecaster


def test_egg_forecast_requires_reincarnation_not_just_excavations():
    result=MonteCarloArtifactForecaster.calculate_egg_probabilities(1600,current_r=24)
    assert not result['is_eligible'] and result['current_dig_drop_chance']==0


def test_egg_forecast_uses_documented_fixed_probability():
    result=MonteCarloArtifactForecaster.calculate_egg_probabilities(1500,current_r=46)
    assert result['is_eligible'] and result['current_dig_drop_chance']==pytest.approx(.02)
    assert result['p50_digs_needed']==35 and result['p90_digs_needed']==114 and result['p99_digs_needed']==228
    assert result['assumption'] and result['source_url']


def test_omitted_reincarnation_does_not_claim_eligibility():
    assert not MonteCarloArtifactForecaster.calculate_egg_probabilities(5000)['is_eligible']


def test_legacy_timeline_no_longer_assumes_two_hours_per_reincarnation():
    result=MilestoneForecaster.forecast_dragon_timeline(24,1e68,1e100,999999,False,{})
    assert result['r46_eta_hours'] is None
    assert result['total_estimated_hours'] is None
    assert result['target_completion_date'] is None
    assert result['hellfire_hours_remaining'] is None
