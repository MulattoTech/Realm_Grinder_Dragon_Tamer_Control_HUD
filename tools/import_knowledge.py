"""Populate local wiki reference material and dated Archive.org fallbacks.

Run from the project root. This tool only writes the bot's reference cache;
it never sends game input. Page failures are recorded instead of hidden.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote,urljoin,urlsplit
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.source_knowledge import KnowledgeStore,html_text,canonical_url
from src.atomic_store import write_json
ROOT=Path(__file__).resolve().parents[1]
UA='RealmGrinderLocalKnowledge/1.0 (personal reference cache; bounded requests)'


def fetch(url,limit=5_000_000):
    request=Request(url,headers={'User-Agent':UA})
    with urlopen(request,timeout=14) as response:
        data=response.read(limit+1)
        if len(data)>limit:raise ValueError('Page exceeds configured size limit')
        return data,response.geturl()


def archived(original):
    available,_=fetch('https://archive.org/wayback/available?url='+quote(original,safe=''))
    closest=json.loads(available).get('archived_snapshots',{}).get('closest',{})
    if not closest.get('available'):raise FileNotFoundError('No available archived snapshot')
    resolved=closest['url'];data,_=fetch(resolved)
    stamp=closest.get('timestamp','')
    captured=f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}' if len(stamp)>=8 else stamp
    return data,resolved,captured


def import_existing(store):
    for path in sorted((ROOT/'scraped_wiki/pages').glob('*.md')):
        text=path.read_text(encoding='utf-8')
        match=re.search(r'^URL:\s*(\S+)',text,re.M)
        if match:
            with store.connect() as db:
                existing=db.execute('SELECT 1 FROM documents WHERE source_url=?',(canonical_url(match.group(1)),)).fetchone()
            if existing:continue
            store.ingest(path.stem,match.group(1),text,origin='musicfamily_cached',
                         captured_at=None,license='Source attribution retained; no open-code license asserted')
    manifest_path=ROOT/'data/source_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')).get('sources',[]) if manifest_path.exists() else []
    for path in sorted((ROOT/'scraped_wiki/html').glob('*.html')):
        title=path.stem.removeprefix('fandom-')
        candidates=[row for row in manifest if row['title']==title]
        if len(candidates)!=1:continue  # Unnamed cache bytes do not establish a date or source URL.
        row=candidates[0]
        with store.connect() as db:
            existing=db.execute('SELECT 1 FROM documents WHERE source_url=?',(row['source_url'],)).fetchone()
        if existing:continue
        store.ingest(row['title'],row['source_url'],html_text(path.read_bytes()),
                     origin='local_cache',resolved_url=row.get('resolved_url'),captured_at=row.get('captured_at'),
                     license='Source attribution retained; cached provenance is not live verification')


def collect_page(spec):
    origin,title,url=spec
    try:
        if origin=='fandom':
            data,resolved,captured=archived(url)
            actual='fandom_archived'
        else:
            data,resolved=fetch(url);captured=None;actual='musicfamily_live'
        soup_text=html_text(data)
        if len(soup_text)<150:raise ValueError('Page has too little usable source text')
        return {'ok':True,'title':title,'url':url,'text':soup_text,'origin':actual,
                'resolved':resolved,'captured':captured,'html':data}
    except Exception as exc:
        if origin=='musicfamily':
            try:
                data,resolved,captured=archived(url)
                return {'ok':True,'title':title,'url':url,'text':html_text(data),'origin':'musicfamily_archived',
                        'resolved':resolved,'captured':captured,'html':data}
            except Exception as archive_exc:return {'ok':False,'url':url,'error':str(exc)+'; Archive: '+str(archive_exc)}
        return {'ok':False,'url':url,'error':str(exc)}


def download_icons():
    from bs4 import BeautifulSoup
    folder=ROOT/'assets/templates';folder.mkdir(parents=True,exist_ok=True)
    registry_path=folder/'registry.json'
    registry=json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else {}
    for page in (ROOT/'scraped_wiki/html').glob('*.html'):
        if page.name.startswith('fandom'):continue
        soup=BeautifulSoup(page.read_bytes(),'html.parser')
        for image in soup.find_all('img'):
            src=urljoin('http://musicfamily.org/realm/',image.get('src',''))
            if '/Factions/picks/' not in src or not src.lower().endswith('.png'):continue
            filename=Path(urlsplit(src).path).name
            name=image.parent.get_text(' ',strip=True)
            if not name or len(name)>90 or len(name)<3:continue
            # Keep named upgrade icons, not banners/navigation art.
            if any(x in filename.lower() for x in ('toppage','banner','favicon')):continue
            target=folder/filename
            if not target.exists():
                try:
                    data,_=fetch(src,500000);target.write_bytes(data)
                except Exception:continue
            registry[name]={'file':filename,'source_url':src,'source_page':'http://musicfamily.org/realm/'+page.stem+'/',
                            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    write_json(registry_path,registry)
    print('ICON_REGISTRY',len(registry),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--icons',action='store_true');parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--manifest',type=Path,default=ROOT/'data/source_manifest.json')
    parser.add_argument('--max-pages',type=int,default=160)
    args=parser.parse_args()
    (ROOT/'scraped_wiki/html').mkdir(parents=True,exist_ok=True)
    store=KnowledgeStore();import_existing(store)
    print('IMPORTED_EXISTING',json.dumps(store.stats()),flush=True)
    if args.refresh:
        names=['MercBuilds','Mercenary','Factions','FactionUpgrades','Spells','Reincarnation','Research','ResearchList',
               'ResearchBuilds','R16Guide','R40-R46','DragonFaction','QuestArtifacts','UniqueBuilding',
               'GoblinFaction','DruidFaction','TitanFaction','FacelessFaction','ElfFaction','AngelFaction','DemonFaction','UndeadFaction',
               'Heritages','Lineages','Challenges','TrophyGuide','GameWindow','Ascension','R47-R60','R60-R75','R75Plus']
        fandom=['Realm_Grinder_Wiki','Upgrades','Mercenary','Research','Research_Builds','Dragon',
                'Reincarnation','Abdication','Spells','Assistants','Bloodline','Factions','Fairy','Goblin',
                'Druid','Titan','Faceless','Challenges','Trophies','Excavation','Artifacts','Mana','Gems','Buildings','Keyboard_Shortcuts','Lineage']
        specs=[('musicfamily',name,'http://musicfamily.org/realm/'+name+'/') for name in names]
        specs += [('fandom',name,'https://realm-grinder.fandom.com/wiki/'+name) for name in fandom]
        if args.manifest.exists():
            known=json.loads(args.manifest.read_text(encoding='utf-8'))
            listed=[]
            for row in known.get('sources',[]):
                parts=urlsplit(row['source_url'])
                if parts.hostname in ('musicfamily.org','www.musicfamily.org') and parts.path.startswith('/realm/'):
                    listed.append(('musicfamily',row['title'],row['source_url']))
                elif parts.hostname=='realm-grinder.fandom.com' and parts.path.startswith('/wiki/'):
                    listed.append(('fandom',row['title'],row['source_url']))
            if listed:specs=listed
        specs=list({url:(origin,title,url) for origin,title,url in specs}.values())[:max(1,min(500,args.max_pages))]
        with ThreadPoolExecutor(max_workers=max(1,min(3,args.workers))) as pool:
            futures=[pool.submit(collect_page,spec) for spec in specs]
            for future in as_completed(futures):
                result=future.result()
                if result['ok']:
                    store.ingest(result['title'],result['url'],result['text'],origin=result['origin'],
                                 resolved_url=result['resolved'],captured_at=result['captured'],
                                 license='CC-BY-SA unless otherwise noted' if 'fandom' in result['origin'] else 'Source attribution retained')
                    prefix='fandom-' if 'fandom' in result['origin'] else ''
                    (ROOT/'scraped_wiki/html'/(prefix+result['title']+'.html')).write_bytes(result['html'])
                    store.log_fetch(result['url'],'ARCHIVED' if result['captured'] else 'LIVE',result['resolved'])
                    print('SOURCE_OK',result['origin'],result['title'],len(result['text']),flush=True)
                else:
                    store.log_fetch(result['url'],'FAILED',result['error']);print('SOURCE_FAILED',result['url'],result['error'],flush=True)
    if args.icons:download_icons()
    from src.knowledge_service import KnowledgeService
    print('STRUCTURED_COVERAGE',json.dumps(KnowledgeService().rebuild_references(store)),flush=True)
    write_json(ROOT/'state/knowledge_coverage.json',dict(store.stats(),updated_at=time.time()))
    print('FINAL_COVERAGE',json.dumps(store.stats()),flush=True)

if __name__=='__main__':main()
