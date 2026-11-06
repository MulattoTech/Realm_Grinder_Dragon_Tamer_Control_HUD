"""Selected-path prerequisite execution using the one shared transaction owner."""
from pathlib import Path
import time
from src.action_verification import ActionLock,upgrade_owned,fresh_transition
from src.atomic_store import write_json
from src.semantic_ui import SemanticUI,purchase_delta
from src.strategy_rules import RoutePlanner,selected_route
from src.runtime_safety import input_allowed

ALIASES={'Fairy Trade Treaty':'Fairies Trade Treaty','Goblin Trade Treaty':'Goblins Trade Treaty',
         'Druid Trade Treaty':'Druids Trade Treaty','Demon Trade Treaty':'Demons Trade Treaty',
         'Angel Trade Treaty':'Angels Trade Treaty','Titan Trade Treaty':'Titans Trade Treaty'}
GOBLIN_BANK_ID=412
SUPPORTED_4322_SWF='7d8cfb3d967e8cc80971885d45e333c373482bcf5024b1dba59ca5497fc4d49b'

def catalog_entry(catalog,name):
    return catalog.get(name) or catalog.get(ALIASES.get(name,''),{})


def template_progress(before,after,manifest):
    ids=manifest['required_upgrade_ids'];spells=manifest.get('merc_spells',[])
    old={identifier for identifier in ids if upgrade_owned(before,identifier)}
    new={identifier for identifier in ids if upgrade_owned(after,identifier)}
    a=before.get('raw_data',{});b=after.get('raw_data',{})
    old_spells={a.get('mercSpell1'),a.get('mercSpell2')}&set(spells)
    new_spells={b.get('mercSpell1'),b.get('mercSpell2')}&set(spells)
    return {'progressed':bool(new-old or new_spells-old_spells),
            'complete':len(new)==len(ids) and len(new_spells)==len(set(spells)),
            'upgrades_owned':len(new),'upgrade_total':len(ids),'spells_selected':len(new_spells),
            'spell_total':len(set(spells)),'new_upgrade_ids':sorted(new-old)}


