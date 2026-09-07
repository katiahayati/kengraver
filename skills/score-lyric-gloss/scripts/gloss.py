"""Add source-order, non-sung text glosses to one MusicXML lyric stream."""
import argparse
from collections import Counter
from fractions import Fraction as F
import json
from pathlib import Path
import xml.etree.ElementTree as E


def words(root, part_id, verse='1'):
    part=root.find(f"part[@id='{part_id}']")
    if part is None:raise ValueError(f'No part {part_id}')
    result=[];current=None;voice_id=None;divisions=1
    for measure in part.findall('measure'):
        divisions=int(measure.findtext('attributes/divisions',str(divisions)))
        cursor=F(0);last=F(0);last_lyric_onset=None
        for n in measure:
            if n.tag in ('backup','forward'):cursor+=(-1 if n.tag=='backup' else 1)*F(n.findtext('duration'))/divisions
            if n.tag!='note':continue
            onset=last if n.find('chord') is not None else cursor
            if n.find('chord') is None:last=cursor;cursor+=F(n.findtext('duration','0'))/divisions
            selected=[l for l in n.findall('lyric') if l.get('number','1')==verse and l.find('text') is not None]
            if len(selected)>1:raise ValueError('Multiple syllables at one anchor: review original underlay first')
            for lyric in selected:
                if last_lyric_onset is not None and onset<=last_lyric_onset:
                    raise ValueError('Overlapping or out-of-order lyric anchors; isolate a single stream')
                last_lyric_onset=onset
                voice=n.findtext('voice','1')
                if voice_id is not None and voice!=voice_id:raise ValueError('Multiple lyric voices; isolate a single stream')
                voice_id=voice
                text=''.join(t.text or '' for t in lyric.findall('text'))
                if not text.strip() or len(lyric.findall('text'))!=1:
                    raise ValueError('Empty or elided lyric; review word segmentation explicitly')
                syllabic=lyric.findtext('syllabic','single')
                if syllabic not in ('single','begin','middle','end'):raise ValueError('Unknown syllabic value')
                if syllabic in ('single','begin'):
                    if current is not None:raise ValueError('Broken word connection: previous word is unclosed')
                    current=dict(source=text,measure=measure.get('number'),onset=str(onset),staff=n.findtext('staff','1'),voice=voice,node=n,parent=measure)
                    result.append(current)
                else:
                    if current is None:raise ValueError('Word continuation without start')
                    current['source']+=text
                if syllabic in ('single','end'):current=None
    if current is not None:raise ValueError('Truncated final lyric word')
    return result


def annotate(source, mapping, output):
    if source.resolve()==output.resolve():raise ValueError('Preserve the input; choose a separate output')
    root=E.parse(source).getroot()
    if any(w.get('id','').startswith('gloss-') for w in root.findall('.//words')):raise ValueError('Input already has gloss annotations')
    stream=words(root,mapping['part'],str(mapping.get('verse','1')));pos=0
    if not stream:raise ValueError('Selected part/verse has no lyric words')
    appearance=mapping.get('appearance',{})
    allowed={'color','font_size','font_style','placement','default_y'}
    if set(appearance)-allowed:raise ValueError('Unknown appearance setting')
    placement=appearance.get('placement','below')
    if placement not in ('above','below'):raise ValueError('Placement must be above or below')
    for index,unit in enumerate(mapping['units']):
        if not unit['source'].strip():raise ValueError('Empty source word group')
        begin=pos;joined=''
        while pos<len(stream) and len(joined)<len(unit['source']):
            joined+=' ' if joined else '';joined+=stream[pos]['source'];pos+=1
        if joined!=unit['source']:raise ValueError(f'Unit {index}: expected {unit["source"]!r}, found {joined!r}')
        if not unit['text'].strip():raise ValueError('Empty gloss')
        anchor=stream[begin];direction=E.Element('direction',placement=placement)
        attrs={'id':f'gloss-{index+1:03}', 'font-style':appearance.get('font_style','normal'),
               'font-size':str(appearance.get('font_size',8)), 'justify':'left', 'halign':'left',
               'default-y':str(appearance.get('default_y',-75 if placement=='below' else 30))}
        if 'color' in appearance:attrs['color']=appearance['color']
        E.SubElement(E.SubElement(direction,'direction-type'),'words',attrs).text=unit['text']
        E.SubElement(direction,'voice').text=anchor['voice'];E.SubElement(direction,'staff').text=anchor['staff']
        # In a monophonic stream, document position immediately before the note
        # is its musical onset. Chord-attached lyrics need explicit handling.
        if anchor['node'].find('chord') is not None:raise ValueError('Chord-member lyric anchor requires an explicit offset adapter')
        anchor['parent'].insert(list(anchor['parent']).index(anchor['node']),direction)
    if pos!=len(stream):raise ValueError(f'Untranslated words remain: {len(stream)-pos}')
    E.indent(root,space='  ');output.parent.mkdir(parents=True,exist_ok=True)
    E.ElementTree(root).write(output,encoding='utf-8',xml_declaration=True)
    return dict(words=len(stream),gloss_units=len(mapping['units']),output=str(output))


def text_inventory(path):
    root=E.parse(path).getroot();rows=[]
    for part in root.findall('part'):
        divisions=1
        for m in part.findall('measure'):
            divisions=int(m.findtext('attributes/divisions',str(divisions)));cursor=F(0)
            for n in m:
                if n.tag in ('backup','forward'):cursor+=(-1 if n.tag=='backup' else 1)*F(n.findtext('duration'))/divisions
                elif n.tag=='note' and n.find('chord') is None:cursor+=F(n.findtext('duration','0'))/divisions
                elif n.tag=='direction':
                    at=cursor+F(n.findtext('offset','0'))/divisions
                    for w in n.findall('direction-type/words'):
                        rows.append((part.get('id'),m.get('number'),str(at),n.findtext('staff','1'),w.text or '',w.get('color','#000000').upper(),w.get('font-style','normal')))
    return rows


def check(before,after):
    gloss_count=sum(w.get('id','').startswith('gloss-') for w in E.parse(before).findall('.//words'))
    if not gloss_count:raise ValueError('Before file has no generated gloss IDs; use the original annotated MusicXML')
    # Importers may drop IDs. Compare every text direction, not only colored
    # words, so black/default-color glosses and duplicate annotations are checked.
    expected=Counter(text_inventory(before));actual=Counter(text_inventory(after))
    missing=list((expected-actual).elements());extra=list((actual-expected).elements())
    return dict(status='pass' if not missing and not extra else 'FAIL',checked_glosses=gloss_count,
                checked_text_directions=sum(expected.values()),missing=missing,extra=extra,
                visual_review='not established; inspect placement and collisions separately')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    inv=sub.add_parser('inventory');inv.add_argument('score',type=Path);inv.add_argument('--part',required=True);inv.add_argument('--verse',default='1')
    add=sub.add_parser('apply');add.add_argument('score',type=Path);add.add_argument('mapping',type=Path);add.add_argument('--out',type=Path,required=True)
    chk=sub.add_parser('check');chk.add_argument('before',type=Path);chk.add_argument('after',type=Path)
    args=p.parse_args()
    if args.command=='inventory':result=[{k:v for k,v in w.items() if k not in ('node','parent')} for w in words(E.parse(args.score).getroot(),args.part,args.verse)]
    elif args.command=='apply':result=annotate(args.score,json.loads(args.mapping.read_text()),args.out)
    else:result=check(args.before,args.after)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if isinstance(result,dict) and result.get('status')=='FAIL':raise SystemExit(1)
