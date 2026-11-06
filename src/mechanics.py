"""Data-driven prerequisite planning and bounded mathematical interpretation.

This module does not issue input and never executes source text as Python.
Unknown facts, unsupported requirements and source conflicts remain blockers.
"""
from __future__ import annotations
import ast
import copy
import math
import operator


def read_field(state,path):
    value=state
    for part in path.split('.'):
        if isinstance(value,dict):
            if part not in value:return None
            value=value[part]
        elif isinstance(value,list) and part.isdigit() and int(part)<len(value):
            value=value[int(part)]
        else:return None
    return value


def calculate_formula(expression,variables):
    """Interpret a limited expression tree with bounded size, powers and results."""
    if not isinstance(expression,str) or len(expression)>512:raise ValueError('Formula exceeds size limit')
    try:tree=ast.parse(expression.replace('^','**'),mode='eval')
    except (SyntaxError,RecursionError) as exc:raise ValueError('Unsupported formula syntax') from exc
    if sum(1 for _ in ast.walk(tree))>100:raise ValueError('Formula exceeds node limit')
    functions={'sqrt':math.sqrt,'ln':math.log,'log10':math.log10,'floor':math.floor,
               'ceil':math.ceil,'min':min,'max':max,'abs':abs}
    binary={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
    def finite(number):
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number):
            raise ValueError('Formula produced a non-finite or non-numeric value')
        if abs(number)>1e300:raise ValueError('Formula result exceeds numeric limit')
        return number
    def visit(node,depth=0):
        if depth>20:raise ValueError('Formula exceeds depth limit')
        if isinstance(node,ast.Expression):return visit(node.body,depth+1)
        if isinstance(node,ast.Constant):return finite(node.value)
        if isinstance(node,ast.Name):
            if node.id not in variables:raise ValueError('Unknown variable: '+node.id)
            return finite(variables[node.id])
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            return finite(visit(node.operand,depth+1)*(1 if isinstance(node.op,ast.UAdd) else -1))
        if isinstance(node,ast.BinOp):
            left,right=visit(node.left,depth+1),visit(node.right,depth+1)
            if isinstance(node.op,ast.Pow):
                if abs(right)>1024:raise ValueError('Power exceeds exponent limit')
                return finite(math.pow(left,right))
            function=binary.get(type(node.op))
            if function:return finite(function(left,right))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
            function=functions.get(node.func.id)
            if function and 1<=len(node.args)<=8:
                return finite(function(*(visit(arg,depth+1) for arg in node.args)))
        raise ValueError('Unsupported formula operation: '+type(node).__name__)
    try:return visit(tree)
    except (OverflowError,ZeroDivisionError,TypeError,RecursionError) as exc:
        raise ValueError('Formula cannot be evaluated safely') from exc


def condition_value(condition,state):
    if condition.get('op') in ('owned_upgrade','owned_trophy'):
        collection='upgrades' if condition['op']=='owned_upgrade' else 'trophies'
        records=read_field(state,'raw_data.'+collection)
        if not isinstance(records,dict):return None
        key=str(condition.get('id'))
        return key in records if collection=='trophies' else bool(records.get(key,{}).get('u1',False))
    if 'all' in condition or 'any' in condition:
        conjunction='all' in condition
        values=[condition_value(child,state) for child in condition['all' if conjunction else 'any']]
        if conjunction:return False if False in values else None if None in values else True
        return True if True in values else None if None in values else False
    if condition.get('op')=='not':
        value=condition_value(condition.get('condition',{}),state)
        return None if value is None else not value
    value=read_field(state,condition.get('field',''))
    expected=condition.get('value')
    if value is None or expected is None:return None
    comparisons={'eq':operator.eq,'ne':operator.ne,'gte':operator.ge,'lte':operator.le,'gt':operator.gt,'lt':operator.lt}
    function=comparisons.get(condition.get('op'))
    try:
        if function:return bool(function(value,expected))
        if condition.get('op')=='in':return value in expected
    except (TypeError,ValueError):return None
    return None


def ownership(rule,state):
    target=rule.get('ownership',{})
    if target.get('kind')=='condition':return condition_value(target['condition'],state)
    collection={'upgrade':'upgrades','trophy':'trophies'}.get(target.get('kind'))
    records=read_field(state,'raw_data.'+collection) if collection else None
    identifier=target.get('id')
    if not isinstance(records,dict) or not isinstance(identifier,int):return None
    if collection=='trophies':return str(identifier) in records
    return bool(records.get(str(identifier),{}).get('u1',False))


