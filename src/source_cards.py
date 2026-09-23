"""Structured reference cards with source variants and explicit non-executable status."""
import hashlib
import math
import re
from collections import defaultdict

LABEL=re.compile(r'^(Description|Unlock Requirement[s]?|Requirement[s]?|Cost|Effect|Formula|Alignment|Note|Range|Type|Duration|Mana Cost)(?:\s*:\s*(.*))?$',re.I)

def parse_cards(text):
    lines=[(number,line.strip()) for number,line in enumerate(text.splitlines(),1) if line.strip()]
    cards=[];current=None;field=None;buffer=[]
    def flush():
        nonlocal buffer
        if current is not None and field and buffer:
            current['fields'].setdefault(field,[]).append(' '.join(buffer).lstrip(':').strip())
        buffer=[]
    for index,(number,line) in enumerate(lines):
        match=LABEL.fullmatch(line)
        next_label=index+1<len(lines) and LABEL.fullmatch(lines[index+1][1])
        heading=(not match and next_label and not line.startswith((':','(', '+','-')) and len(line)<180 and
                 not re.match(r'^\d[\d.,e+\-]*\s+(?:Coin|Gem|Mana|Faction)',line,re.I))
        if heading:
            flush();current={'name':line,'fields':{},'source_line':number};cards.append(current);field=None
        elif match and current is not None:
            flush();field=match.group(1).lower().replace('requirements','requirement')
            if match.group(2):buffer=[match.group(2)]
        elif current is not None and field:
            buffer.append(line)
    flush()
    return [card for card in cards if card['fields']]


def source_number(text):
    scientific=re.findall(r'(?<![\w.])\d+(?:\.\d+)?[eE][+-]?\d+',text)
    if scientific:
        values=set(float(value) for value in scientific)
        return values.pop() if len(values)==1 and all(math.isfinite(value) for value in values) else None
    match=re.match(r'^\s*(\d[\d,]*(?:\.\d+)?)\s+(?:Coins?|Mana|Faction Coins?|of each)',text,re.I)
    if match:return float(match.group(1).replace(',',''))
    return None


def build_card_index(documents):
    groups=defaultdict(list)
    for document in documents:
        text=document.get('text','')
        for card in parse_cards(text):
            source={'url':document['source_url'],'sha256':document.get('sha256') or hashlib.sha256(text.encode()).hexdigest(),
                    'captured_at':document.get('captured_at'),'observed_at':document.get('observed_at'),
                    'origin':document.get('origin'),'resolved_url':document.get('resolved_url'),
                    'line':card['source_line']}
            groups[card['name']].append({'fields':card['fields'],'source':source})
    cards=[]
    for name,variants in sorted(groups.items()):
        comparisons=defaultdict(set)
        for variant in variants:
            for field in ('requirement','unlock requirement','cost','formula','effect'):
                values=variant['fields'].get(field)
                if values:comparisons[field].add(' '.join(values).casefold())
        conflicts=[field for field,values in comparisons.items() if len(values)>1]
        cards.append({'name':name,'variants':variants,'conflicting_fields':conflicts,
                      'has_conflicting_fields':bool(conflicts),'execution_status':'REFERENCE_ONLY'})
    return {'schema_version':1,'documents':len(documents),'cards':cards,
            'card_count':len(cards),'conflict_count':sum(card['has_conflicting_fields'] for card in cards)}
