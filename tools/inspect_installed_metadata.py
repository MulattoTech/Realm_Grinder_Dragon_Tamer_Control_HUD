"""Read-only installed SWF metadata inspection. Does not execute or modify game code."""
from pathlib import Path
import json,struct,zlib
ROOT=Path(__file__).resolve().parents[1]

class ABC:
    def __init__(self,data):self.data=data;self.p=0
    def take(self,n):
        if n<0 or self.p+n>len(self.data):raise ValueError('Truncated ABC')
        result=self.data[self.p:self.p+n];self.p+=n;return result
    def byte(self):return self.take(1)[0]
    def u(self):
        result=0
        for i in range(5):
            b=self.byte();result|=(b&127)<<(7*i)
            if b<128:return result
        return result
    def pool(self,reader):return [None]+[reader() for _ in range(max(0,self.u()-1))]
    def parse(self):
        self.version=struct.unpack('<HH',self.take(4))
        self.ints=self.pool(self.u);self.uints=self.pool(self.u)
        self.doubles=self.pool(lambda:struct.unpack('<d',self.take(8))[0])
        self.strings=['']+[self.take(self.u()).decode('utf-8',errors='replace') for _ in range(max(0,self.u()-1))]
        self.ns=self.pool(lambda:(self.byte(),self.u()))
        self.sets=self.pool(lambda:[self.u() for _ in range(self.u())])
        self.names=[None]
        for _ in range(max(0,self.u()-1)):
            kind=self.byte()
            if kind in (7,13):value=(kind,self.u(),self.u())
            elif kind in (15,16):value=(kind,self.u())
            elif kind in (17,18):value=(kind,)
            elif kind in (9,14):value=(kind,self.u(),self.u())
            elif kind in (27,28):value=(kind,self.u())
            elif kind==29:
                base=self.u();value=(kind,base,[self.u() for _ in range(self.u())])
            else:raise ValueError('Unsupported multiname kind '+str(kind))
            self.names.append(value)
        self.methods=[]
        for _ in range(self.u()):
            count=self.u();ret=self.u();params=[self.u() for _ in range(count)]
            name=self.u();flags=self.byte()
            if flags&8:
                for _ in range(self.u()):self.u();self.byte()
            if flags&128:
                for _ in range(count):self.u()
            self.methods.append({'name':self.strings[name],'return_type':ret,'params':params,'flags':flags})
        for _ in range(self.u()):
            self.u();count=self.u()
            for _ in range(count*2):self.u()
        count=self.u();self.instances=[]
        for _ in range(count):
            name=self.u();parent=self.u();flags=self.byte()
            if flags&8:self.u()
            interfaces=[self.u() for _ in range(self.u())]
            init=self.u();traits=self.traits()
            self.instances.append({'name':self.name(name),'parent':self.name(parent),'init':init,'traits':traits})
        self.classes=[]
        for _ in range(count):self.classes.append({'init':self.u(),'traits':self.traits()})
        for _ in range(self.u()):self.u();self.traits()
        self.bodies={}
        for _ in range(self.u()):
            index=self.u();limits=[self.u() for _ in range(4)];code=self.take(self.u())
            for _ in range(self.u()):
                for _ in range(5):self.u()
            traits=self.traits();self.bodies[index]=code
        if self.p!=len(self.data):raise ValueError('Unparsed bytes at end of ABC')
        return self
    def name(self,index):
        if not index:return '*'
        item=self.names[index]
        if item[0] in (7,13):
            namespace=self.strings[self.ns[item[1]][1]] if item[1] else ''
            return namespace+':'+self.strings[item[2]]
        if item[0] in (9,14,15,16):return self.strings[item[1]]
        return repr(item)
    def traits(self):
        result=[]
        for _ in range(self.u()):
            name=self.u();flags=self.byte();kind=flags&15
            item={'name':self.name(name),'kind':kind}
            if kind in (0,6):
                item.update(slot=self.u(),type=self.name(self.u()))
                value=self.u();item['value_index']=value
                if value:item['value_kind']=self.byte()
            elif kind in (1,2,3):item.update(dispatch=self.u(),method=self.u())
            elif kind in (4,5):item.update(slot=self.u(),target=self.u())
            else:raise ValueError('Unsupported trait kind '+str(kind))
            if flags&64:
                for _ in range(self.u()):self.u()
            result.append(item)
        return result
    def instructions(self,index):
        code=self.bodies.get(index,b'');r=ABC(code);output=[]
        names={0x24:'pushbyte',0x25:'pushshort',0x2c:'pushstring',0x2d:'pushint',0x2e:'pushuint',0x2f:'pushdouble',
         0x30:'pushscope',0x49:'constructsuper',0x60:'getlex',0x66:'getproperty',0x68:'initproperty',0x61:'setproperty',
         0x46:'callproperty',0x4f:'callpropvoid',0x47:'returnvoid',0x48:'returnvalue',0xd0:'getlocal0',0xd1:'getlocal1',
         0xd2:'getlocal2',0xd3:'getlocal3',0x26:'pushtrue',0x27:'pushfalse',0x20:'pushnull',0x21:'pushundefined'}
        single={0x04,0x05,0x06,0x22,0x54,0x67,0xb2,0x08,0x25,0x2c,0x2d,0x2e,0x2f,0x31,0x40,0x41,0x42,0x49,0x53,0x55,0x56,0x58,0x59,0x5a,
                0x5d,0x5e,0x5f,0x60,0x61,0x62,0x63,0x66,0x68,0x6a,0x6c,0x6d,0x6e,0x6f,0x80,0x86,0x92,0x94,0xc2,0xc3,0xf0,0xf1}
        double={0x32,0x43,0x44,0x45,0x46,0x4a,0x4b,0x4c,0x4e,0x4f}
        multiname_ops={0x04,0x05,0xb2,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86}
        while r.p<len(code):
            start=r.p;op=r.byte();args=[]
            if op==0x24:args=[struct.unpack('b',r.take(1))[0]]
            elif op in single:args=[r.u()]
            elif op in double:args=[r.u(),r.u()]
            elif 0x0c<=op<=0x1a:args=[int.from_bytes(r.take(3),'little',signed=True)]
            elif op==0x1b:
                default=r.take(3);count=r.u();args=[default.hex(),[r.take(3).hex() for _ in range(count+1)]]
            elif op==0x65:args=[r.byte()]
            elif op==0xef:args=[r.byte(),r.u(),r.byte(),r.u()]
            resolved=None
            if args:
                if op==0x2c:resolved=self.strings[args[0]]
                elif op==0x2d:resolved=self.ints[args[0]]
                elif op==0x2e:resolved=self.uints[args[0]]
                elif op==0x2f:resolved=self.doubles[args[0]]
                elif op in multiname_ops:resolved=self.name(args[0])
            output.append({'offset':start,'op':names.get(op,hex(op)),'args':args,'resolved':resolved})
        return output

