"""Local source-backed reference index. Retrieved prose is never executable code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

DEFAULT_DB=Path(__file__).resolve().parents[1]/'scraped_wiki/knowledge.sqlite3'
TOKEN=r"(?:[A-Z]{1,2}\d{1,5}|SP:[^,\n]+)"
TEMPLATE=re.compile(r'^'+TOKEN+r'(?:,\s*'+TOKEN+r')+,?$')

def extract_templates(text):
    result=[];pending=''
    for line in text.splitlines()+['']:
        line=line.strip()
        starts=bool(re.match(r'^(?:[A-Z]{1,2}\d|SP:)',line))
        if starts:
            if pending.endswith(','):pending+=line
            else:
                if TEMPLATE.fullmatch(pending):result.append(pending.rstrip(','))
                pending=line
        else:
            if TEMPLATE.fullmatch(pending):result.append(pending.rstrip(','))
            pending=''
    return list(dict.fromkeys(result))

def extract_records(text):
    """Preserve field-labelled source blocks, not guesses about executable conditions."""
    lines=text.splitlines();records=[]
    labels={'requirement','requirements','unlock requirement','cost','effect','formula','alignment','range','note','type'}
    for index,line in enumerate(lines):
        label=line.strip().lower().rstrip(':')
        if label not in labels or index==0:continue
        previous=lines[index-1].strip()
        if not previous or previous.startswith(':') or previous.lower() in labels:continue
        end=min(len(lines),index+28)
        for j in range(index+2,end):
            if (j+1<len(lines) and lines[j+1].strip().lower().rstrip(':') in labels and
                lines[j].strip() and not lines[j].lstrip().startswith(':')):
                end=j;break
        body='\n'.join(lines[index:end]).strip()
        if body:records.append({'name':previous,'text':body,'line':index+1,'execution_status':'REFERENCE_ONLY'})
    return records

class KnowledgeStore:
    def __init__(self,path=DEFAULT_DB):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents(
                    source_url TEXT PRIMARY KEY,title TEXT,text TEXT,origin TEXT,resolved_url TEXT,
                    captured_at TEXT,observed_at REAL,sha256 TEXT,license TEXT);
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(source_url UNINDEXED,title,text);
                CREATE TABLE IF NOT EXISTS records(source_url TEXT,name TEXT,text TEXT,line INTEGER,status TEXT);
                CREATE TABLE IF NOT EXISTS templates(source_url TEXT,template TEXT,UNIQUE(source_url,template));
                CREATE TABLE IF NOT EXISTS fetch_log(url TEXT PRIMARY KEY,status TEXT,detail TEXT,updated_at REAL);
            """)
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL');return db
    def ingest(self,title,source_url,text,origin='musicfamily',resolved_url=None,captured_at=None,license=None):
        if not isinstance(text,str) or not text.strip():raise ValueError('Empty source content')
        source_url=canonical_url(source_url)
        digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?,?,?,?,?)',
                (source_url,title,text,origin,resolved_url or source_url,captured_at,time.time(),digest,license))
            db.execute('DELETE FROM documents_fts WHERE source_url=?',(source_url,))
            db.execute('INSERT INTO documents_fts VALUES(?,?,?)',(source_url,title,text))
            db.execute('DELETE FROM records WHERE source_url=?',(source_url,))
            db.execute('DELETE FROM templates WHERE source_url=?',(source_url,))
            db.executemany('INSERT INTO records VALUES(?,?,?,?,?)',
                [(source_url,r['name'],r['text'],r['line'],r['execution_status']) for r in extract_records(text)])
            db.executemany('INSERT OR IGNORE INTO templates VALUES(?,?)',[(source_url,t) for t in extract_templates(text)])
        return digest
    def log_fetch(self,url,status,detail=''):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO fetch_log VALUES(?,?,?,?)',(url,status,detail,time.time()))
    def search(self,query,limit=8):
        words=re.findall(r'[\w]+',query,flags=re.UNICODE)[:20]
        if not words:return []
        expression=' AND '.join('"'+word+'"' for word in words)
        with self.connect() as db:
            rows=db.execute('SELECT d.* FROM documents_fts f JOIN documents d ON d.source_url=f.source_url '
                'WHERE documents_fts MATCH ? ORDER BY bm25(documents_fts) LIMIT ?',
                (expression,max(1,min(50,int(limit))))).fetchall()
        return [dict(row) for row in rows]
    def stats(self):
        with self.connect() as db:
            result={key:db.execute('SELECT COUNT(*) FROM '+key).fetchone()[0] for key in ('documents','records','templates')}
            result['origins']={row[0]:row[1] for row in db.execute('SELECT origin,COUNT(*) FROM documents GROUP BY origin')}
            result['fetch_status']={row[0]:row[1] for row in db.execute('SELECT status,COUNT(*) FROM fetch_log GROUP BY status')}
        result['record_execution_status']='REFERENCE_ONLY unless separately compiled and tested'
        return result


def canonical_url(url):
    from urllib.parse import urlsplit,urlunsplit
    parts=urlsplit(url);path=parts.path
    if parts.hostname and parts.hostname.lower().endswith('musicfamily.org'):
        path=path.rstrip('/')+'/'
    return urlunsplit((parts.scheme.lower(),parts.netloc.lower(),path,parts.query,''))

def html_text(content):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(content,'html.parser')
    # Template text often lives in input attributes rather than text nodes.
    for node in soup.find_all('input'):
        value=node.get('value','')
        if ',' in value and re.search(r'[A-Z]{1,2}\d',value):
            node.replace_with(soup.new_string('\n'+value+'\n'))
    for node in soup(['script','style','noscript','nav','header','footer']):node.decompose()
    for node in soup.select('#wm-ipp-base,.mw-editsection,.wds-global-navigation,.page-side-tools'):
        node.decompose()
    main=soup.select_one('.mw-parser-output') or soup.find(id='content') or soup.body or soup
    return main.get_text('\n',strip=True)
