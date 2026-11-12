"""Export this deck's native text, tables and screenshot from OOXML to a compact PDF."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from io import BytesIO
import posixpath
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader
import sys

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'output/NetGuard_Nhom8_Final.pptx'
OUT=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'output/pdf/NetGuard_Nhom8.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
U=12700
pdfmetrics.registerFont(TTFont('Arial',r'C:\Windows\Fonts\arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold',r'C:\Windows\Fonts\arialbd.ttf'))

def color(e,default='#17243B'):
    n=e.find('./a:solidFill/a:srgbClr',NS) if e is not None else None
    return '#'+n.get('val') if n is not None else default

def frame(e):
    x=e.find('a:off',NS);z=e.find('a:ext',NS)
    return tuple(float(n)/U for n in (x.get('x'),x.get('y'),z.get('cx'),z.get('cy')))

def lines_for(body,width):
    output=[]
    for para in body.findall('a:p',NS):
        prop=para.find('a:pPr',NS)
        style=para.find('.//a:rPr',NS)
        if style is None: style=para.find('./a:pPr/a:defRPr',NS)
        size=float(style.get('sz','2100'))/100 if style is not None else 21
        font='Arial-Bold' if style is not None and style.get('b')=='1' else 'Arial'
        fill=color(style)
        align=prop.get('algn','l') if prop is not None else 'l'
        value=''.join(('\n' if n.tag.endswith('}br') else ''.join(n.itertext()) if n.tag.endswith('}t') else '') for n in para.iter() if n.tag.endswith('}t') or n.tag.endswith('}br'))
        wrapped=[]
        for hard in value.split('\n'):
            cur=''
            for word in hard.split():
                test=(cur+' '+word).strip()
                if cur and pdfmetrics.stringWidth(test,font,size)>width:
                    wrapped.append(cur);cur=word
                else:cur=test
            wrapped.append(cur)
        for line in wrapped:output.append((line,font,size,fill,align))
    return output

def draw_body(c,body,x,y,w,h,insets=(0,0,0,0),middle=False):
    left,right,top,bottom=insets
    ls=lines_for(body,w-left-right)
    total=sum(z[2]*1.2 for z in ls)
    yy=y+top+(max(0,(h-top-bottom-total)/2) if middle else 0)
    for value,font,size,fill,align in ls:
        c.setFont(font,size);c.setFillColor(HexColor(fill))
        baseline=540-yy-size*.97
        if align=='r':c.drawRightString(x+w-right,baseline,value)
        elif align=='ctr':c.drawCentredString(x+left+(w-left-right)/2,baseline,value)
        else:c.drawString(x+left,baseline,value)
        yy+=size*1.2

with ZipFile(SOURCE) as z:
    c=canvas.Canvas(str(OUT),pagesize=(960,540),pageCompression=1)
    c.setTitle('NetGuard - Nhom 8')
    c.setAuthor('Nhom 8')
    for num in range(1,13):
        slide=ET.fromstring(z.read(f'ppt/slides/slide{num}.xml'))
        relations={}
        relname=f'ppt/slides/_rels/slide{num}.xml.rels'
        if relname in z.namelist():
            for rel in ET.fromstring(z.read(relname)):
                relations[rel.get('Id')]=posixpath.normpath(posixpath.join('ppt/slides',rel.get('Target'))).lstrip('/')
        tree=slide.find('p:cSld/p:spTree',NS)
        for e in tree:
            kind=e.tag.rsplit('}',1)[-1]
            if kind=='sp':
                xfrm=e.find('p:spPr/a:xfrm',NS);body=e.find('p:txBody',NS)
                if xfrm is None:continue
                x,y,w,h=frame(xfrm)
                sppr=e.find('p:spPr',NS)
                if sppr.find('a:solidFill/a:srgbClr',NS) is not None:
                    c.setFillColor(HexColor(color(sppr)))
                    c.rect(x,540-y-h,w,h,stroke=0,fill=1)
                if body is None:continue
                bp=body.find('a:bodyPr',NS)
                ins=tuple(float(bp.get(k,'0'))/U for k in ('lIns','rIns','tIns','bIns')) if bp is not None else (0,0,0,0)
                draw_body(c,body,x,y,w,h,ins)
            elif kind=='graphicFrame':
                tbl=e.find('.//a:tbl',NS)
                if tbl is None:continue
                x,y,_,_=frame(e.find('p:xfrm',NS))
                widths=[float(a.get('w'))/U for a in tbl.findall('a:tblGrid/a:gridCol',NS)]
                yy=y
                for row in tbl.findall('a:tr',NS):
                    h=float(row.get('h'))/U;xx=x
                    for j,cell in enumerate(row.findall('a:tc',NS)):
                        w=widths[j];pr=cell.find('a:tcPr',NS)
                        c.setFillColor(HexColor(color(pr,'#FFFFFF')))
                        c.setStrokeColor(HexColor('#DDE5EF'));c.setLineWidth(.6)
                        c.rect(xx,540-yy-h,w,h,stroke=1,fill=1)
                        ins=tuple(float(pr.get(k,'0'))/U for k in ('marL','marR','marT','marB'))
                        draw_body(c,cell.find('a:txBody',NS),xx,yy,w,h,ins,pr.get('anchor')=='ctr')
                        xx+=w
                    yy+=h
            elif kind=='pic':
                x,y,w,h=frame(e.find('p:spPr/a:xfrm',NS))
                ref=e.find('p:blipFill/a:blip',NS).get('{'+NS['r']+'}embed')
                data=z.read(relations[ref])
                c.drawImage(ImageReader(BytesIO(data)),x,540-y-h,w,h,preserveAspectRatio=True,anchor='c',mask='auto')
        c.showPage()
    c.save()
reader=PdfReader(OUT)
assert len(reader.pages)==12
assert 'NetGuard' in reader.pages[0].extract_text()
assert '65/65' in reader.pages[9].extract_text()
assert OUT.stat().st_size<1_000_000
print(f'PDF: {len(reader.pages)} pages, {OUT.stat().st_size} bytes, selectable text')
