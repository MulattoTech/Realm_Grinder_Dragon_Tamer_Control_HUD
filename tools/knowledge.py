"""Search, compile and inspect source-backed mechanics without issuing gameplay input."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('coverage');sub.add_parser('compile')
    search=sub.add_parser('search');search.add_argument('query')
    plan=sub.add_parser('plan');plan.add_argument('target');plan.add_argument('--state-json',type=Path)
    formula=sub.add_parser('formula');formula.add_argument('expression');formula.add_argument('--variables',default='{}')
    args=parser.parse_args()
    from src.knowledge_service import KnowledgeService
    service=KnowledgeService()
    if args.command=='coverage':result=service.coverage()
    elif args.command=='compile':result=service.rebuild_references()
    elif args.command=='formula':
        from src.mechanics import calculate_formula
        result={'result':calculate_formula(args.expression,json.loads(args.variables))}
    elif args.command=='search':
        from src.source_knowledge import KnowledgeStore
        result=KnowledgeStore().search(args.query,limit=10)
    else:
        if args.state_json:state=json.loads(args.state_json.read_text(encoding='utf-8-sig'))
        else:
            from src.live_state import get_live_game_state
            state=get_live_game_state()
        result=service.plan_target(args.target,state)
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__':main()
