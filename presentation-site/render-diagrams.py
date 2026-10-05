from pathlib import Path
import re,textwrap,json,subprocess
R=Path(__file__).resolve().parent.parent
(R/'.presentation-build').mkdir(exist_ok=True)
# Generate every diagram from its owning Mermaid graph; DOT mirrors nodes/edges.
owners={'system-architecture':('docs/02-system-architecture.md',0),'runtime':('docs/02-system-architecture.md',1),'data-flow':('docs/03-data-core.md',0),'improvement-loop':('docs/04-learning-core.md',0),'evaluation':('docs/06-validation-and-roadmap.md',0)}
for name,(owner,idx) in owners.items():
 block=re.findall(r'```mermaid\n(.*?)```',(R/owner).read_text(),re.S)[idx]
 labels={}; edges=[]; clusters={}; active=None
 for raw in block.splitlines():
  line=raw.strip()
  m=re.match(r'subgraph\s+(\w+)\["(.*?)"\]',line)
  if m: active=m[1];clusters[active]={'label':m[2],'nodes':[]};continue
  if line=='end':active=None;continue
  for m in re.finditer(r'(\w+)\s*(?:\["(.*?)"\]|\{"(.*?)"\})',line):
   nid=m[1];labels[nid]=m[2] or m[3]
   if active and nid not in clusters[active]['nodes']:clusters[active]['nodes'].append(nid)
  line=re.sub(r'(\w+)\s*(?:\[".*?"\]|\{".*?"\})',r'\1',line)
  for m in re.finditer(r'(?<!\w)(?=(\w+)\s*-->\s*(?:\|"?([^|]*?)"?\|\s*)?(\w+))',line):edges.append((m[1],m[3],(m[2] or '').strip('"')))
 def dot(themed):
  lines=['digraph G {','graph [rankdir=TB,bgcolor="transparent",pad="0.3",nodesep="0.35",ranksep="0.55",fontname="Arial",fontsize=16];','node [shape=box,style="rounded,filled",fillcolor="white",color="#9cacc0",fontname="Arial",fontsize=14,margin="0.18,0.14"];','edge [color="#70849b",fontname="Arial",fontsize=11,arrowsize=0.7];']
  for k,v in labels.items():
   label='\\n'.join(textwrap.wrap(v,35)); fill='#edf4ff' if themed else '#f6f7f9'; lines.append(f'{k} [label={json.dumps(label,ensure_ascii=False)},fillcolor="{fill}"];'.replace('\\\\n','\\n'))
  for k,v in clusters.items():
   fill='#f2f7ff' if k=='DC' else '#fff4f5';lines.append(f'subgraph cluster_{k} {{ label={json.dumps(v["label"],ensure_ascii=False)}; style="rounded,filled"; color="#c8d4e2"; fillcolor="{fill if themed else "#f6f7f9"}"; '+ '; '.join(v['nodes'])+'; }')
  for a,b,label in edges:lines.append(f'{a} -> {b}'+(f' [label={json.dumps(label,ensure_ascii=False)}]' if label else '')+';')
  lines.append('}');return '\n'.join(lines)+'\n'
 src=R/'.presentation-build'/f'{name}.dot';src.write_text(dot(False));subprocess.run(['dot','-Tsvg',str(src),'-o',str(R/'docs/assets'/f'{name}.svg')],check=True)
 (R/'.presentation-build'/f'{name}.graph.json').write_text(json.dumps({'owner':owner,'nodes':labels,'edges':edges},ensure_ascii=False,indent=2))