class RuleBook:
    def __init__(self,rules):
        self.rules={}
        for rule in rules:
            name=rule.get('name')
            if not isinstance(name,str) or not name:raise ValueError('Every rule needs a name')
            if name in self.rules and self.rules[name]!=rule:raise ValueError('Conflicting rules: '+name)
            self.rules[name]=copy.deepcopy(rule)
        if len(self.rules)>20000:raise ValueError('Rule catalog exceeds limit')

    def _assess(self,rule,state):
        result={'name':rule['name'],'sources':rule.get('sources',[]),'owned':ownership(rule,state),
                'conditions':[],'costs':[],'status':'READY','action':rule.get('action')}
        if not rule.get('reviewed') or not rule.get('sources') or rule.get('conflicts'):
            result['status']='REFERENCE_ONLY';return result
        scope=rule.get('scope',{})
        supported_hashes=scope.get('swf_sha256s')
        if supported_hashes is not None:
            identity=state.get('game_identity')
            save_version=read_field(state,'raw_data.saveVersion')
            if (not isinstance(identity,dict) or identity.get('supported') is not True or
                identity.get('swf_sha256') not in supported_hashes or
                identity.get('save_version') not in scope.get('save_versions',[]) or
                save_version not in scope.get('save_versions',[])):
                result['status']='UNSUPPORTED_GAME_VERSION';return result
        if result['owned'] is True:result['status']='OWNED';return result
        save_version=read_field(state,'game_identity.save_version')
        if save_version is None:save_version=read_field(state,'raw_data.saveVersion')
        if ((scope.get('ascensions') is not None and state.get('ascension') not in scope['ascensions']) or
            ('min_r' in scope and state.get('reincarnation',-1)<scope['min_r']) or
            ('max_r' in scope and state.get('reincarnation',math.inf)>scope['max_r']) or
            (scope.get('save_versions') and save_version not in scope['save_versions'])):
            result['status']='UNSUPPORTED_STAGE';return result
        for condition in rule.get('conditions',[]):
            actual=read_field(state,condition.get('field',''))
            result['conditions'].append(dict(condition,actual=actual,satisfied=condition_value(condition,state)))
        for cost in rule.get('costs',[]):
            amount=cost.get('amount')
            if 'formula' in cost:
                try:amount=calculate_formula(cost['formula'],{key:read_field(state,path) for key,path in cost.get('variables',{}).items()})
                except ValueError:amount=None
            if 'free_from_ascension' in cost and state.get('ascension',-1)>=cost['free_from_ascension']:amount=0
            actual=read_field(state,cost.get('field',''))
            known=(isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(actual) and
                   isinstance(amount,(int,float)) and not isinstance(amount,bool) and math.isfinite(amount) and amount>=0)
            result['costs'].append(dict(cost,amount=amount,actual=actual,satisfied=actual>=amount if known else None,
                                       deficit=max(0,amount-actual) if known else None))
        predicates=[item['satisfied'] for item in result['conditions']]
        budgets=[item['satisfied'] for item in result['costs']]
        if result['owned'] is None or None in predicates or None in budgets:result['status']='UNKNOWN'
        elif False in predicates:result['status']='LOCKED'
        elif False in budgets:result['status']='NEEDS_RESOURCES'
        return result

    def plan(self,goal,state):
        steps=[];visited=set();active=set()
        def walk(name):
            if name in active:raise ValueError('Prerequisite cycle at '+name)
            if name in visited:return
            if len(visited)+len(active)>256:raise ValueError('Prerequisite graph exceeds traversal limit')
            active.add(name)
            rule=self.rules.get(name)
            if rule is None:
                assessed={'name':name,'status':'REFERENCE_ONLY','owned':None,'sources':[],
                          'conditions':[],'costs':[],'reason':'No reviewed rule for the requested prerequisite'}
            else:
                assessed=self._assess(rule,state)
                if assessed['status'] not in ('OWNED','UNSUPPORTED_GAME_VERSION'):
                    for dependency in rule.get('dependencies',[]):walk(dependency)
                    if any(step['status']!='OWNED' and step['name'] in rule.get('dependencies',[]) for step in steps):
                        assessed['prerequisite_status']=assessed['status'];assessed['status']='NEEDS_PREREQUISITE'
            steps.append(assessed);active.remove(name);visited.add(name)
        walk(goal)
        pending=next((step for step in steps if step['status']!='OWNED'),None)
        action=None
        if pending:
            status=pending['status'];action={'target':pending['name'],'sources':pending['sources'],'status':status}
            if status=='READY':action.update(pending.get('action') or {'action':'reference_only'})
            elif status=='NEEDS_RESOURCES':
                cost=next(item for item in pending['costs'] if item['satisfied'] is False)
                action.update(action='collect_coins' if cost['field']=='coins' else 'collect_resource',
                              field=cost['field'],amount=cost['amount'],deficit=cost['deficit'])
                if cost['field']=='coins':action['target_coins']=cost['amount']
            elif status in ('UNKNOWN','LOCKED'):
                action.update(action='needs_measurement' if status=='UNKNOWN' else 'prerequisite_blocked',
                              conditions=pending['conditions'],costs=pending['costs'])
            else:action['action']='reference_only'
        return {'goal':goal,'complete':pending is None,'next_action':action,'steps':steps,
                'execution_policy':'Only reviewed, source-attributed, fully evaluated rules authorize a proposed purchase'}
