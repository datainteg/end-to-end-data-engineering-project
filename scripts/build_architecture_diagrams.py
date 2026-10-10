"""Generate editable draw.io pages and matching GitHub SVG previews.

Standard library only. Diagram specifications below are the source of truth.
No network calls: logos are vendored with credits in docs/diagrams/icons/.
"""
import base64
import html
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/diagrams'
ICONS = OUT / 'icons'
SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)
COLORS = {'data':'#167C80','control':'#7555BC','failure':'#C14D32','proposed':'#A66C08'}


def node(id, title, lines, x, y, icon=None, w=320, h=146, color='data', icon2=None):
    return dict(id=id,title=title,lines=lines,x=x,y=y,w=w,h=h,icon=icon,color=color,icon2=icon2)


def edge(source,target,sp='right',tp='left',points=None,color='data',label=None,at=None):
    return dict(source=source,target=target,sp=sp,tp=tp,points=points or [],color=color,label=label,at=at)


def specs():
    return [dict(id='local-reference',title='01 / The working local reference',
        subtitle='VERIFIED LOCALLY  •  Python + SQLite  •  Exact paise arithmetic  •  No cloud dependency',w=1640,h=760,
        nodes=[
            node('fixture','Synthetic fixture',['5 datasets • stable business keys','Orders, lines, attempts, lookups'],60,180,'python'),
            node('raw','Immutable raw attempt',['JSONL + selected file manifest','Batch ID / attempt ID / SHA256'],460,180),
            node('quality','Validate + clean',['Fields, references and duplicates','Reason-coded quality accounting'],860,180,'python'),
            node('db','SQLite warehouse',['Dimensions + separate facts','Ledger + watermarks commit too'],1260,180,'sqlite'),
            node('tests','Failure tests',['Missing file • rollback • writer lock','Conflict • deletion • safe replay'],160,440,'python',w=380,color='failure'),
            node('history','Customer history',['Silver closes; Gold becomes current','Existing sales keep their first key'],630,440,'sqlite',w=380),
            node('metrics','Reconciled business result',['Sales ₹1,200 • 2 paid orders','AOV ₹600 • attempts 2/4 = 50%'],1100,440,w=380),
        ],edges=[edge('fixture','raw'),edge('raw','quality'),edge('quality','db'),
            edge('db','metrics','bottom','top',[(1420,390),(1290,390)]),
            edge('history','metrics'),edge('tests','history',color='failure',label='checks',at=(585,498))],
        footer='Local archive and SQLite behavior are tested. This diagram does not represent Glue or Snowflake execution.'),
    dict(id='cloud-workflow',title='02 / Cloud integration workflow',
        subtitle='CODE SUPPLIED — CLOUD EXECUTION NOT VERIFIED  •  Frozen full snapshots  •  10,000 rows per dataset cap',w=1640,h=1040,
        nodes=[
            node('airflow','Apache Airflow',['Manual trigger + terminal wait'],60,150,'apacheairflow',w=320,h=112,color='control'),
            node('sfn','AWS Step Functions',['Standard workflow • Glue .sync'],460,150,'stepfunctions',w=350,h=112,color='control'),
            node('lock','Amazon DynamoDB',['Non-expiring mutex; failure keeps lock'],920,150,'dynamodb',w=660,h=112,color='control'),
            node('sources','Sources',['PostgreSQL: orders and payments','MongoDB: customer profiles'],60,350,'postgresql',icon2='mongodb'),
            node('extract','AWS Glue extract',['JDBC + MongoDB connection','One job, sequential source reads'],460,350,'glue'),
            node('raw','Amazon S3 / raw',['Immutable JSONL + manifest','Freeze source writers for the demo'],860,350,'s3'),
            node('validate','AWS Lambda',['Selected files, size and checksum','Complete input before transform'],1260,350,'lambda'),
            node('spark','Glue + Spark',['Typed frames • grain-safe join','Quality checks; rejects block load'],1260,600,'apachespark'),
            node('curated','S3 / curated',['Decimal Parquet + file manifest','COPY only selected batch files'],860,600,'s3'),
            node('snowflake','Snowflake',['COPY staging → transaction','Synchronous Glue publisher driver'],460,600,'snowflake'),
            node('bi','Microsoft Power BI',['Published marts → manual refresh','Guide supplied; report not built'],60,600,'powerbi'),
            node('secrets','Secrets Manager + IAM',['Configure TLS, private source routes','Scoped roles; no secrets in payloads'],60,840,'secrets',w=470,h=126,color='control'),
            node('observability','CloudWatch / diagnostics',['Job IDs + SQL query IDs + batch IDs','Account integration remains pending'],585,840,'cloudwatch',w=470,h=126,color='control'),
            node('alerts','Amazon SNS',['Foundation topic supplied','Terminal event rule is not wired'],1110,840,'sns',w=470,h=126,color='control'),
        ],edges=[edge('airflow','sfn',color='control'),edge('sfn','lock',color='control'),
            edge('sfn','extract','bottom','top',color='control'),edge('sources','extract'),edge('extract','raw'),edge('raw','validate'),
            edge('validate','spark','bottom','top'),edge('spark','curated','left','right'),edge('curated','snowflake','left','right'),edge('snowflake','bi','left','right')],
        footer='Solid teal = data path. Dashed purple = control. Step Functions coordinates extract, transform and publish; it does not carry source rows.'),
    dict(id='advanced-roadmap',title='03 / Advanced production design',
        subtitle='PROPOSED — NOT IMPLEMENTED OR BENCHMARKED  •  Prioritize correctness, recovery and measured scaling',w=1640,h=1130,
        nodes=[
            node('schedule','Airflow + Step Functions',['Schedule, dependency and terminal state','Pass IDs / manifest URIs, not row payloads'],60,150,'apacheairflow',w=470,h=126,color='proposed'),
            node('ownership','Safe publication ownership',['Durable owner + query reconciliation','Prove fencing before automatic takeover'],585,150,'dynamodb',w=470,h=126,color='proposed'),
            node('contracts','Release + contract checks',['Schema versions • integration fixtures','Backfill and replay acceptance gates'],1110,150,w=470,h=126,color='proposed'),
            node('delta','Incremental state',['Committed W to U, with overlap','Affected orders + full lookups'],60,380,'postgresql',color='proposed'),
            node('archive','S3 raw archive',['Attempts, counts and provenance','Retention + access policy'],460,380,'s3',color='proposed'),
            node('distributed','Distributed Spark',['Partitioned dedupe, joins and rules','Remove driver collect; test skew'],860,380,'apachespark',color='proposed'),
            node('parquet','Parquet contracts',['Types, manifest, reconciliation','Measure file sizes and partitions'],1260,380,'s3',color='proposed'),
            node('async','SQL submit / poll',['Persist handles; bounded polling','Reconcile before resubmission'],1260,650,'lambda',color='proposed'),
            node('transaction','Snowflake publish',['SCD2, facts, ledger, watermarks','Atomic DML; DDL outside commit'],860,650,'snowflake',color='proposed'),
            node('marts','Governed marts',['Grains, lineage and freshness','Access roles + SQL reconciliation'],460,650,'snowflake',color='proposed'),
            node('report','Power BI',['Refresh after confirmed commit','Report errors do not rerun SQL'],60,650,'powerbi',color='proposed'),
            node('ops','Observability + recovery',['CloudWatch / SNS: stale batch and lock','Alert retry never republishes data'],60,920,'cloudwatch',w=470,h=126,color='proposed'),
            node('security','Security + cost controls',['IAM, Secrets Manager, private routes','Encryption, spend limits and retention'],585,920,'secrets',w=470,h=126,color='proposed'),
            node('cdc','Optional CDC extension',['Only if latency / deletion needs justify it','Offsets, ordering and replay need design'],1110,920,'mongodb',w=470,h=126,color='proposed'),
        ],edges=[edge('schedule','ownership',color='proposed'),edge('ownership','contracts',color='proposed'),
            edge('delta','archive',color='proposed'),edge('archive','distributed',color='proposed'),edge('distributed','parquet',color='proposed'),
            edge('parquet','async','bottom','top',color='proposed'),edge('async','transaction','left','right',color='proposed'),edge('transaction','marts','left','right',color='proposed'),edge('marts','report','left','right',color='proposed')],
        footer='Amber dashed paths = proposed changes. A lease timeout alone is never proof that an earlier warehouse writer stopped.'),
    dict(id='warehouse-model',title='04 / Warehouse grains and relationships',
        subtitle='MODEL IN THE SUPPLIED CODE  •  SQLite tested; Snowflake not executed  •  One-to-many logical relationships',w=1640,h=920,
        nodes=[
            node('date','DIM_DATE',['Key: date_key','One UTC calendar date'],60,190,w=390),
            node('customer','DIM_CUSTOMER',['Key: customer_sk • customer_id repeats','One observed version; one current row'],625,190,w=390),
            node('product','DIM_PRODUCT',['Key: product_id','One product; Type 1 attributes'],1190,190,w=390),
            node('orders','FACT_ORDERS',['Key: order_id • one order','customer_sk + date_key + status'],60,500,w=390),
            node('sales','FACT_SALES',['Key: order_id + line_id • one line','customer_sk + product_id + revenue'],625,500,w=390),
            node('payments','FACT_PAYMENTS',['Key: payment_id • one attempt','order_id + amount + status'],1190,500,w=390),
            node('rules','Protect the meaning of each row',['No direct sales-to-payments join. Sales date comes through its order.','Existing facts keep the customer version assigned at first publication.'],60,745,w=960,h=125),
            node('ledger','Publication controls',['BATCH_LEDGER + WATERMARKS','Commit with dimensions and facts'],1080,745,w=500,h=125,color='control'),
        ],edges=[edge('date','orders','bottom','top',label='1 → many',at=(325,420)),
            edge('customer','sales','bottom','top',label='1 → many',at=(890,420)),
            edge('customer','orders','left','top-right',[(545,263),(545,390),(372,390)]),
            edge('product','sales','bottom','right',[(1385,445),(1080,445),(1080,573)]),
            edge('orders','sales',label='order_id',at=(537,557)),
            edge('orders','payments','bottom','bottom',[(255,690),(1385,690)],label='order_id • 1 → many attempts',at=(820,682))],
        footer='Snowflake standard-table key constraints are not a replacement for deduplication checks and serialized publication.'),
    ]


