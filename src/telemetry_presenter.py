"""Pure presentation helpers: never convert unknown measurements into accomplishments."""
import math

def measured(value):
    if value is None or not isinstance(value,(int,float)) or not math.isfinite(value):
        return 'Unknown'
    return f'{value:,.0f}' if float(value).is_integer() else f'{value:,.1f}'

def mana_bar(state):
    """Return a dict ready for HUD mana bar display from live volatile state.

    Returns keys: current, maximum, regen, fill_pct, source_badge, is_live.
    fill_pct is None when either value is unknown.
    """
    current=state.get('mana_current')
    maximum=state.get('mana_max')
    regen=state.get('mana_regeneration')
    provenance=state.get('provenance',{}).get('mana_current',{})
    source=provenance.get('source','')
    is_live=(source=='PROCESS_MEMORY')
    source_badge='MEM' if is_live else ('SAVE' if source=='AIR_SHAREDOBJECT' else 'UNKNOWN')

    fill_pct=None
    if (current is not None and isinstance(current,(int,float)) and math.isfinite(current) and current>=0 and
            maximum is not None and isinstance(maximum,(int,float)) and math.isfinite(maximum) and maximum>0):
        fill_pct=min(100.0,max(0.0,current/maximum*100.0))

    return {
        'current':current,'maximum':maximum,'regen':regen,
        'fill_pct':fill_pct,'source_badge':source_badge,'is_live':is_live,
        'current_str':measured(current),'maximum_str':measured(maximum),
        'regen_str':(f'+{regen:,.1f}' if isinstance(regen,(int,float)) and math.isfinite(regen) else 'Unknown'),
    }

def telemetry_banner(state,build):
    health=state.get('telemetry',{})
    origin=state.get('provenance',{}).get('mana_current',{}).get('source')
    source={'PROCESS_MEMORY':'MEM','AIR_SHAREDOBJECT':'SAVE','DERIVED':'DERIVED'}.get(origin,'UNKNOWN')
    count=len(health.get('verified_fields',[]))
    bar=mana_bar(state)
    regen_str=bar['regen_str']
    return (f"RAM {health.get('memory_provider_health','UNKNOWN')} | {count} verified fields | "
            f"Save {health.get('save_provider_health','UNKNOWN')} ({health.get('save_age_seconds',0):.0f}s old)\n"
            f"Mana {bar['current_str']} [{source}] / {bar['maximum_str']} max | Regen {regen_str} mana/s | "
            f"Fairy assistants {measured(state.get('fairy_assistants'))} | "
            f"Build {'VERIFIED' if build.get('build_verified') else 'UNVERIFIED'}")

_FIELD_LABELS = {
    'game_identity.supported': 'Supported game profile',
    'reincarnation': 'Reincarnation',
    'ascension': 'Ascension',
    'excavations': 'Excavations',
    'dragon_quest_counter': 'Dragon quest counter',
    'faction': 'Current faction',
    'assistants_current': 'Current assistants',
    'fairy_assistants_current': 'Fairy assistants',
    'mana_max': 'Maximum mana',
}


def _rule_field_label(field):
    if field in _FIELD_LABELS:
        return _FIELD_LABELS[field]
    return str(field or 'Required evidence').replace('raw_data.', '').replace('.', ' ')


def _condition_blockers(step):
    blockers = []
    for condition in step.get('conditions', []):
        satisfied = condition.get('satisfied')
        if satisfied is True:
            continue
        label = _rule_field_label(condition.get('field'))
        actual = condition.get('actual')
        expected = condition.get('value')
        if satisfied is None or actual is None:
            blockers.append(f'{label}: UNKNOWN')
        elif condition.get('op') == 'gte':
            blockers.append(f'{label}: {measured(actual)} / {measured(expected)} required')
        else:
            blockers.append(f'{label}: requirement not verified')
    for cost in step.get('costs', []):
        satisfied = cost.get('satisfied')
        if satisfied is True:
            continue
        label = _rule_field_label(cost.get('field'))
        actual = cost.get('actual')
        amount = cost.get('amount')
        if satisfied is None or actual is None or amount is None:
            blockers.append(f'{label}: UNKNOWN')
        else:
            blockers.append(f'{label}: {measured(actual)} / {measured(amount)} required')
    return blockers


def dragon_stage_reference(stage, profile_supported):
    """Render static stage facts only for the matching supported game profile."""
    if profile_supported is not True:
        return 'Requirements: UNKNOWN until the supported game profile is confirmed.'
    parts = []
    req_r = stage.get('req_r')
    parts.append(f'Minimum reincarnation: R{req_r}' if isinstance(req_r, int) and not isinstance(req_r, bool)
                 else 'Minimum reincarnation: UNKNOWN')
    excavation_count = stage.get('req_excavations')
    if excavation_count is not None:
        parts.append(f'Excavations: {measured(excavation_count)}')
    counter = stage.get('time_gate_seconds')
    counter_source = stage.get('time_gate_description', '')
    if counter is not None:
        if isinstance(counter, (int, float)) and 'stat 81' in str(counter_source).casefold():
            parts.append(f'Dragon quest counter (stat 81): at least {measured(counter)}; updater semantics UNKNOWN')
        else:
            parts.append('Dragon quest counter: UNKNOWN')
    faction = stage.get('req_faction')
    if faction is not None:
        parts.append(f'Faction field: {measured(faction)}')
    assistants = stage.get('req_assistants')
    if assistants is not None:
        parts.append(stage.get('assistants_description') or f'Assistants: at least {measured(assistants)}')
    max_mana = stage.get('req_max_mana')
    if max_mana is not None:
        parts.append(stage.get('max_mana_description') or f'Maximum mana: at least {measured(max_mana)}')
    return '; '.join(parts) if parts else 'Requirements: UNKNOWN'


