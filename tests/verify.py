# SPDX-License-Identifier: MIT
"""Focused standard-library verification; captures stay inside the repository."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]


def decode(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'PNG signature'
    pos, chunks, payload = 8, [], b''
    w = h = 0
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        kind = data[pos+4:pos+8]
        body = data[pos+8:pos+8+length]
        crc = struct.unpack('>I', data[pos+8+length:pos+12+length])[0]
        assert crc == zlib.crc32(kind+body)&0xffffffff, 'CRC'
        chunks.append(kind)
        if kind == b'IHDR':
            w,h,depth,color,compression,filtering,interlace = struct.unpack('>IIBBBBB',body)
            assert (depth,color,compression,filtering,interlace) == (8,2,0,0,0)
        if kind == b'IDAT':
            payload += body
        if kind == b'IEND':
            assert not body
        pos += length+12
    assert chunks == [b'IHDR',b'IDAT',b'IEND'] and pos == len(data)
    assert 0 < w <= 1024 and 0 < h <= 1024 and len(data) <= 1048576
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(payload)+decompressor.flush()
    assert decompressor.eof and not decompressor.unused_data
    assert len(raw) == h*(1+w*3)
    assert all(raw[y*(1+w*3)] == 0 for y in range(h))
    return w,h,raw


def guarded(target, default):
    target = Path(target).resolve()
    target.mkdir(exist_ok=True)
    os.environ.pop('MAKEFUN_OUTPUT_DIR', None)
    if not default:
        os.environ['MAKEFUN_OUTPUT_DIR'] = str(target)
    # Redirect only the literal fallback, to exercise it without writing outside ROOT.
    original_path = Path
    def entry_path(value):
        return original_path(target if value == '/output' else value)
    namespace = runpy.run_path(str(ROOT/'main.py'))
    if default:
        namespace['main'].__globals__['Path'] = entry_path
    writes = []
    def audit(event, args):
        if event.startswith(('socket.', 'subprocess.')) or event in ('os.system','os.exec','os.spawn'):
            raise AssertionError('Forbidden runtime action: '+event)
        if event == 'open':
            name, mode, flags = args
            if isinstance(name, (str,bytes)) and (flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT)):
                path = original_path(os.fsdecode(name)).resolve()
                assert path == target/'entry.png', ('Unexpected file write', str(path))
                writes.append(path.name)
        if event == 'os.mkdir':
            assert original_path(args[0]).resolve() == target, 'Unexpected mkdir'
    sys.addaudithook(audit)
    namespace['main']()
    assert writes == ['entry.png']
    print('PASS runtime audit'+(' /output fallback redirected' if default else ''))


def verify(capture):
    capture = (ROOT/capture).resolve()
    assert capture.is_relative_to(ROOT)
    capture.mkdir(parents=True, exist_ok=True)
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in ROOT.rglob('*') if p.is_file() and not p.is_relative_to(capture)}
    tree = ast.parse((ROOT/'main.py').read_text())
    imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node,ast.Import)}
    imports |= {node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
    assert imports <= {'math','os','pathlib','struct','zlib'}, imports
    records, outputs = [], []
    for i in (1,2):
        directory = capture/('run'+str(i))
        directory.mkdir(exist_ok=True)
        assert set(p.name for p in directory.iterdir()) <= {'entry.png'}
        env = dict(os.environ, MAKEFUN_OUTPUT_DIR=str(directory),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED=str(i), TZ='UTC' if i == 1 else 'Pacific/Fiji')
        command = [sys.executable,'-P','-s',str(ROOT/'main.py')]
        result = subprocess.run(command,env=env,cwd=capture,capture_output=True,timeout=30)
        assert result.returncode == 0, result.stderr.decode()
        assert not result.stdout and not result.stderr
        assert [p.name for p in directory.iterdir()] == ['entry.png']
        data = (directory/'entry.png').read_bytes()
        w,h,raw = decode(data)
        outputs.append(data)
        records.append({'file':str((directory/'entry.png').relative_to(ROOT)),
                        'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data),
                        'width':w,'height':h})
    assert outputs[0] == outputs[1], 'Byte determinism'
    for default in (False,True):
        directory = capture/('default' if default else 'audit')
        command = [sys.executable,'-B','-P','-s',str(Path(__file__).resolve()),
                   '--guard',str(directory)]+(['--default'] if default else [])
        result = subprocess.run(command,capture_output=True,timeout=30)
        assert result.returncode == 0, result.stderr.decode()
        assert (directory/'entry.png').read_bytes() == outputs[0]
    namespace = runpy.run_path(str(ROOT/'main.py'))
    canvas = namespace['render']()
    boxes = canvas.text_boxes
    for i,(label,x,y,w,h) in enumerate(boxes):
        for other,ox,oy,ow,oh in boxes[i+1:]:
            assert x+w <= ox or ox+ow <= x or y+h <= oy or oy+oh <= y, (label,other)
    # A 300px box-filtered raster capture uses the same writer with a smaller canvas.
    thumb = bytearray()
    for y in range(300):
        row = bytearray()
        ya,yb = y*1000//300,(y+1)*1000//300
        for x in range(300):
            xa,xb = x*1000//300,(x+1)*1000//300
            for channel in range(3):
                total = sum(raw[yy*3001+1+xx*3+channel] for yy in range(ya,yb) for xx in range(xa,xb))
                row.append(total//((yb-ya)*(xb-xa)))
        thumb += b'\0'+row
    def chunk(kind,body):
        return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
    (capture/'thumbnail.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',300,300,8,2,0,0,0))+
                                         chunk(b'IDAT',zlib.compress(thumb,9))+chunk(b'IEND',b''))
    after = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in ROOT.rglob('*') if p.is_file() and not p.is_relative_to(capture)}
    assert before == after, 'Unexpected repository writes'
    summary = {'status':'pass','python':sys.version.split()[0], 'outputs':records,
               'checks':['two isolated entry runs with -P -s','different hash seeds and time zones',
                         'byte identity','PNG signature/chunk order/CRCs/zlib/scanlines',
                         'dimensions and 1 MiB cap','only entry.png in output',
                         'runtime write/network/process audit','redirected /output fallback',
                         'standard-library import allowlist','text boxes do not overlap',
                         'no writes outside capture directory'],
               'thumbnail':str((capture/'thumbnail.png').relative_to(ROOT))}
    (capture/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture',default='artifacts/final')
    parser.add_argument('--guard')
    parser.add_argument('--default',action='store_true')
    args = parser.parse_args()
    if args.guard:
        guarded(args.guard,args.default)
    else:
        verify(args.capture)