class RouteExecutor:
    def __init__(self,actions):
        self.actions=actions
        self.planner=RoutePlanner()

    def plan(self,state=None):
        from src.config import load_config
        selection=load_config().get('selected_path','Automatic')
        state=state or self.actions.read()
        catalog=self.actions.load('upgrade_catalog.json')
        for alias,name in ALIASES.items():
            if name in catalog:catalog.setdefault(alias,catalog[name])
        step=self.planner.next_step(state,selection,catalog)
        if step['action']=='deploy_build':
            manifest=self.actions.manifest(step['recommendation'])
            if manifest.get('verified') and manifest.get('required_upgrade_ids'):
                progress=template_progress(state,state,manifest)
                if progress['complete']:
                    step.update(action='maintain_faction',reason='Requested upgrade and spell selections are owned; maintain production',build_verified=True)
        step['selected_path']=selection
        step['observed_at']=time.time()
        write_json(self.actions.state_dir/'selected_route.json',step)
        return step

    def purchase_named(self,step):
        name=step['target'];before=self.actions.read()
        catalog=self.actions.load('upgrade_catalog.json');known=catalog_entry(catalog,name)
        if known.get('id') is not None and upgrade_owned(before,known['id']):
            return {'success':True,'status':'VERIFIED','action':'ALREADY_OWNED','message':name+' is already purchased'}
        cancelled=lambda:not input_allowed(self.actions.window)
        ui=SemanticUI(self.actions.window,cancelled)
        resolved=name if name in ui.registry else ALIASES.get(name,name)
        holder={}
        def precondition(state):
            if known.get('save_version') not in (None,state['raw_data'].get('saveVersion')):return False
            target=ui.find_named(resolved)
            if target is None:return False
            holder['target']=target
            return True
        def verify(old,new):
            proof=purchase_delta(old,new,known,step.get('expect',{}))
            holder['proof']=proof
            return fresh_transition(old,new) and proof['verified']
        result=self.actions.runner.run('PURCHASE_'+name,precondition,
            lambda:ui.click_target(holder['target']),verify,allow_no_effect=True)
        if result['success']:
            proof=holder['proof'];after=self.actions.read()
            evidence={'name':name,'target':holder['target'],'proof':proof,'timestamp':time.time(),
                      'save_version':after['raw_data']['saveVersion'],'sources':step.get('sources',[]),
                      'before_fingerprint':before.get('save_fingerprint'),'after_fingerprint':after.get('save_fingerprint')}
            filename='purchase-'+''.join(ch if ch.isalnum() else '-' for ch in name.lower())+'.json'
            write_json(self.actions.state_dir/filename,evidence)
            if proof.get('learned_id') is not None and not known:
                catalog[name]={'id':proof['learned_id'],'save_version':after['raw_data']['saveVersion'],
                    'verification':'normal_single_target_save_delta','evidence':filename,'sources':step.get('sources',[])}
                write_json(self.actions.state_dir/'upgrade_catalog.json',catalog)
            result['message']=name+': purchase and game-state change verified'
        elif result['status']=='BLOCKED':
            result['message']=name+': target unavailable, obscured, unaffordable, or input paused; no purchase claimed'
        return result

    def collect(self,step=None):
        if not input_allowed(self.actions.window):
            return {'success':False,'status':'BLOCKED','action':'PAUSED','message':'Setup is paused or the game window/session is not eligible'}
        before=self.actions.read()
        if before.get('telemetry',{}).get('consequential_actions_allowed') is not True:
            return {'success':False,'status':'BLOCKED','action':'OBSERVATION_UNTRUSTED',
                    'message':'Waiting for a fresh save from the supported running game; no input sent'}
        ui=SemanticUI(self.actions.window,lambda:not input_allowed(self.actions.window))
        from src.config import load_config
        config=load_config()
        with ActionLock(self.actions.state_dir):
            # Once gem power is active, ordinary buildings start the production loop.
            if config.get('auto_click_realm',True):
                for _ in range(5):ui.click_control('realm')
            if config.get('auto_buy_buildings',True):ui.click_control('buy_all_buildings')
            if before.get('alignment',0) and config.get('auto_buy_upgrades',True):ui.click_control('buy_all_upgrades')
            from src.spell_policy import plan_spells
            from src.config import load_config
            policy=plan_spells(self.actions.read())
            write_json(self.actions.state_dir/'spell_plan.json',dict(policy,timestamp=time.time()))
            if config.get('auto_spells',True) and config.get('auto_cast_spells',True):
                for cast in policy['casts']:
                    if not input_allowed(self.actions.window):break
                    self.actions.window.press_key(cast['key'],delay_after=.1)
        deadline=time.monotonic()+8.0
        after=before
        identity=tuple(before.get('telemetry',{}).get(k) for k in ('pid','process_start_time'))
        while True:
            try:
                after=self.actions.read()
            except (OSError,ValueError):
                after=before
            if tuple(after.get('telemetry',{}).get(k) for k in ('pid','process_start_time')) != identity:
                break
            if fresh_transition(before,after) and after.get('coins_this_game',0)>before.get('coins_this_game',0):
                break
            if time.monotonic()>=deadline:
                break
            time.sleep(.25)
        observed=(tuple(after.get('telemetry',{}).get(k) for k in ('pid','process_start_time')) == identity
                  and fresh_transition(before,after)
                  and after.get('coins_this_game',0)>before.get('coins_this_game',0))
        return {'success':observed,'status':'VERIFIED' if observed else 'OBSERVING',
                'action':'COLLECT_RESOURCES',
                'message':('Fresh save showed increased run coins during collection window' if observed else
                           'Collection input sent; no fresh save with increased run coins observed yet'),
                'before':{'coins_this_game':before.get('coins_this_game'),'save_fingerprint':before.get('save_fingerprint')},
                'after':{'coins_this_game':after.get('coins_this_game'),'save_fingerprint':after.get('save_fingerprint')},
                'target_coins':(step or {}).get('target_coins')}

    def run_once(self):
        step=self.plan();action=step['action']
        if action=='purchase_named':return self.purchase_named(step)
        if action=='collect_coins':return self.collect(step)
        if action=='deploy_build':
            current=self.actions.read()
            faction=current.get('faction')
            if type(faction) is not int or faction not in (*range(9),11):
                return {'success':False,'status':'BLOCKED','action':'FACTION_UNVERIFIED',
                        'message':'Faction is not verified; no build or collection input sent'}
            if faction!=11:
                identity=current.get('game_identity',{})
                if (faction==3 and identity.get('supported') is True and
                        identity.get('swf_sha256')==SUPPORTED_4322_SWF and
                        identity.get('save_version')==58 and current.get('raw_data',{}).get('saveVersion')==58 and
                        not upgrade_owned(current,GOBLIN_BANK_ID)):
                    result=self.collect(step)
                    after=self.actions.read()
                    old_process=tuple(current.get('telemetry',{}).get(k) for k in ('pid','process_start_time'))
                    new_process=tuple(after.get('telemetry',{}).get(k) for k in ('pid','process_start_time'))
                    same_process=all(value is not None for value in old_process) and old_process==new_process
                    if upgrade_owned(after,GOBLIN_BANK_ID):
                        if not same_process or not fresh_transition(current,after):
                            (self.actions.state_dir/'STOP').write_text(
                                'Goblin Bank ownership observed without a fresh same-process transition',
                                encoding='utf-8')
                            return {'success':False,'status':'UNCERTAIN','action':'GOBLIN_BANK_OWNERSHIP_UNCERTAIN',
                                    'message':'Goblin Bank ID 412 is present, but its fresh same-process ownership transition is unproven'}
                        return {'success':True,'status':'VERIFIED','action':'GOBLIN_BANK_PURCHASED',
                                'upgrade_id':GOBLIN_BANK_ID,'before_fingerprint':current.get('save_fingerprint'),
                                'after_fingerprint':after.get('save_fingerprint'),
                                'message':'Goblin Bank ID 412 became owned in a fresh save from the same game process'}
                    if result.get('status') in ('BLOCKED','UNCERTAIN'):
                        return result
                    result.update(action='PREPARE_GOBLIN_BANK',upgrade_id=GOBLIN_BANK_ID,
                        message='Goblin Bank ID 412 is not owned; continue ordinary production until the save confirms it')
                    return result
                # Non-Mercenary template deployment uses its Research UI path;
                # unsupported factions remain explicitly blocked there.
                return self.deploy_template(step['template'])
            result=self.actions.deploy_template(step['template'])
            # A partial build can still make ordinary production progress.
            if not result.get('build_verified') and input_allowed(self.actions.window):
                self.collect()
            return result
        if action=='maintain_faction':return self.collect(step)
        return {'success':False,'status':'BLOCKED','action':action.upper(),'message':step['reason'],'sources':step['sources']}


    def deploy_template(self,template):
        from src.build_catalog import compile_template,load_reference_ids
        state=self.actions.read()
        manifest=compile_template(template,load_reference_ids(),state['raw_data']['saveVersion'],state.get('game_identity'))
        if not manifest['verified']:
            return {'success':False,'status':'BLOCKED','action':'UNKNOWN_TEMPLATE_TOKEN',
                    'message':'Unresolved template selections: '+', '.join(manifest['unresolved_tokens'])}
        existing=template_progress(state,state,manifest)
        if existing['complete']:
            return {'success':True,'status':'VERIFIED','action':'BUILD_SELECTIONS_OWNED',
                    'message':'All requested upgrade and spell selections are already owned','build_verified':True}
        if state['faction']!=11:
            if state['faction']!=3 or state.get('game_identity',{}).get('swf_sha256')!=SUPPORTED_4322_SWF:
                return {'success':False,'status':'BLOCKED','action':'RESEARCH_UI_NOT_CALIBRATED',
                        'message':'Research selections are known, but this faction needs its Research interface calibrated'}
            ui=SemanticUI(self.actions.window,lambda:not input_allowed(self.actions.window))
            observed={}
            def dispatch():ui.enter_research_template(template)
            def verify(before,after):
                progress=template_progress(before,after,manifest);observed.update(progress)
                return fresh_transition(before,after) and progress['progressed']
            result=self.actions.runner.run('GOBLIN_RESEARCH_TEMPLATE',
                lambda current:current.get('faction')==3 and
                    current.get('game_identity',{}).get('swf_sha256')==manifest['swf_sha256'] and
                    current['raw_data'].get('saveVersion')==manifest['save_version'] and
                    upgrade_owned(current,GOBLIN_BANK_ID),dispatch,verify,allow_no_effect=True)
            result['build_verified']=bool(observed.get('complete'))
            if result['success']:
                result.update(action='BUILD_COMPLETE' if observed['complete'] else 'BUILD_PARTIAL',
                    message=f"Verified research selections: {observed['upgrades_owned']}/{observed['upgrade_total']}; " +
                        ('selections complete' if observed['complete'] else 'continuing prerequisites and resource production'),
                    progress=observed)
            write_json(self.actions.state_dir/'template_application.json',dict(result,template=template,manifest=manifest,timestamp=time.time()))
            return result
        ui=SemanticUI(self.actions.window,lambda:not input_allowed(self.actions.window))
        observed={}
        def verify(before,after):
            progress=template_progress(before,after,manifest);observed.update(progress)
            return fresh_transition(before,after) and progress['progressed']
        result=self.actions.runner.run('MERCENARY_TEMPLATE',
            lambda current:current['faction']==11 and current['raw_data']['saveVersion']==manifest['save_version'],
            lambda:ui.enter_mercenary_template(template),verify,allow_no_effect=True)
        result['build_verified']=bool(observed.get('complete'))
        if result['success']:
            result.update(action='BUILD_COMPLETE' if observed['complete'] else 'BUILD_PARTIAL',
                message=f"Verified template: {observed['upgrades_owned']}/{observed['upgrade_total']} upgrades, "
                        f"{observed['spells_selected']}/{observed['spell_total']} spells; "
                        +('selections complete' if observed['complete'] else 'continuing prerequisites and resource production'),
                progress=observed)
        write_json(self.actions.state_dir/'template_application.json',dict(result,template=template,manifest=manifest,timestamp=time.time()))
        return result
