"""Compile wiki template codes to source-listed save identifiers; no source code is executed."""
import hashlib
import json
from pathlib import Path
import re
from src.atomic_store import write_json
ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://github.com/dox4242/RG-tools/blob/master/lib/util.js'
PREFIX={'Fairy':'FR','Elven':'EL','Angel':'AN','Goblin':'GB','Undead':'UD','Demon':'DM',
        'Titan':'TT','Druid':'DD','Faceless':'FC','Dwarven':'DN','Drow':'DW','Dragon':'DG',
        'Archon':'AR','Djinn':'DJ','Makers':'MK'}

def named_entries(text,section):
    match=re.search(r'this\.'+re.escape(section)+r'\s*=\s*\[(.*?)\];',text,re.S)
    if not match:raise ValueError('Missing reference section '+section)
    pattern=r"\{\s*id:\s*(\d+),\s*name:\s*'((?:\\.|[^'])*)'"
    return [(int(identifier),name.replace("\\'", "'").replace('\\\\','\\'))
            for identifier,name in re.findall(pattern,match.group(1))]

def load_reference_ids():
    packaged=ROOT/'data'/'reference_identifiers.json'
    if packaged.exists():
        return json.loads(packaged.read_text(encoding='utf-8'))
    path=ROOT/'scratch/rgtools-util.txt';text=path.read_text(encoding='utf-8')
    codes={};bloodlines={};names={}
    for identifier,name in named_entries(text,'upgradeIDs'):
        names[name]=identifier
        tier=re.match(r'(.+?)\s+(\d+),(\d+):',name)
        research=re.match(r'^([SCDEAWF]\d+):',name)
        if tier and tier.group(1) in PREFIX:
            codes[PREFIX[tier.group(1)]+str((int(tier.group(2))-1)*3+int(tier.group(3)))]=identifier
        elif research:codes[research.group(1)]=identifier
        if name.endswith(' Bloodline'):bloodlines[name]=identifier
    return {'codes':codes,'bloodlines':bloodlines,'names':names,
            'spells':{name:i for i,name in named_entries(text,'spells')},
            'source_url':SOURCE,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def _supported_definitions(game_identity):
    """Return SWF definitions pinned to the exact supported binary and save schema."""
    if not isinstance(game_identity,dict) or game_identity.get('supported') is not True:
        return []
    digest=game_identity.get('swf_sha256')
    version=game_identity.get('save_version')
    if not isinstance(digest,str) or len(digest)!=64 or not isinstance(version,int):
        return []
    try:
        versions=json.loads((ROOT/'data'/'supported_game_versions.json').read_text(encoding='utf-8')).get('versions',[])
    except (OSError,ValueError):
        return []
    matches=[item for item in versions if item.get('swf_sha256')==digest and item.get('save_version')==version]
    return matches[0].get('definitions',[]) if len(matches)==1 else []


def compile_template(template,catalog,save_version,game_identity=None):
    required=[];spells=[];unknown=[]
    definitions=_supported_definitions(game_identity)
    source_names={}
    for name,identifier in catalog.get('names',{}).items():
        if identifier in source_names:
            source_names[identifier]=None
        else:
            source_names[identifier]=name.split(': ',1)[-1]
    installed_names={}
    for definition in definitions:
        if definition.get('kind')=='upgrade':
            installed_names.setdefault(definition.get('name'),[]).append(definition.get('id'))
    for token in [p.strip() for p in template.replace('\n','').split(',') if p.strip()]:
        if token.startswith('SP:'):
            identifier=catalog['spells'].get(token[3:].strip())
            if identifier is None:unknown.append(token)
            else:spells.append(identifier)
        else:
            source_id=catalog.get('codes',{}).get(token)
            name=source_names.get(source_id) if source_id is not None else None
            candidates=installed_names.get(name,[]) if name else []
            identity_version=game_identity.get('save_version') if isinstance(game_identity,dict) else None
            if len(candidates)!=1 or identity_version!=save_version:
                unknown.append(token)
            else:
                required.append(candidates[0])
    if len(required)!=len(set(required)):unknown.append('DUPLICATE_UPGRADE_SELECTION')
    verified=bool(required) and not unknown and bool(definitions)
    return {'verified':verified,'template':template,'save_version':save_version,
            'required_upgrade_ids':required,'merc_spells':spells,'unresolved_tokens':unknown,
            'sources':[catalog['source_url']],'source_sha256':catalog['sha256'],
            'swf_sha256':game_identity.get('swf_sha256') if verified else None,
            'verification_scope':'Exact supported SWF definitions; in-game ownership is checked separately'}

def rebuild_manifests(save_version,game_identity=None):
    from src.wiki_data import BUILDS_DATABASE
    reference=load_reference_ids();builds={}
    for rec in BUILDS_DATABASE.values():
        manifest=compile_template(rec.get('template',''),reference,save_version,game_identity)
        faction=rec.get('faction','')
        if 'Neutral' in faction:manifest['alignment']=3
        elif faction in ('Fairy','Fairy/Dwarf','Angel','Elf'):manifest['alignment']=1
        elif faction in ('Goblin','Goblin/Drow','Demon','Undead'):manifest['alignment']=2
        builds[rec['name']]=manifest
    write_json(ROOT/'state/build_manifests.json',{'schema_version':2,'builds':builds})
    path=ROOT/'state/upgrade_catalog.json'
    known=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for name,identifier in reference['bloodlines'].items():
        if known.get(name,{}).get('verification')!='installed_definition':
            known[name]={'id':identifier,'save_version':save_version,'verification':'source_identifier',
                         'source_url':SOURCE,'source_sha256':reference['sha256']}
    write_json(path,known);write_json(ROOT/'state/reference_identifiers.json',reference)
    return builds
