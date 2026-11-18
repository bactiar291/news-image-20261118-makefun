# SPDX-License-Identifier: MIT
"""WORLD: an original, deterministic raster news front page. Standard library only."""
import math
import os
from pathlib import Path
import struct
import zlib

SIZE = 1000
INK = (24, 37, 43)
PAPER = (244, 233, 211)
WHITE = (255, 247, 227)
RED = (191, 61, 44)
AMBER = (228, 165, 65)
TEAL = (77, 119, 121)
MUTED = (115, 119, 108)

# Self-authored 5-by-7 uppercase raster alphabet. Each row is a five-bit mask.
GLYPHS = {
    'A': (14,17,17,31,17,17,17), 'B': (30,17,17,30,17,17,30),
    'C': (14,17,16,16,16,17,14), 'D': (30,17,17,17,17,17,30),
    'E': (31,16,16,30,16,16,31), 'F': (31,16,16,30,16,16,16),
    'G': (14,17,16,23,17,17,15), 'H': (17,17,17,31,17,17,17),
    'I': (31,4,4,4,4,4,31), 'J': (7,2,2,2,18,18,12),
    'K': (17,18,20,24,20,18,17), 'L': (16,16,16,16,16,16,31),
    'M': (17,27,21,21,17,17,17), 'N': (17,25,25,21,19,19,17),
    'O': (14,17,17,17,17,17,14), 'P': (30,17,17,30,16,16,16),
    'Q': (14,17,17,17,21,18,13), 'R': (30,17,17,30,20,18,17),
    'S': (15,16,16,14,1,1,30), 'T': (31,4,4,4,4,4,4),
    'U': (17,17,17,17,17,17,14), 'V': (17,17,17,17,17,10,4),
    'W': (17,17,17,21,21,27,17), 'X': (17,17,10,4,10,17,17),
    'Y': (17,17,10,4,4,4,4), 'Z': (31,1,2,4,8,16,31),
    '0': (14,17,19,21,25,17,14), '1': (4,12,4,4,4,4,14),
    '2': (14,17,1,2,4,8,31), '3': (30,1,1,14,1,1,30),
    '4': (2,6,10,18,31,2,2), '5': (31,16,16,30,1,1,30),
    '6': (14,16,16,30,17,17,14), '7': (31,1,2,4,8,8,8),
    '8': (14,17,17,14,17,17,14), '9': (14,17,17,15,1,1,14),
    '-': (0,0,0,31,0,0,0), '/': (1,2,2,4,8,8,16),
    '+': (0,4,4,31,4,4,0), '>': (16,8,4,2,4,8,16),
    ':': (0,4,4,0,4,4,0), '.': (0,0,0,0,0,12,12),
    '?': (14,17,1,2,4,0,4), '%': (25,26,2,4,8,11,19),
    ' ': (0,0,0,0,0,0,0),
}


class Canvas:
    def __init__(self):
        self.pixels = bytearray(bytes(INK) * SIZE * SIZE)
        self.text_boxes = []

    def rect(self, x, y, w, h, color):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(SIZE, int(x+w)), min(SIZE, int(y+h))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1-x0)
        for yy in range(y0, y1):
            start = (yy*SIZE+x0)*3
            self.pixels[start:start+len(row)] = row

    def disk(self, x, y, radius, color):
        for yy in range(-radius, radius+1):
            span = math.isqrt(radius*radius-yy*yy)
            self.rect(x-span, y+yy, span*2+1, 1, color)

    def line(self, points, color=INK, width=3):
        for (x0,y0), (x1,y1) in zip(points, points[1:]):
            steps = max(abs(x1-x0), abs(y1-y0), 1)
            for i in range(steps+1):
                self.disk(round(x0+(x1-x0)*i/steps),
                          round(y0+(y1-y0)*i/steps), width//2, color)

    def poly(self, points, color):
        for y in range(max(0, min(p[1] for p in points)),
                       min(SIZE, max(p[1] for p in points)+1)):
            xs = []
            for (ax,ay), (bx,by) in zip(points, points[1:]+points[:1]):
                if min(ay,by) <= y < max(ay,by):
                    xs.append(ax+(y-ay)*(bx-ax)/(by-ay))
            xs.sort()
            for left, right in zip(xs[::2], xs[1::2]):
                self.rect(math.ceil(left), y, math.floor(right)-math.ceil(left)+1, 1, color)

    def text(self, label, x, y, scale=3, color=INK):
        width = (len(label)*6-1)*scale
        assert 0 <= x and x+width <= SIZE and 0 <= y <= SIZE-7*scale, label
        self.text_boxes.append((label, x, y, width, 7*scale))
        for i, ch in enumerate(label):
            for yy, row in enumerate(GLYPHS[ch]):
                for xx in range(5):
                    if row & (16 >> xx):
                        self.rect(x+(6*i+xx)*scale, y+yy*scale, scale, scale, color)

    def arrow(self, points, color=RED, width=4):
        self.line(points, color, width)
        x,y = points[-1]
        px,py = points[-2]
        angle = math.atan2(y-py, x-px)
        ends = [(round(x-14*math.cos(angle+a)), round(y-14*math.sin(angle+a)))
                for a in (-0.6, 0.6)]
        self.line([ends[0], (x,y), ends[1]], color, width)

    def png(self):
        def chunk(kind, data):
            return (struct.pack('>I', len(data))+kind+data+
                    struct.pack('>I', zlib.crc32(kind+data)&0xffffffff))
        raw = b''.join(b'\0'+self.pixels[y*SIZE*3:(y+1)*SIZE*3] for y in range(SIZE))
        return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', SIZE,SIZE,8,2,0,0,0))+
                chunk(b'IDAT', zlib.compress(raw, 9))+chunk(b'IEND', b''))


