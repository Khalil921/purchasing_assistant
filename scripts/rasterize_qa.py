from pathlib import Path
import fitz
from PIL import Image, ImageDraw

root=Path('test-results')
thumbs=[]
for pdf in root.rglob('*.pdf'):
    if pdf.name=='demo-report.pdf': continue
    doc=fitz.open(pdf)
    folder=pdf.with_suffix('');folder.mkdir(exist_ok=True)
    for n,p in enumerate(doc):
        pix=p.get_pixmap(matrix=fitz.Matrix(1.2,1.2))
        dest=folder/f'page-{n+1}.png';pix.save(dest)
        im=Image.open(dest).convert('RGB');im.thumbnail((306,420))
        tile=Image.new('RGB',(326,456),'#e8eeee');tile.paste(im,((326-im.width)//2,25));ImageDraw.Draw(tile).text((8,6),f'{pdf.parent.name}/{pdf.stem} p{n+1}',fill='black');thumbs.append(tile)
    print(f'{pdf}: {len(doc)} pages')
canvas=Image.new('RGB',(326*4,456*((len(thumbs)+3)//4)),'white')
for n,im in enumerate(thumbs):canvas.paste(im,((n%4)*326,(n//4)*456))
canvas.save(root/'document-contact.png')