def dragon_goal_presentation(state, plan):
    """Present planner-derived Dragon Tamer steps without inventing readiness.

    The plan supplies stage names, scoped requirements, and condition values.
    Completion is independently bound to the decoded save's trophy 210 record.
    """
    identity = state.get('game_identity') if isinstance(state, dict) else None
    supported = identity.get('supported') if isinstance(identity, dict) else None
    profile_status = ('SUPPORTED' if supported is True else
                      'UNSUPPORTED' if supported is False else 'UNKNOWN')

    raw = state.get('raw_data') if isinstance(state, dict) else None
    trophies = raw.get('trophies') if isinstance(raw, dict) else None
    trophy_owned = None if not isinstance(trophies, dict) else '210' in trophies

    steps = plan.get('steps', []) if isinstance(plan, dict) else []
    milestones = []
    by_name = {}
    for step in steps:
        name = str(step.get('name') or 'Unknown milestone')
        raw_status = step.get('status')
        owned = step.get('owned')
        if name == 'Dragon Tamer':
            status = 'OWNED' if trophy_owned is True else ('UNKNOWN' if trophy_owned is None else 'WAITING')
            blockers = [] if trophy_owned is True else [
                'Trophy 210: UNKNOWN' if trophy_owned is None else 'Trophy 210 not observed in the save'
            ]
        elif profile_status != 'SUPPORTED':
            status = 'UNKNOWN'
            blockers = ['Supported game identity: UNKNOWN' if profile_status == 'UNKNOWN'
                        else 'Game identity is not a supported profile']
        else:
            if owned is True or raw_status == 'OWNED':
                status = 'OWNED'
            elif raw_status in ('READY', 'NEEDS_RESOURCES'):
                status = raw_status
            elif raw_status in ('LOCKED', 'NEEDS_PREREQUISITE'):
                status = 'BLOCKED'
            else:
                status = 'UNKNOWN'
            blockers = _condition_blockers(step)
            counter_conditions = [condition for condition in step.get('conditions', [])
                                  if condition.get('field') == 'dragon_quest_counter']
            if counter_conditions and status != 'OWNED':
                status = 'UNKNOWN'
                condition = counter_conditions[0]
                actual = condition.get('actual')
                threshold = condition.get('value')
                measured_counter = measured(actual) if actual is not None else 'UNKNOWN'
                measured_threshold = measured(threshold) if threshold is not None else 'UNKNOWN'
                blockers = [f'Dragon quest counter: {measured_counter} / {measured_threshold}; updater semantics UNKNOWN']
            if raw_status == 'NEEDS_PREREQUISITE' and not blockers:
                blockers = ['Prerequisites are not yet verified']
            if raw_status == 'UNSUPPORTED_STAGE' and not blockers:
                blockers = ['Game or save profile scope: UNKNOWN/unsupported']
            if not blockers and status == 'UNKNOWN':
                blockers = ['Required evidence: UNKNOWN']
        row = {'name': name, 'status': status, 'blockers': blockers,
               'owned': status == 'OWNED'}
        milestones.append(row)
        by_name[name] = row

    next_action = plan.get('next_action') if isinstance(plan, dict) else None
    target = next_action.get('target') if isinstance(next_action, dict) else None
    next_milestone = target if isinstance(target, str) else None
    if not next_milestone:
        next_milestone = next((row['name'] for row in milestones if not row['owned']), None)

    if trophy_owned is True:
        completion = 'COMPLETE'
        blocker = ''
    elif profile_status != 'SUPPORTED':
        completion = 'UNKNOWN'
        blocker = ('Supported game identity: UNKNOWN' if profile_status == 'UNKNOWN'
                   else 'Game identity is not a supported profile')
    elif trophy_owned is None:
        completion = 'UNKNOWN'
        blocker = 'Trophy 210: UNKNOWN'
    else:
        completion = 'IN_PROGRESS'
        row = by_name.get(next_milestone)
        blocker = '; '.join(row['blockers']) if row and row['blockers'] else (
            f'Next milestone: {next_milestone}' if next_milestone else 'Trophy 210 not observed in the save'
        )

    return {
        'profile_status': profile_status,
        'completion': completion,
        'trophy_210_owned': trophy_owned,
        'next_milestone': next_milestone or 'UNKNOWN',
        'blocker': blocker or 'None',
        'milestones': milestones,
    }
