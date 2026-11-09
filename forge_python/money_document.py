"""Create a historical source-note PDF texture, not a rendered animation frame."""
from reportlab.pdfgen import canvas
import pymupdf

def create_money_document(path):
    pdf=path.with_suffix('.pdf');c=canvas.Canvas(str(pdf),pagesize=(760,980))
    c.setFillColorRGB(.98,.965,.93);c.rect(0,0,760,980,fill=1,stroke=0)
    c.setFillColorRGB(.28,.25,.28);c.setFont('Helvetica',18);c.drawString(78,900,'SOURCE NOTES  /  MONETARY HISTORY')
    c.setStrokeColorRGB(.67,.63,.60);c.line(78,875,682,875)
    c.setFillColorRGB(.1,.09,.11);c.setFont('Helvetica-Bold',48);c.drawString(78,792,'The gold window')
    c.setFont('Helvetica',26);c.setFillColorRGB(.25,.23,.25)
    lines=['August 1971 marked a turning point', 'in the international monetary system.', 'Foreign official conversion changed.', '', 'REDEEMABLE IN GOLD', '', 'Gold did not disappear from the world.', 'In 2022, the US dollar was on one side', 'of about 88 percent of foreign-exchange', 'trades, according to the BIS survey.']
    for i,line in enumerate(lines):c.drawString(78,720-i*38,line)
    c.setFont('Helvetica',16);c.drawString(78,160,'SOURCES  /  FEDERAL RESERVE HISTORY + BIS 2022');c.showPage();c.save()
    doc=pymupdf.open(str(pdf));doc[0].get_pixmap(alpha=False).save(str(path));doc.close()
    return pdf,{'x1':78,'x2':560,'y':402}
