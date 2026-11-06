"""Prepare a checkout using bundled factual IDs and optional local game metadata.

No network, game input, game launch, save editing or administrator access is used.
Live state, game binaries and full extracted game textures remain local.
Small version-bound UI reference crops are distributed separately with attribution.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from src.atomic_store import write_json
from src.build_catalog import compile_template

ROOT=Path(__file__).resolve().parents[1]
VERSION_CATALOG_PATH=ROOT/'data/supported_game_versions.json'


def find_game_directory(explicit=None):
    if explicit:return Path(explicit).expanduser().resolve()
    override=os.environ.get('REALM_GRINDER_GAME_DIR')
    if override:return Path(override).expanduser().resolve()
    candidates=[Path(r'C:\Program Files (x86)\Steam')]
    if os.name=='nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
                candidates.insert(0,Path(winreg.QueryValueEx(key,'SteamPath')[0]))
        except OSError:pass
    for steam in list(candidates):
        config=steam/'steamapps/libraryfolders.vdf'
        if config.exists():
            for value in re.findall(r'"path"\s+"([^"]+)"',config.read_text(encoding='utf-8')):
                library=Path(value.replace('\\\\','\\'))
                if library not in candidates:candidates.append(library)
    for steam in candidates:
        folder=steam/'steamapps/common/Realm Grinder'
        if (folder/'RealmGrinderDesktop.swf').exists():return folder
    return candidates[0]/'steamapps/common/Realm Grinder'


def initialize(root=ROOT,game_dir=None,refresh_installed=False):
    root=Path(root);game=find_game_directory(game_dir)
    for folder in ('state','logs','backups','screenshots','scraped_wiki/html','assets/templates'):
        (root/folder).mkdir(parents=True,exist_ok=True)
    config=root/'state/bot_config.json'
    if not config.exists():
        write_json(config,{'paused':True,'selected_path':'Automatic','selected_goal':'Build only',
            'auto_buy_upgrades':True,'auto_buy_buildings':True,'auto_click_realm':True,
            'auto_cast_spells':True,'auto_spells':True,'auto_apply_build':True,
            'auto_abdicate':False,'auto_reincarnate':False,'auto_excavate':False,
            'require_minimized':True,'cycle_delay_sec':5.0})
        (root/'state/STOP').write_text('New checkout: review source coverage and select a path before resuming.',encoding='utf-8')
    reference=json.loads((ROOT/'data/reference_identifiers.json').read_text(encoding='utf-8'))
    from src import game_identity
    # Keep the public module constant usable for controlled tests and local
    # metadata refreshes while identity cache keys include its stat signature.
    game_identity.VERSION_CATALOG_PATH=VERSION_CATALOG_PATH
    identity=game_identity.get_game_identity(game)
    digest=identity['swf_sha256'];verified=identity['supported']
    save_version=identity['save_version']
    status=identity['support_status']
    from src.wiki_data import BUILDS_DATABASE
    manifests={rec['name']:compile_template(rec.get('template',''),reference,save_version,identity) for rec in BUILDS_DATABASE.values()}
    path=root/'state/build_manifests.json'
    if not path.exists() or verified:write_json(path,{'schema_version':2,'builds':manifests})
    path=root/'state/upgrade_catalog.json'
    if not path.exists() and not verified:write_json(path,{})
    path=root/'state/milestone_catalog.json'
    if not path.exists() or verified:
        names={'spiky_rough_egg':('Spiky Rough Egg','trophy'),'hatch':('Hatch!','upgrade'),
               'drakeling':('Drakeling','upgrade'),'dragon':('Dragon','upgrade'),
               'elder_dragon':('Elder Dragon','upgrade'),'dragon_tamer':('Dragon Tamer','trophy')}
        milestones={}
        for key,(name,kind) in names.items():
            matches=[item for item in _definitions_for_identity(identity) if item['name']==name and item['kind']==kind]
            if len(matches)==1:milestones[key]={'id':matches[0]['id'],'kind':kind,'verified':verified,
                'source':'SUPPORTED_INSTALLED_LITERAL_DEFINITION','swf_sha256':digest}
        write_json(path,{'schema_version':2,'milestones':milestones})
    if verified:
        from src.installed_catalog import install_catalog
        install_catalog(game_dir=game,root_dir=root,save_version=save_version,
                        invalidate_existing=True)
    elif not verified:
        _invalidate_installed_catalogs(root)
    if verified:
        anchors=ROOT/'data/ui_reference'
        manifest=json.loads((anchors/'manifest.json').read_text(encoding='utf-8'))
        if manifest['swf_sha256']==digest:
            for item in manifest['files']:
                data=(anchors/item['file']).read_bytes()
                if hashlib.sha256(data).hexdigest()!=item['sha256']:
                    raise ValueError('UI reference checksum mismatch: '+item['file'])
                target=root/'assets/templates'/item['file']
                if not target.exists():target.write_bytes(data)
    from src.source_knowledge import KnowledgeStore
    knowledge=KnowledgeStore(root/'scraped_wiki/knowledge.sqlite3')
    notes=json.loads((ROOT/'data/compatibility_notes.json').read_text(encoding='utf-8'))
    for note in notes['notes']:
        with knowledge.connect() as database:
            existing=database.execute('SELECT 1 FROM documents WHERE source_url=?',(note['source_url'],)).fetchone()
        if not existing:
            knowledge.ingest(note['title'],note['source_url'],note['text'],origin=note['origin'],
                             captured_at=note['captured_at'],license='Project development observation; game facts retain their original attribution')
    report={'game_metadata':status,'game_dir':str(game),'installed_sha256':digest,
            'game_version':identity['game_version'],'save_version':identity['save_version'],
            'network_requests':0,'game_input_sent':False,
            'prepared_build_manifests':len(manifests),'configuration_preserved':True,
            'instructions':'Open the HUD from the logged-on Windows desktop. Keep resets off until semantic reset validation passes.'}
    write_json(root/'state/bootstrap_report.json',report)
    return report


def _definitions_for_identity(identity):
    if not identity.get('supported'):
        return []
    catalog=json.loads(VERSION_CATALOG_PATH.read_text(encoding='utf-8'))
    version=next((item for item in catalog.get('versions',[])
                  if item.get('swf_sha256')==identity.get('swf_sha256')),None)
    return [] if version is None else version.get('definitions',[])


def _invalidate_installed_catalogs(root):
    """Remove local generated verification tied to a different/absent SWF."""
    state=root/'state';path=state/'upgrade_catalog.json'
    if path.exists():
        try:catalog=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):catalog={}
        catalog={name:item for name,item in catalog.items()
                 if item.get('verification') not in ('installed_definition','unverified_bundled_identifier')
                 and not item.get('verified_against_installed')}
        write_json(path,catalog)
    write_json(state/'milestone_catalog.json',{'schema_version':2,'milestones':{}})
    definitions=state/'installed_definitions.json'
    if definitions.exists():definitions.unlink()
    registry_path=root/'assets/templates/registry.json'
    if registry_path.exists():
        try:registry=json.loads(registry_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):registry={}
        registry={name:item for name,item in registry.items()
                  if not str(item.get('source_page','')).startswith('INSTALLED_GAME ')}
        write_json(registry_path,registry)