def from_swf(path):
    raw=Path(path).read_bytes();data=zlib.decompress(raw[8:]) if raw[:3]==b'CWS' else raw[8:]
    p=(5+4*(data[0]>>3)+7)//8+4
    while p<len(data):
        header=struct.unpack_from('<H',data,p)[0];p+=2;kind,size=header>>6,header&63
        if size==63:size=struct.unpack_from('<I',data,p)[0];p+=4
        body=data[p:p+size];p+=size
        if kind==82:
            start=body.index(0,4)+1
            yield ABC(body[start:]).parse()

if __name__=='__main__':
    game=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Realm Grinder\RealmGrinderDesktop.swf')
    reports=[]
    for abc in from_swf(game):
        print('ABC_PARSED',abc.version,len(abc.instances),len(abc.methods),flush=True)
        for item in abc.instances:
            if any(term in item['name'].lower() for term in ('stoic','gempower','gemupgrade','manamanager','game','player','manapanel')):
                report=dict(item,constructor=abc.instructions(item['init']))
                reports.append(report)
                print('CLASS',item['name'],'TRAITS',[(t['name'],t.get('type'),t.get('method')) for t in item['traits'][:35]],flush=True)
                if 'stoic' in item['name'].lower():print('STOIC_CONSTRUCTOR',json.dumps(report['constructor']),flush=True)
    (ROOT/'state/installed-class-metadata.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