def panel(c, x, y, w, h, number, section):
    c.rect(x,y,w,h,PAPER)
    c.rect(x,y,7,h,AMBER)
    c.text(number+' / '+section,x+20,y+18,2,RED)


def bridge(c):
    panel(c,28,222,560,314,'01','UKRAINE - CRIMEA')
    c.text('KERCH BRIDGE',48,270,5)
    c.text('DAMAGED',48,313,5,RED)
    c.rect(48,425,520,85,TEAL)
    for y in (449,477,499):
        for x in range(56,550,64):
            c.line([(x,y),(x+17,y-3),(x+38,y)],PAPER,2)
    for x in (98,224,428,532):
        c.poly([(x-8,402),(x+7,402),(x+12,474),(x-12,474)],INK)
    c.poly([(48,398),(271,398),(283,410),(270,420),(48,420)],INK)
    c.poly([(374,398),(568,398),(568,420),(366,420)],INK)
    c.poly([(290,413),(351,438),(346,455),(286,431)],RED)
    c.line([(96,398),(143,369),(184,398),(224,374),(265,398)],INK,4)
    c.line([(391,398),(437,367),(483,398),(530,374),(568,398)],INK,4)
    c.line([(321,376),(314,388),(328,397),(318,408)],RED,5)


def quad(c):
    panel(c,604,222,368,314,'02','DIPLOMACY')
    c.text('QUAD /',624,270,5)
    c.text('MANILA',624,313,5)
    for x in (648,735,822,909):
        c.disk(x,395,14,INK)
        c.poly([(x-20,419),(x+19,420),(x+25,457),(x-23,457)],TEAL)
        c.line([(x-27,370),(x-27,411)],INK,2)
        c.poly([(x-26,370),(x-4,373),(x-26,383)],RED)
    c.rect(629,457,318,10,INK)
    c.text('US INDIA JAPAN AUSTRALIA',624,486,2)
    c.text('MARCOS MEETING PLANNED',624,507,2,RED)


def weather(c):
    panel(c,28,552,304,330,'03','INDIAN OCEAN')
    c.text('AKVAN',48,594,5)
    c.text('FORECAST',48,636,4,RED)
    c.poly([(62,687),(107,695),(118,719),(144,745),(150,797),(119,826),(92,787)],TEAL)
    c.line([(107,695),(118,719),(144,745),(150,797),(119,826)],INK,3)
    for offset in (0, math.pi):
        points = []
        for i in range(60):
            a = i*0.075+offset
            r = 8+i*0.8
            points.append((round(235+r*math.cos(a)),round(751+r*math.sin(a))))
        c.line(points,INK,5)
    c.disk(235,751,6,RED)
    c.arrow([(218,791),(190,803),(158,786)],RED,3)
    c.text('BAY OF BENGAL',48,843,3)


def outages(c):
    panel(c,348,552,304,330,'04','TECH / US')
    c.text('US',368,594,5)
    c.text('OUTAGES',368,636,4)
    nodes = [(389,716),(599,716),(389,796),(599,796)]
    for x,y in nodes:
        c.line([(x,y),(494,755)],MUTED,3)
        c.rect(x-15,y-12,30,24,INK)
        c.rect(x-10,y-7,20,14,PAPER)
    c.disk(494,755,31,AMBER)
    c.text('?',484,741,4)
    c.text('NO LINK',368,826,4,RED)
    c.text('CONFIRMED',368,856,4,RED)


def ev(c):
    panel(c,668,552,304,330,'05','CLIMATE / UK')
    c.text('UK EV',688,594,5)
    c.text('MANDATE',688,636,4)
    c.poly([(707,792),(747,687),(800,687),(850,792)],INK)
    c.line([(776,702),(776,718)],PAPER,3)
    c.line([(777,733),(778,751)],PAPER,3)
    c.line([(780,768),(782,786)],PAPER,3)
    c.poly([(835,763),(831,720),(870,695),(897,692),(894,727),(863,753)],TEAL)
    c.line([(832,778),(849,743),(877,716)],INK,3)
    c.text('33 > 80 > 100',688,812,3,RED)
    c.text('2026  2030  2035',688,842,3)
    c.text('TARGET WARNING',688,866,3)


def render():
    c = Canvas()
    c.text('WORLD',28,32,18,PAPER)
    c.rect(596,33,376,125,RED)
    c.text('18 NOV',616,47,7,WHITE)
    c.text('2026',616,107,5,WHITE)
    c.text('WEDNESDAY',28,179,4,PAPER)
    c.text('ONE DAY / FIVE WINDOWS',508,185,3,AMBER)
    c.rect(28,209,944,2,PAPER)
    bridge(c)
    quad(c)
    weather(c)
    outages(c)
    ev(c)
    c.rect(28,906,944,66,AMBER)
    c.text('XAVIER / CATEGORY 5',48,919,4)
    c.text('SOUTH PACIFIC - NORTHERN COOK ISLANDS',48,953,3)
    return c


def main():
    output = Path(os.environ.get('MAKEFUN_OUTPUT_DIR', '/output'))
    output.mkdir(parents=True, exist_ok=True)
    (output/'entry.png').write_bytes(render().png())


if __name__ == '__main__':
    main()
