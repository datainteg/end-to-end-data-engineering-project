"""Build self-contained GitHub README artwork; standard library, offline."""
from pathlib import Path
import xml.etree.ElementTree as ET
try:
    from .build_architecture_diagrams import svg_icon, svg_text, SVG
except ImportError:
    from build_architecture_diagrams import svg_icon, svg_text, SVG

OUT = Path(__file__).resolve().parents[1] / 'docs/media'


def rect(root,x,y,w,h,fill,rx=16,stroke=None):
    attrs=dict(x=str(x),y=str(y),width=str(w),height=str(h),rx=str(rx),fill=fill)
    if stroke:attrs['stroke']=stroke
    return ET.SubElement(root,f'{{{SVG}}}rect',attrs)


def canvas(w,h,title):
    root=ET.Element(f'{{{SVG}}}svg',{'viewBox':f'0 0 {w} {h}','width':str(w),'height':str(h),'role':'img'})
    ET.SubElement(root,f'{{{SVG}}}title').text=title
    return root


def save(name,root):
    ET.ElementTree(root).write(OUT/name,encoding='utf-8',xml_declaration=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r=canvas(1440,540,'End-to-end data engineering: build, understand, explain. Synthetic e-commerce pipeline.')
    defs=ET.SubElement(r,f'{{{SVG}}}defs')
    g=ET.SubElement(defs,f'{{{SVG}}}linearGradient',{'id':'hero','x1':'0','y1':'0','x2':'1','y2':'1'})
    ET.SubElement(g,f'{{{SVG}}}stop',{'offset':'0','stop-color':'#08172E'})
    ET.SubElement(g,f'{{{SVG}}}stop',{'offset':'1','stop-color':'#202348'})
    rect(r,0,0,1440,540,'url(#hero)',24)
    for x in range(32,1440,32):
        for y in range(28,540,32):
            ET.SubElement(r,f'{{{SVG}}}circle',{'cx':str(x),'cy':str(y),'r':'1','fill':'#B8CEF7','opacity':'.08'})
    rect(r,56,48,252,31,'#173C4D',15)
    svg_text(r,72,69,'DATAINTEG  /  PROJECT LAB',13,'#6EE7D0','bold')
    svg_text(r,56,147,'END-TO-END',57,'#FFFFFF','bold')
    svg_text(r,56,214,'DATA ENGINEERING',57,'#FFFFFF','bold')
    svg_text(r,58,267,'Build it. Understand it. Explain it.',26,'#A7BFFF')
    svg_text(r,58,311,'An e-commerce batch pipeline with replay,',20,'#CBD5E8')
    svg_text(r,58,343,'customer history and failure recovery.',20,'#CBD5E8')
    for x,label,col,width in [(56,'RUNNABLE LOCAL LAB','#69E4CE',232),(306,'CLOUD INTEGRATION CODE','#B4A7FF',286)]:
        rect(r,x,389,width,38,'#172E48',9,stroke='#34465F')
        svg_text(r,x+15,414,label,14,col,'bold')
    # Compact visual summary, not a second detailed architecture.
    stages=[(864,115,'postgresql','SOURCES','#60C9F1'),(1134,115,'s3','RAW FILES','#8FD68C'),
            (864,290,'apachespark','TRANSFORM','#F7AB72'),(1134,290,'snowflake','PUBLISH','#B7ACFF')]
    for x,y,icon,label,col in stages:
        rect(r,x,y,212,125,'#F8FAFF',15)
        rect(r,x,y+110,212,15,col,0)
        svg_icon(r,icon,x+20,y+20,45,icon+'-hero')
        svg_text(r,x+20,y+94,label,16,'#10243A','bold')
    for pts in ['1078,172 1120,172','1240,241 1240,267 970,267 970,279','1078,352 1120,352']:
        ET.SubElement(r,f'{{{SVG}}}polyline',{'points':pts,'fill':'none','stroke':'#82E4E2','stroke-width':'3'})
    for x,y in [(1120,172),(970,279),(1120,352)]:
        ET.SubElement(r,f'{{{SVG}}}circle',{'cx':str(x),'cy':str(y),'r':'4','fill':'#82E4E2'})
    svg_text(r,57,493,'PYTHON  /  SQL  /  AWS GLUE  /  SNOWFLAKE  /  AIRFLOW',14,'#99AAC6','bold')
    svg_text(r,864,480,'SYNTHETIC DATA  •  REPRODUCIBLE LEARNING',13,'#A8B9D4')
    save('hero.svg',r)

    cards=[('start','01','RUN THE PROJECT','Setup → baseline → replay','Start with Python. No cloud account.','#0F766E','#ECFDF5','python'),
           ('design','02','EXPLORE THE DESIGN','Architecture → code → trade-offs','Follow an order across every boundary.','#6D28D9','#F5F3FF','apachespark'),
           ('interview','03','PREPARE & EXPLAIN','45 questions + 12 scenarios','Practice answers with code evidence.','#C2410C','#FFF7ED','snowflake')]
    for name,num,title,line1,line2,color,bg,icon in cards:
        r=canvas(460,212,title+'. '+line1)
        rect(r,1,1,458,210,bg,16,stroke='#D4DDEB')
        rect(r,22,22,46,31,color,8)
        svg_text(r,45,44,num,16,'#FFFFFF','bold',anchor='middle')
        svg_icon(r,icon,384,20,45,name)
        svg_text(r,24,94,title,22,'#16253D','bold')
        svg_text(r,24,133,line1,19,color,'bold')
        svg_text(r,24,168,line2,17,'#475569')
        svg_text(r,407,191,'→',24,color,'bold')
        save('nav-'+name+'.svg',r)

    r=canvas(1440,150,'Synthetic baseline: net sales 1200 rupees, 2 paid orders, AOV 600 rupees, payment attempt success 50 percent.')
    for i,(value,label,sub,color) in enumerate([('₹1,200','DEMO NET SALES','900 + 300, cancelled excluded','#0F766E'),('2','PAID ORDERS','One row per paid order','#2563EB'),('₹600','AVERAGE ORDER VALUE','Net sales / paid orders','#7C3AED'),('50%','PAYMENT SUCCESS','2 successful / 4 attempts','#C2410C')]):
        x=i*360;rect(r,x+3,2,348,146,'#F5F7FC',14,stroke='#E0E7F0')
        rect(r,x+3,20,4,107,color,2)
        svg_text(r,x+25,36,label,13,color,'bold')
        svg_text(r,x+25,91,value,43,'#12243A','bold')
        svg_text(r,x+25,124,sub,15,'#526177')
    save('baseline.svg',r)
    print('Built hero, three navigation cards, and baseline metric strip.')


if __name__=='__main__':main()
