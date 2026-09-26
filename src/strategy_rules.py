"""Declarative prerequisites and explicit faction-setup routes, grounded in source pages."""
from __future__ import annotations
from src.action_verification import upgrade_owned,trophy_owned
from src.wiki_data import get_recommended_build

SOURCE_UPGRADES='http://musicfamily.org/realm/Upgrades/'
SOURCE_MERC='http://musicfamily.org/realm/MercenaryFaction/'
SOURCE_BUILDS='http://musicfamily.org/realm/MercBuilds/'
SOURCE_TROPHIES='http://musicfamily.org/realm/AllTrophies/'
FACTIONS={'Fairy':(0,1),'Elf':(1,1),'Angel':(2,1),'Goblin':(3,2),'Undead':(4,2),
          'Demon':(5,2),'Titan':(6,3),'Druid':(7,3),'Faceless':(8,3),
          'Good Mercenary':(11,1),'Evil Mercenary':(11,2),'Neutral Mercenary':(11,3)}
PATH_CHOICES=('Automatic',)+tuple(FACTIONS)

def evaluate_condition(condition,state):
    if 'all' in condition:
        values=[evaluate_condition(child,state) for child in condition['all']]
        return False if False in values else None if None in values else True
    if 'any' in condition:
        values=[evaluate_condition(child,state) for child in condition['any']]
        return True if True in values else None if None in values else False
    operation=condition.get('op')
    if operation=='upgrade_owned':return upgrade_owned(state,condition['id'])
    if operation=='trophy_owned':return trophy_owned(state,condition['id'])
    actual=state
    for key in condition.get('field','').split('.'):
        if not isinstance(actual,dict) or key not in actual:return None
        actual=actual[key]
    expected=condition.get('value')
    if actual is None or expected is None:return None
    try:
        if operation=='eq':return actual==expected
        if operation=='ne':return actual!=expected
        if operation=='gte':return actual>=expected
        if operation=='lte':return actual<=expected
        if operation=='gt':return actual>expected
        if operation=='lt':return actual<expected
        if operation=='in':return actual in expected
    except TypeError:return None
    return None

def normalize_faction(name):
    if 'Mercenary' in name:return 'Mercenary'
    return {'Elven':'Elf','Fairy/Dwarf':'Fairy','Goblin/Drow':'Goblin'}.get(name,name)

def _explicit_route(state,selection):
    if selection not in FACTIONS:raise ValueError('Unknown faction path: '+str(selection))
    if 'Mercenary' in selection:
        from src.wiki_data import BUILDS_DATABASE
        rec=dict(BUILDS_DATABASE['R24_MERC_NEUTRAL'])
        rec['faction']=selection
        # Neutral build is not silently used with incompatible Good/Evil spell choices.
        if selection!='Neutral Mercenary':rec['template']='';rec['name']=selection+' (select a compatible template)'
    else:
        candidate=get_recommended_build(state['reincarnation'],state['gems'])
        rec=dict(candidate) if normalize_faction(candidate['faction'])==selection else {
            'name':selection+' faction progression','faction':selection,'bloodline':None,'template':'','notes':'Selected faction; no unverified template is assumed.'}
    return selection,rec

def selected_route(state,selection):
    if selection!='Automatic':return _explicit_route(state,selection)
    recommended=dict(get_recommended_build(state['reincarnation'],state['gems']))
    recommended_name=recommended['faction']
    if recommended_name=='Mercenary':recommended_name='Neutral Mercenary'
    if recommended_name not in FACTIONS:recommended_name=normalize_faction(recommended_name)
    if recommended_name not in FACTIONS:return recommended_name,recommended

    # The recommended build is for the next faction choice. Keep the current
    # run productive when changing to it would require an Abdication first.
    active_name=next((name for name,(faction,alignment) in FACTIONS.items()
                      if state.get('faction')==faction and state.get('alignment')==alignment),None)
    if active_name is not None and active_name!=recommended_name:
        name,active=_explicit_route(state,active_name)
        next_run=dict(recommended)
        next_run.update(faction=recommended_name,alignment=FACTIONS[recommended_name][1])
        active['route_role']='active_run'
        active['next_run_recommendation']=next_run
        return name,active

    recommended['route_role']='active_run'
    return recommended_name,recommended

