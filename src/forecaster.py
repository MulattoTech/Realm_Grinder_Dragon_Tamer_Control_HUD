"""Source-attributed probability estimates; timeline inference requires observations."""
import math

class MonteCarloArtifactForecaster:
    """Legacy public name; the fixed-probability model is evaluated analytically."""
    @staticmethod
    def calculate_egg_probabilities(current_excavations,target_confidence=.95,*,current_r=None):
        if not 0<target_confidence<1:raise ValueError('Confidence must be between zero and one')
        eligible=current_r is not None and current_r>=42 and current_excavations>=1500
        chance=.02
        quantile=lambda confidence:math.ceil(math.log1p(-confidence)/math.log1p(-chance))
        return {'current_excavations':current_excavations,'current_reincarnation':current_r,
                'current_dig_drop_chance':chance if eligible else 0.0,
                'current_dig_drop_percent':chance*100 if eligible else 0.0,
                'p50_digs_needed':quantile(.5),'p90_digs_needed':quantile(.9),'p99_digs_needed':quantile(.99),
                'target_confidence_digs':quantile(target_confidence),'is_eligible':eligible,
                'source_url':'http://musicfamily.org/realm/DragonFaction/',
                'assumption':'4.3.22 model: R42+ and 1500 excavations; conditional 2% chance per attempt. Not a guarantee, live eligibility check, or RNG-seed prediction.'}

class MilestoneForecaster:
    """Compatibility API. Fixed hours-per-R and pre-Hatch Hellfire credit were removed."""
    @staticmethod
    def forecast_dragon_timeline(current_r,current_gems,current_coins,hellfire_time,has_egg,stage_timestamps):
        return {'current_r':current_r,'reincarnations_remaining':max(0,48-current_r),
                'r46_eta_hours':None,'r46_target_date':None,'hellfire_hours_remaining':None,
                'total_estimated_hours':None,'target_completion_date':None,
                'formatted_eta':'Not established - use measured same-run ETA and observed quest transitions',
                'status':'INSUFFICIENT_OBSERVATIONS'}
