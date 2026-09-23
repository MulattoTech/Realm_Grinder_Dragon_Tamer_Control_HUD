"""One interface for reviewed progression recipes and the broader reference corpus."""
import json
from pathlib import Path
from src.atomic_store import write_json
from src.mechanics import RuleBook
from src.source_cards import build_card_index

ROOT=Path(__file__).resolve().parents[1]

class KnowledgeService:
    def __init__(self,state_dir=None,data_dir=None):
        self.state_dir=Path(state_dir or ROOT/'state')
        self.data_dir=Path(data_dir or ROOT/'data')
        data=json.loads((self.data_dir/'progression_rules.json').read_text(encoding='utf-8'))
        self.book=RuleBook(data['rules']);self.formulas=data.get('formulas',[])
        self.cards_file=self.state_dir/'source_cards.json'
        self._cards=None

    def rebuild_references(self,store=None):
        if store is None:
            from src.source_knowledge import KnowledgeStore
            store=KnowledgeStore()
        with store.connect() as database:documents=[dict(row) for row in database.execute('SELECT * FROM documents')]
        index=build_card_index(documents)
        write_json(self.cards_file,index)
        self._cards=index
        write_json(self.state_dir/'mechanics_coverage.json',self.coverage())
        return self.coverage()

    def cards(self):
        if self._cards is None:
            self._cards=json.loads(self.cards_file.read_text(encoding='utf-8')) if self.cards_file.exists() else {'cards':[],'documents':0}
        return self._cards['cards']

    def coverage(self):
        cards=self.cards()
        return {'documents':self._cards.get('documents',0),'reference_cards':len(cards),
                'conflicting_cards':sum(card.get('has_conflicting_fields',False) for card in cards),
                'reviewed_recipes':len(self.book.rules),'reviewed_formula_models':len(self.formulas),
                'reference_only_cards':sum(card['name'] not in self.book.rules for card in cards),
                'all_wiki_logic_executable':False,
                'policy':'Reference coverage is not executable coverage. Unknown prerequisites and source disagreements are retained.'}

    def plan_target(self,target,state):
        target=target.strip()
        if not target:raise ValueError('Enter a goal or exact upgrade/trophy name')
        canonical=next((name for name in self.book.rules if name.casefold()==target.casefold()),target)
        result=self.book.plan(canonical,state)
        result['references']=[card for card in self.cards() if card['name'].casefold()==target.casefold()][:8]
        return result
