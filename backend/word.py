from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn

def style_document(doc):
    sec=doc.sections[0]
    sec.page_width=Inches(8.5);sec.page_height=Inches(11)
    sec.top_margin=sec.bottom_margin=Inches(.75)
    sec.left_margin=sec.right_margin=Inches(.8)
    for style in doc.styles:
        if style.type != 1: continue
        style.font.name='Microsoft YaHei'
        style.font.color.rgb=RGBColor(0,0,0)
        style.font.underline=False
        style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei')
        for border in list(style.element.iter(qn('w:pBdr'))): border.getparent().remove(border)
    normal=doc.styles['Normal'];normal.font.size=Pt(11)
    normal.paragraph_format.line_spacing=1.15
    normal.paragraph_format.space_after=Pt(6)
    normal.paragraph_format.space_before=Pt(0)
    for name,size in [('Title',22),('Heading 1',15),('Heading 2',12)]:
        s=doc.styles[name];s.font.size=Pt(size)
        s.paragraph_format.space_before=Pt(12 if name!='Title' else 0)
        s.paragraph_format.space_after=Pt(7)
    return doc