def point(n, port):
    return {'left':(n['x'],n['y']+n['h']/2),'right':(n['x']+n['w'],n['y']+n['h']/2),
            'top':(n['x']+n['w']/2,n['y']),'top-right':(n['x']+n['w']*.8,n['y']),'bottom':(n['x']+n['w']/2,n['y']+n['h'])}[port]


def icon_file(name):
    files=[p for ext in ['svg','png'] if (p:=ICONS/(name+'.'+ext)).exists()]
    if not files:raise FileNotFoundError(name)
    return files[0]


def svg_text(root,x,y,value,size=17,color='#334155',weight='normal',anchor='start'):
    e=ET.SubElement(root,f'{{{SVG}}}text',{'x':str(x),'y':str(y),'font-family':'DejaVu Sans, Arial, sans-serif',
        'font-size':str(size),'fill':color,'font-weight':weight,'text-anchor':anchor})
    e.text=value


def svg_icon(parent,name,x,y,size,unique):
    p=icon_file(name)
    if p.suffix=='.svg':
        el=ET.fromstring(p.read_bytes())
        # Prefix definitions so repeated brand gradients do not collide.
        ids={n.attrib['id']:unique+'-'+n.attrib['id'] for n in el.iter() if 'id' in n.attrib}
        for n in el.iter():
            for k,v in list(n.attrib.items()):
                if k=='id':n.set(k,ids[v])
                else:
                    for old,new in ids.items():
                        v=v.replace('url(#'+old+')','url(#'+new+')')
                        if v=='#'+old:v='#'+new
                    n.set(k,v)
        if 'viewBox' not in el.attrib:
            el.set('viewBox','0 0 '+re.sub('[^0-9.]','',el.get('width','128'))+' '+re.sub('[^0-9.]','',el.get('height','128')))
        el.set('x',str(x));el.set('y',str(y));el.set('width',str(size));el.set('height',str(size))
        parent.append(el)
    else:
        ET.SubElement(parent,f'{{{SVG}}}image',{'x':str(x),'y':str(y),'width':str(size),'height':str(size),
            'href':'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()})


def render_svg(s):
    root=ET.Element(f'{{{SVG}}}svg',{'width':str(s['w']),'height':str(s['h']),'viewBox':f"0 0 {s['w']} {s['h']}",'role':'img','aria-labelledby':'title desc'})
    ET.SubElement(root,f'{{{SVG}}}title',{'id':'title'}).text=s['title']
    ET.SubElement(root,f'{{{SVG}}}desc',{'id':'desc'}).text=s['subtitle']
    ET.SubElement(root,f'{{{SVG}}}rect',{'width':'100%','height':'100%','fill':'#F5F7FB'})
    defs=ET.SubElement(root,f'{{{SVG}}}defs')
    for name,color in COLORS.items():
        m=ET.SubElement(defs,f'{{{SVG}}}marker',{'id':'arrow-'+name,'viewBox':'0 0 10 10','refX':'9','refY':'5','markerWidth':'7','markerHeight':'7','orient':'auto-start-reverse'})
        ET.SubElement(m,f'{{{SVG}}}path',{'d':'M 0 0 L 10 5 L 0 10 z','fill':color})
    svg_text(root,60, 62,s['title'],32,'#10243A','bold')
    svg_text(root,60,99,s['subtitle'],16,'#52657D')
    lookup={n['id']:n for n in s['nodes']}
    for e in s['edges']:
        pts=[point(lookup[e['source']],e['sp']),*e['points'],point(lookup[e['target']],e['tp'])]
        attrs={'points':' '.join(f'{x},{y}' for x,y in pts),'fill':'none','stroke':COLORS[e['color']],'stroke-width':'2.5','marker-end':'url(#arrow-'+e['color']+')','stroke-linejoin':'round'}
        if e['color']!='data':attrs['stroke-dasharray']='8 5'
        ET.SubElement(root,f'{{{SVG}}}polyline',attrs)
        if e['label']:
            x,y=e['at'];svg_text(root,x,y,e['label'],14,COLORS[e['color']],anchor='middle')
    for n in s['nodes']:
        color=COLORS[n['color']]
        ET.SubElement(root,f'{{{SVG}}}rect',{'x':str(n['x']),'y':str(n['y']),'width':str(n['w']),'height':str(n['h']),'rx':'12','fill':'#FFFFFF','stroke':'#D5DFEA','stroke-width':'1.5'})
        ET.SubElement(root,f'{{{SVG}}}rect',{'x':str(n['x']),'y':str(n['y']+14),'width':'4','height':str(n['h']-28),'rx':'2','fill':color})
        if n['icon']:svg_icon(root,n['icon'],n['x']+18,n['y']+18,44,n['id'])
        if n['icon2']:svg_icon(root,n['icon2'],n['x']+68,n['y']+18,44,n['id']+'-second')
        svg_text(root,n['x']+(128 if n['icon2'] else 78 if n['icon'] else 20),n['y']+43,n['title'],20,'#10243A','bold')
        for i,line in enumerate(n['lines']):svg_text(root,n['x']+20,n['y']+83+i*24,line,16)
    svg_text(root,60,s['h']-28,s['footer'],14,'#52657D')
    ET.ElementTree(root).write(OUT/(s['id']+'.svg'),encoding='utf-8',xml_declaration=True)


def drawio(s,parent):
    page=ET.SubElement(parent,'diagram',{'id':s['id'],'name':s['title']})
    graph=ET.SubElement(page,'mxGraphModel',{'dx':'1800','dy':'1200','grid':'1','gridSize':'10','guides':'1','tooltips':'1','connect':'1','arrows':'1','fold':'1','page':'1','pageScale':'1','pageWidth':str(s['w']),'pageHeight':str(s['h']),'background':'#F5F7FB'})
    cells=ET.SubElement(graph,'root');ET.SubElement(cells,'mxCell',{'id':'0'});ET.SubElement(cells,'mxCell',{'id':'1','parent':'0'})
    def cell(id,value,x,y,w,h,style,parent='1'):
        c=ET.SubElement(cells,'mxCell',{'id':id,'value':value,'style':style,'vertex':'1','parent':parent})
        ET.SubElement(c,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'})
    textstyle='text;html=1;align=left;verticalAlign=middle;whiteSpace=wrap;overflow=hidden;strokeColor=none;fillColor=none;fontFamily=Arial;'
    cell('heading',s['title'],60,27,s['w']-120,48,textstyle+'fontSize=32;fontStyle=1;fontColor=#10243A;')
    cell('subtitle',s['subtitle'],60,78,s['w']-120,30,textstyle+'fontSize=16;fontColor=#52657D;')
    cell('footer',s['footer'],60,s['h']-48,s['w']-120,36,textstyle+'fontSize=14;fontColor=#52657D;')
    for n in s['nodes']:
        cell(n['id'],'',n['x'],n['y'],n['w'],n['h'],'rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor='+COLORS[n['color']]+';strokeWidth=1.5;container=1;collapsible=0;')
        tx=128 if n['icon2'] else 78 if n['icon'] else 20
        cell(n['id']+'-title',html.escape(n['title']),tx,14,n['w']-tx-12,48,textstyle+'fontSize=20;fontStyle=1;fontColor=#10243A;',n['id'])
        cell(n['id']+'-body','<br>'.join(html.escape(t) for t in n['lines']),20,67,n['w']-35,n['h']-67,textstyle+'fontSize=16;fontColor=#334155;verticalAlign=top;',n['id'])
        if n['icon']:
            p=icon_file(n['icon']);mime='image/svg+xml' if p.suffix=='.svg' else 'image/png'
            data=base64.b64encode(p.read_bytes()).decode()
            cell(n['id']+'-icon','',18,18,44,44,'shape=image;verticalLabelPosition=bottom;imageAspect=1;aspect=fixed;image=data:'+mime+','+data+';',n['id'])
        if n['icon2']:
            p=icon_file(n['icon2']);data=base64.b64encode(p.read_bytes()).decode()
            cell(n['id']+'-second-icon','',68,18,44,44,'shape=image;imageAspect=1;aspect=fixed;image=data:image/svg+xml,'+data+';',n['id'])
    ports={'left':(0,.5),'right':(1,.5),'top':(.5,0),'top-right':(.8,0),'bottom':(.5,1)}
    for i,e in enumerate(s['edges']):
        sx,sy=ports[e['sp']];tx,ty=ports[e['tp']]
        style=f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeWidth=2;strokeColor={COLORS[e['color']]};fontSize=14;fontColor={COLORS[e['color']]};exitX={sx};exitY={sy};exitDx=0;exitDy=0;entryX={tx};entryY={ty};entryDx=0;entryDy=0;"
        if e['color']!='data':style+='dashed=1;'
        c=ET.SubElement(cells,'mxCell',{'id':'edge-'+str(i),'value':e['label'] or '','style':style,'edge':'1','parent':'1','source':e['source'],'target':e['target']})
        geo=ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
        if e['points']:
            array=ET.SubElement(geo,'Array',{'as':'points'})
            for x,y in e['points']:ET.SubElement(array,'mxPoint',{'x':str(x),'y':str(y)})


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    mx=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device','compressed':'false','version':'26.0.0'})
    for s in specs():
        render_svg(s);drawio(s,mx)
    ET.indent(mx)
    ET.ElementTree(mx).write(OUT/'ecommerce-architecture.drawio',encoding='utf-8',xml_declaration=True)
    print('Generated 4 editable draw.io pages and 4 SVG previews.')


if __name__=='__main__':main()
