from tools.inspect_installed_metadata import ABC

def sample(body):
    abc=ABC(b'');abc.bodies={0:body};abc.name=lambda index:'field'+str(index)
    return abc

def test_getsuper_has_a_u30_operand():
    result=sample(bytes([4,0x81,1,0x47])).instructions(0)
    assert len(result)==2 and result[0]['args']==[129] and result[1]['op']=='returnvoid'

def test_getouterscope_and_istype_operands_do_not_desynchronize():
    result=sample(bytes([0x67,3,0xb2,2,0x47])).instructions(0)
    assert len(result)==3 and result[0]['args']==[3] and result[1]['args']==[2]
