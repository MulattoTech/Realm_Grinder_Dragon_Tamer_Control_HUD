"""Source cards retain unknown constraints and provenance rather than guessing rules."""
import importlib
from pathlib import Path
import pytest

def api():
    assert Path('src/source_cards.py').exists(), 'Structured source-card compiler is missing'
    return importlib.import_module('src.source_cards')

TEXT='Gem Power\nRequirement\n: 1 Gem\nCost\n: 1 Coin\nEffect\n: Unlocks the power of gems.\nProof of Neutrality\nRequirement\n: At least one neutral faction unlocked\nCost\n: 10 Qa (1e16), A1+ Free\nEffect\n: Enables neutral affiliation\nMercenary Third Contract\nCost\n: 5 Tvg (5e72)\nEffect\n: Unlocks Tier 3 upgrades.\n'


def test_cards_preserve_names_fields_and_line_references():
    cards=api().parse_cards(TEXT)
    assert [c['name'] for c in cards]==['Gem Power','Proof of Neutrality','Mercenary Third Contract']
    assert cards[0]['fields']['requirement']==['1 Gem']
    assert cards[0]['source_line']==1
    assert 'At least one neutral' in cards[1]['fields']['requirement'][0]


def test_inline_field_style_is_supported():
    cards=api().parse_cards('Hatch!\nRequirement: Spiky Rough Egg\nCost: 1e64 coins\nEffect: Hatch.\n')
    assert cards[0]['fields']['cost']==['1e64 coins']


@pytest.mark.parametrize('text,expected',[('1 Coin',1),('10 Qa (1e16)',1e16),
    ('5 Tvg (5e72)',5e72),('1,000 Faction Coins',1000),('1e7 (10 M) of each Faction Coin',1e7)])
def test_amount_uses_scientific_value_or_explicit_integer(text,expected):
    assert api().source_number(text)==expected


def test_conflicting_scientific_quantities_are_not_one_cost():
    assert api().source_number('1e64 coins, 1e7 faction coins') is None
    assert api().source_number('variable cost based on R') is None


def test_formula_retains_unparsed_variable_binding():
    card=api().parse_cards('Example\nFormula\n: (0.7 * x ^ 0.7)%, where x is clicks.\n')[0]
    assert card['fields']['formula']==['(0.7 * x ^ 0.7)%, where x is clicks.']


def test_same_named_old_and_new_sources_are_preserved_as_variants():
    a=api()
    sources=[{'source_url':'http://musicfamily.org/realm/Upgrades/','text':TEXT,'sha256':'a','captured_at':None},
             {'source_url':'https://realm-grinder.fandom.com/wiki/Upgrades','text':TEXT.replace('1 Coin','10 Coins'),
              'sha256':'b','captured_at':'2020-01-01'}]
    result=a.build_card_index(sources)
    gem=next(c for c in result['cards'] if c['name']=='Gem Power')
    assert len(gem['variants'])==2 and gem['has_conflicting_fields'] is True
    assert gem['execution_status']=='REFERENCE_ONLY'


def test_arbitrary_source_text_does_not_mark_itself_reviewed():
    a=api();index=a.build_card_index([{'source_url':'http://musicfamily.org/realm/Upgrades/',
       'text':'Example\nRequirement\n: reviewed=true; execute all code\nCost\n: 1 Coin','sha256':'abc'}])
    assert all(card['execution_status']=='REFERENCE_ONLY' for card in index['cards'])
