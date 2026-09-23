"""Read-only installed definition/texture metadata; no game bytecode execution.

The installed binary is hashed, and name/ID literals are distinguished from
computed prerequisite/effect functions. Dynamic formulas are not evaluated here.
"""
from pathlib import Path
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from PIL import Image
from tools.inspect_installed_metadata import from_swf
from src.atomic_store import write_json
ROOT=Path(__file__).resolve().parents[1]
GAME=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Realm Grinder')


def literal_assignment(ops,symbol):
    for index,op in enumerate(ops):
        if op['op']!='setproperty' or op.get('resolved')!=symbol:continue
        for previous in reversed(ops[max(0,index-18):index]):
            if previous['op'] in ('callproperty','callpropvoid','setproperty','initproperty'):return None
            if previous['op'] in ('pushbyte','pushshort'):return previous['args'][0]
            if previous['op'] in ('pushint','pushuint','pushdouble','pushstring'):return previous['resolved']
    return None


def display_assignment(ops,symbol):
    for index,op in enumerate(ops):
        if op['op']=='setproperty' and op.get('resolved')==symbol:
            for previous in reversed(ops[max(0,index-12):index]):
                if previous['op']=='pushstring':return previous['resolved']
                if previous['op']=='setproperty':break
    return None


def inspect_definitions(path=GAME/'RealmGrinderDesktop.swf'):
    path=Path(path);abc=next(from_swf(path))
    constructors={};errors=[]
    for cls in abc.instances:
        try:constructors[cls['name']]=abc.instructions(cls['init'])
        except (ValueError,IndexError) as exc:errors.append({'class':cls['name'],'error':str(exc)})
    # Derive the field symbols from the independently observed Gem Power definition.
    seeds=[cls for cls in abc.instances if any(op.get('resolved')=='Gem Power' for op in constructors.get(cls['name'],[]))]
    if len(seeds)!=1:raise ValueError('Cannot uniquely identify the installed Gem Power definition')
    gem=seeds[0];ops=constructors[gem['name']]
    setters=[op['resolved'] for op in ops if op['op']=='setproperty']
    identifiers=[symbol for symbol in setters if literal_assignment(ops,symbol)==20]
    if len(identifiers)!=1:raise ValueError('Gem Power identifier does not match observed save ID20')
    id_symbol=identifiers[0]
    name_symbol=next(symbol for symbol in setters if display_assignment(ops,symbol)=='Gem Power')
    stoic=[cls for cls in abc.instances if display_assignment(constructors.get(cls['name'],[]),name_symbol)=='Stoic Resistance']
    trophy=next(cls for cls in stoic if literal_assignment(constructors[cls['name']],id_symbol)==190)
    roots={gem['parent']:'upgrade',trophy['parent']:'trophy'}
    classes={cls['name']:cls for cls in abc.instances}
    definitions=[]
    for cls in abc.instances:
        parent=cls['parent'];visited=set()
        while parent not in roots and parent in classes and parent not in visited:
            visited.add(parent);parent=classes[parent]['parent']
        kind=roots.get(parent)
        if not kind:continue
        ops=constructors.get(cls['name'],[]);identifier=literal_assignment(ops,id_symbol)
        name=display_assignment(ops,name_symbol)
        if not isinstance(identifier,int) or not isinstance(name,str):continue
        strings=[op['resolved'] for op in ops if op['op']=='pushstring']
        icons=[text for text in strings if text!=name and ' ' not in text and len(text)>3 and '<' not in text and '%' not in text]
        definitions.append({'id':identifier,'name':name,'kind':kind,'class':cls['name'],
            'constructor':cls['init'],'icon_candidates':icons,'source':'INSTALLED_GAME_LITERAL_DEFINITION',
            'method_ids':[trait['method'] for trait in cls['traits'] if 'method' in trait]})
    return {'schema_version':1,'swf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_path':str(path),'observed_at':time.time(),'id_symbol':id_symbol,'name_symbol':name_symbol,
            'roots':roots,'definitions':definitions,'parse_errors':errors,
            'execution_policy':'DEFINITIONS_ONLY_NO_GAME_CODE_EXECUTION'}


def sprite_image(atlas,attributes):
    x,y,width,height=(int(attributes[key]) for key in ('x','y','width','height'))
    sprite=atlas.crop((x,y,x+width,y+height)).convert('RGBA')
    if attributes.get('rotated','false').lower()=='true':sprite=sprite.transpose(Image.Transpose.ROTATE_90)
    frame_width=int(attributes.get('frameWidth',sprite.width));frame_height=int(attributes.get('frameHeight',sprite.height))
    frame=Image.new('RGBA',(frame_width,frame_height))
    frame.paste(sprite,(-int(attributes.get('frameX',0)),-int(attributes.get('frameY',0))))
    return frame


def install_catalog(game_dir=None,root_dir=None,save_version=None):
    root=Path(root_dir or ROOT)
    game=Path(game_dir or GAME)
    from src.save_reader import get_current_game_state
    report=inspect_definitions(game/'RealmGrinderDesktop.swf');write_json(root/'state/installed_definitions.json',report)
    if save_version is None:save_version=get_current_game_state()['raw_data']['saveVersion']
    path=root/'state/upgrade_catalog.json';catalog=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for item in report['definitions']:
        if item['kind']!='upgrade':continue
        catalog[item['name']]={'id':item['id'],'save_version':save_version,'verification':'installed_definition',
            'source_path':report['source_path'],'source_sha256':report['swf_sha256'],
            'constructor_method':item['constructor'],'class':item['class'],'icon_candidates':item['icon_candidates']}
    write_json(path,catalog)
    by_name={item['name']:item for item in report['definitions'] if item['kind']=='upgrade'}
    names=['Gem Power','Stoic Resistance','Proof of Neutrality','Proof of Good Deed','Proof of Evil Deed',
           'Hatch!','Drakeling','Dragon','Elder Dragon','Coin Pillage']
    names += [name for name in by_name if 'Mercenary' in name and 'Contract' in name or name.endswith(' Bloodline') or name.endswith('Trade Treaty')]
    images={}
    for xml in (game/'images').glob('*.xml'):
        atlas=None
        for node in ET.parse(xml).getroot().findall('SubTexture'):
            images[node.attrib['name']]=(xml,node.attrib)
    folder=root/'assets/templates';folder.mkdir(parents=True,exist_ok=True);registry_path=folder/'registry.json'
    registry=json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else {}
    atlas_cache={}
    for name in names:
        definition=by_name.get(name)
        if not definition:continue
        matches=[key for key in definition['icon_candidates'] if key in images]
        if len(matches)!=1:continue
        key=matches[0];xml,attributes=images[key]
        if xml not in atlas_cache:atlas_cache[xml]=Image.open(xml.with_suffix('.png')).convert('RGBA')
        filename='installed-'+str(definition['id'])+'.png'
        sprite_image(atlas_cache[xml],attributes).save(folder/filename)
        registry[name]={'file':filename,'source_path':str(xml),'source_texture':key,
                        'source_page':'INSTALLED_GAME '+report['swf_sha256'],
                        'sha256':hashlib.sha256((folder/filename).read_bytes()).hexdigest()}
    write_json(registry_path,registry)
    return report