class RoutePlanner:
    """Return one next prerequisite. No input, resets, or purchases happen in planning."""
    def next_step(self,state,selection='Automatic',catalog=None):
        catalog=catalog or {}
        name,rec=selected_route(state,selection)
        next_run=rec.get('next_run_recommendation')
        def annotate(step):
            step['active_path']=name
            if next_run:step['next_run_recommendation']=next_run
            return step
        if name not in FACTIONS:return annotate(self.step('unsupported_stage',None,'No compiled faction route for this stage',[SOURCE_BUILDS]))
        faction,alignment=FACTIONS[name]
        if state['reincarnation']>=100 or state.get('ascension',0)>=2:
            return annotate(self.step('unsupported_stage',None,'Later-stage alignment/lineage prerequisites need a stage-specific recipe',[SOURCE_MERC]))
        if (state.get('faction',-1) not in (-1,faction) or state.get('alignment',0) not in (0,alignment)):
            return annotate(dict(self.step('needs_abdication',None,'Selected path differs from the active run; a separately verified reset is required',[SOURCE_BUILDS]),automatic_reset=False))
        def owned(item):
            entry=catalog.get(item,{})
            return entry.get('id') is not None and upgrade_owned(state,entry['id'])
        if state.get('gems',0)>0 and not owned('Gem Power'):
            return annotate(self.step('purchase_named','Gem Power','Activate the existing gem production bonus before selecting or producing',[SOURCE_UPGRADES]))
        if trophy_owned(state,190) and not owned('Stoic Resistance'):
            return annotate(self.step('purchase_named','Stoic Resistance','Activate the installed Stoic starter reward if unowned; older wiki descriptions differ from this game version',[SOURCE_TROPHIES]))
        if state.get('alignment',0)!=alignment:
            required=1e16 if alignment==3 and state.get('ascension',0)==0 else 0
            if state.get('coins',0)<required:
                return annotate(dict(self.step('collect_coins',None,'Collect enough coins for the chosen alignment',[SOURCE_UPGRADES]),target_coins=required))
            title={1:'Proof of Good Deed',2:'Proof of Evil Deed',3:'Proof of Neutrality'}[alignment]
            return annotate(dict(self.step('purchase_named',title,'Choose the requested alignment, not an arbitrary treaty',[SOURCE_UPGRADES]),expect={'alignment':alignment}))
        if state.get('faction',-1)!=faction:
            if faction==11:
                required=5e55 if state.get('ascension',0)==0 else 0
                if state.get('coins',0)<required:
                    return annotate(dict(self.step('collect_coins',None,'Reach the Mercenary First Contract cost',[SOURCE_MERC]),target_coins=required))
                title='Mercenary First Contract'
            else:title={'Elf':'Elven','Titan':'Titans'}.get(name,name)+' Trade Treaty'
            return annotate(dict(self.step('purchase_named',title,'Affiliation unlocks the faction upgrades and spells',[SOURCE_MERC if faction==11 else 'http://musicfamily.org/realm/Factions/']),expect={'faction':faction}))
        bloodline=rec.get('bloodline')
        if bloodline and not owned(bloodline+' Bloodline'):
            return annotate(self.step('purchase_named',bloodline+' Bloodline','Templates do not select bloodlines; verify this purchase separately',[SOURCE_BUILDS]))
        if rec.get('template'):
            return annotate(dict(self.step('deploy_build',rec['name'],'Load affordable template choices and verify actual ownership; repeat only while making progress',[SOURCE_BUILDS]),template=rec['template'],recommendation=rec))
        return annotate(dict(self.step('maintain_faction',name,'Buy ordinary upgrades/buildings and maintain the selected faction spells',['http://musicfamily.org/realm/Factions/']),recommendation=rec))
    @staticmethod
    def step(action,target,reason,sources):
        return {'action':action,'target':target,'reason':reason,'sources':sources,'planned_only':True}
