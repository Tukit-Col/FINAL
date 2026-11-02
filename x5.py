import docx,re
from lxml import etree
d=docx.Document('/tmp/s6/VFP_ISIS2610G19_v3.docx')
b=d.element.body
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
t=b[86]
s=etree.tostring(t.find(W+'tblPr')).decode(); print(re.sub(r'xmlns:\w+="[^"]+"\s*','',s))
s=etree.tostring(t.find(W+'tblGrid')).decode(); print(re.sub(r'xmlns:\w+="[^"]+"\s*','',s))
tr=t.findall(W+'tr')
s=etree.tostring(tr[0]).decode(); print(re.sub(r'xmlns:\w+="[^"]+"\s*','',s)[:2500])
s=etree.tostring(tr[1]).decode(); print(re.sub(r'xmlns:\w+="[^"]+"\s*','',s)[:2500])
