#!/usr/bin/env python3
"""Generate docs/diagrams/erd-*.html (diagram-design ER type) from the inline spec below,
and render erd-schema.md as erd-schema.html.

    python3 docs/diagrams/erd-gen.py            # all diagrams + erd-map.html
    python3 docs/diagrams/erd-gen.py order      # one slug

Edit the spec (entities, grid, relationships) here and rerun; do not hand-edit the HTML.

Every diagram is checked before it is written: orthogonal routes only, no crossing or
touching connectors, no transit behind a non-endpoint box, label masks clear of boxes
and lines, attach points >= 12px apart, 4px grid, ER budget, and every drawn column
must exist in erd-schema.md.
"""
import collections
import html
import itertools
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SCHEMA_MD = ROOT / 'erd-schema.md'

PAPER, INK, MUTED, SOFT, ACCENT = '#f5f5f5', '#2d3142', '#4f5d75', '#7a8399', '#eb6c36'
MONO, SANS = "'Geist Mono', monospace", "'Geist', sans-serif"
HEAD_H, ROW_H, PAD_B = 40, 20, 12
COL_GAP, ROW_GAP, MARGIN, TOP = 80, 56, 40, 32
VB_W = 1280
CH10 = 6.0   # 10px mono advance
CH8 = 6.0    # 8px mono + 0.12em tracking


def r4(v):
    return int(round(v / 4.0)) * 4


def sign(v):
    return (v > 0) - (v < 0)


# ----------------------------------------------------------------- schema doc
ALIAS = {'std_size': 'std_color', 'vendor_size': 'vendor_color'}


def parse_schema(md):
    tables, cur, in_code = {}, None, False
    for line in md.splitlines():
        if line.startswith('```'):
            in_code = not in_code
            continue
        m = re.match(r'^### (\S+)', line)
        if m and not in_code:
            cur = m.group(1)
            tables.setdefault(cur, [])
            continue
        if in_code and cur:
            s = line.strip()
            if not s or s.startswith(('PK (', 'UQ (')):
                continue
            m2 = re.match(r'^([a-z_][a-z0-9_]*)\s+\S', s)
            if m2 and m2.group(1) not in tables[cur]:
                tables[cur].append(m2.group(1))
    return tables


SCHEMA = parse_schema(SCHEMA_MD.read_text())


def schema_cols(table):
    return SCHEMA[ALIAS.get(table, table)]


# ----------------------------------------------------------------- model
class Field:
    def __init__(self, spec):
        kind = ''
        if spec.startswith('# '):
            kind, spec = 'pk', spec[2:]
        elif spec.startswith('→ '):
            kind, spec = 'fk', spec[2:]
        self.name, self.type = spec.split(' ', 1)
        self.kind = kind


class E:
    def __init__(self, key, ko, fields, style='entity', w=None):
        self.key, self.ko, self.style, self.force_w = key, ko, style, w
        self.fields = [Field(f) for f in fields]
        self.x = self.y = self.w = self.h = 0
        self.col = self.row = None
        self.more = 0

    @property
    def cx(self):
        return self.x + self.w // 2

    @property
    def cy(self):
        return self.y + self.h // 2


class R:
    """src.side(off) -> dst.side(off). off: None=center, float=fraction, int=px, 'match'."""

    def __init__(self, src, ss, so, dst, ds, do, sc, dc, label=None, dashed=False, via=None, lab=None):
        self.src, self.ss, self.so = src, ss, so
        self.dst, self.ds, self.do = dst, ds, do
        self.sc, self.dc, self.label, self.dashed, self.via, self.lab = sc, dc, label, dashed, via, lab
        self.pts = []

    def __repr__(self):
        return f'{self.src}.{self.ss}->{self.dst}.{self.ds}'


# ----------------------------------------------------------------- layout
def layout(d):
    ents, grid = d['ents'], d['grid']
    ncols = max(len(r) for r in grid)
    for i, row in enumerate(grid):
        for j, k in enumerate(row):
            if k:
                ents[k].col, ents[k].row = j, i
    for e in ents.values():
        assert e.col is not None, f'{e.key} not placed'
        e.more = len(schema_cols(e.key)) - len(e.fields)
        rows = len(e.fields) + (1 if e.more > 0 else 0)
        e.h = HEAD_H + ROW_H * rows + PAD_B
        chars = max(len(f.name) + len(f.type) + (2 if f.kind else 0) + 3 for f in e.fields)
        need = max(chars * CH10 + 32, len(e.key) * 7.6 + len(e.ko) * 10.5 + 44)
        e.w = e.force_w or next(w for w in (160, 180, 200, 240, 320) if w >= need)
    colw = [max((e.w for e in ents.values() if e.col == j), default=0) for j in range(ncols)]
    rowh = [max((e.h for e in ents.values() if e.row == i), default=0) for i in range(len(grid))]
    col_x = [MARGIN]
    for j in range(ncols - 1):
        col_x.append(col_x[-1] + colw[j] + COL_GAP)
    rg = d.get('row_gap', ROW_GAP)
    row_y = [TOP]
    for i in range(len(grid) - 1):
        row_y.append(row_y[-1] + rowh[i] + rg)
    for e in ents.values():
        e.x = r4(col_x[e.col] + (colw[e.col] - e.w) / 2)
        e.y = row_y[e.row]
    d.update(colw=colw, rowh=rowh, col_x=col_x, row_y=row_y)


def gapx(d, j, delta=0):
    return r4(d['col_x'][j] + d['colw'][j] + COL_GAP / 2 + delta)


def gapy(d, i, delta=0):
    return r4(d['row_y'][i] + d['rowh'][i] + d.get('row_gap', ROW_GAP) / 2 + delta)


def resolve(off, L):
    if off is None:
        return r4(L / 2)
    if isinstance(off, float):
        return r4(L * off)
    return off


def attach(e, side, off):
    if side in 'LR':
        return (e.x if side == 'L' else e.x + e.w, e.y + resolve(off, e.h))
    return (e.x + resolve(off, e.w), e.y if side == 'T' else e.y + e.h)


def attach_match(e, side, p):
    if side in 'LR':
        return (e.x if side == 'L' else e.x + e.w, p[1])
    return (p[0], e.y if side == 'T' else e.y + e.h)


def route(d, r):
    ents = d['ents']
    S, D = ents[r.src], ents[r.dst]
    if r.so == 'match':
        p1 = attach(D, r.ds, r.do)
        p0 = attach_match(S, r.ss, p1)
    elif r.do == 'match':
        p0 = attach(S, r.ss, r.so)
        p1 = attach_match(D, r.ds, p0)
    else:
        p0, p1 = attach(S, r.ss, r.so), attach(D, r.ds, r.do)
    hs, hd = r.ss in 'LR', r.ds in 'LR'
    if hs and hd:
        if p0[1] == p1[1]:
            pts = [p0, p1]
        else:
            vx = gapx(d, *r.via[1:]) if r.via[0] == 'x' else r.via[1]
            pts = [p0, (vx, p0[1]), (vx, p1[1]), p1]
    elif not hs and not hd:
        if p0[0] == p1[0]:
            pts = [p0, p1]
        else:
            vy = gapy(d, *r.via[1:]) if r.via[0] == 'y' else r.via[1]
            pts = [p0, (p0[0], vy), (p1[0], vy), p1]
    elif hs:
        pts = [p0, (p1[0], p0[1]), p1]
    else:
        pts = [p0, (p0[0], p1[1]), p1]
    r.pts = pts


# ----------------------------------------------------------------- annotations
def card_mark(end, toward, text):
    dx, dy = sign(toward[0] - end[0]), sign(toward[1] - end[1])
    px, py = end[0] + dx * 16, end[1] + dy * 16
    w = len(text) * CH10 + 2
    if dy == 0:
        return dict(x=px, y=py - 6, anchor='middle', text=text, bbox=(px - w / 2, py - 15, w, 10))
    return dict(x=px + 8, y=py + 4, anchor='start', text=text, bbox=(px + 8, py - 5, w, 10))


def label_box(d, pts, text, lab):
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    at = None
    if lab:
        i, side = lab[0], lab[1]
        at = lab[2] if len(lab) > 2 else None
    else:
        i = max(range(len(segs)), key=lambda k: abs(segs[k][0][0] - segs[k][1][0]) + abs(segs[k][0][1] - segs[k][1][1]))
        side = None
    a, b = segs[i]
    mx, my = r4((a[0] + b[0]) / 2), r4((a[1] + b[1]) / 2)
    if at:  # anchor the label at a gap coordinate instead of the segment midpoint
        if at[0] == 'y':
            my = gapy(d, *at[1:])
        else:
            mx = gapx(d, *at[1:])
    w, h = r4(len(text) * CH8 + 8), 12
    if a[1] == b[1]:  # horizontal (marks sit above, so labels default below)
        side = side or 'below'
        if side == 'above':
            rect = (mx - w // 2, my - 18, w, h)
            ty = my - 9
        else:
            rect = (mx - w // 2, my + 6, w, h)
            ty = my + 15
        tx = mx
    else:  # vertical (marks sit right, so labels default left)
        side = side or 'left'
        if side == 'right':
            rect = (mx + 6, my - 6, w, h)
        else:
            rect = (mx - 6 - w, my - 6, w, h)
        tx, ty = rect[0] + w // 2, my + 3
    return dict(rect=rect, x=tx, y=ty, text=text)


# ----------------------------------------------------------------- checks
def bbox_overlap(a, b):
    """open-interval overlap of two (x, y, w, h) rects"""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def seg_bbox(a, b):
    x1, x2 = sorted((a[0], b[0]))
    y1, y2 = sorted((a[1], b[1]))
    return (x1, y1, x2 - x1, y2 - y1)


def segs_touch(a, b, c, d):
    ax1, ax2 = sorted((a[0], b[0]))
    ay1, ay2 = sorted((a[1], b[1]))
    cx1, cx2 = sorted((c[0], d[0]))
    cy1, cy2 = sorted((c[1], d[1]))
    return ax1 <= cx2 and cx1 <= ax2 and ay1 <= cy2 and cy1 <= ay2


def check(d):
    errs = []
    ents, rels = d['ents'], d['rels']
    cap = d.get('max_ents', 8)
    if len(ents) > cap:
        errs.append(f'{len(ents)} entities > {cap}')
    if len(rels) > 12:
        errs.append(f'{len(rels)} relationships > 12')
    if sum(e.style == 'focal' for e in ents.values()) > 2:
        errs.append('more than 2 focal entities')
    for e in ents.values():
        for v in (e.x, e.y, e.w, e.h):
            if v % 4:
                errs.append(f'{e.key} off grid: {v}')
        if not e.fields:
            continue
        cols = schema_cols(e.key)
        for f in e.fields:
            if f.name not in cols:
                errs.append(f'{e.key}.{f.name} not in erd-schema.md')
        if e.more < 0:
            errs.append(f'{e.key} shows more fields than the schema has')
    segs = []
    for ri, r in enumerate(rels):
        pts = r.pts
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if a[0] != b[0] and a[1] != b[1]:
                errs.append(f'{r}: diagonal segment {a}-{b}')
            if a == b:
                errs.append(f'{r}: zero-length segment')
            if len(pts) > 2 and abs(a[0] - b[0]) + abs(a[1] - b[1]) < 16:
                errs.append(f'{r}: segment {a}-{b} shorter than 16px')
            if any(v % 4 for v in a + b):
                errs.append(f'{r}: off-grid point {a}-{b}')
            segs.append((ri, a, b))
    for (ri, a, b), (rj, c, dd) in itertools.combinations(segs, 2):
        if ri != rj and segs_touch(a, b, c, dd):
            errs.append(f'{rels[ri]} touches/crosses {rels[rj]} at {a}-{b} / {c}-{dd}')
    boxes = {k: (e.x, e.y, e.w, e.h) for k, e in ents.items()}
    for ri, a, b in segs:
        for k, box in boxes.items():
            if bbox_overlap(seg_bbox(a, b), box):
                errs.append(f'{rels[ri]} passes through {k} at {a}-{b}')
    # annotations
    for r in rels:
        for m in r.marks + ([r.labelbox['rect']] if r.labelbox else []):
            rect = m['bbox'] if isinstance(m, dict) else m
            for k, box in boxes.items():
                if bbox_overlap(rect, box):
                    errs.append(f'{r}: annotation {rect} overlaps {k}')
            for ri, a, b in segs:
                sb = seg_bbox(a, b)
                sb = (sb[0] - 1, sb[1] - 1, sb[2] + 2, sb[3] + 2)
                if bbox_overlap(rect, sb):
                    errs.append(f'{r}: annotation {rect} sits on {rels[ri]}')
    ann = []
    for r in rels:
        ann += [(r, m['bbox']) for m in r.marks]
        if r.labelbox:
            ann.append((r, r.labelbox['rect']))
    for (r1, b1), (r2, b2) in itertools.combinations(ann, 2):
        if bbox_overlap(b1, b2):
            errs.append(f'annotation {b1} of {r1} overlaps annotation {b2} of {r2}')
    # attach spacing
    att = {}
    for r in rels:
        att.setdefault((r.src, r.ss), []).append(r.pts[0])
        att.setdefault((r.dst, r.ds), []).append(r.pts[-1])
    for (k, side), pts in att.items():
        e = ents[k]
        vals = sorted(p[1] if side in 'LR' else p[0] for p in pts)
        lo, hi = (e.y, e.y + e.h) if side in 'LR' else (e.x, e.x + e.w)
        for v in vals:
            if v < lo + 12 or v > hi - 12:
                errs.append(f'{k}.{side} attach {v} within 12px of a corner')
        for v1, v2 in zip(vals, vals[1:]):
            if v2 - v1 < 12:
                errs.append(f'{k}.{side} attaches {v1},{v2} closer than 12px')
    return errs


# ----------------------------------------------------------------- render
def t(s):
    return html.escape(s, quote=False)


def render_svg(d):
    ents, rels = d['ents'], d['rels']
    out = []
    content_bottom = max(e.y + e.h for e in ents.values())
    for r in rels:
        content_bottom = max(content_bottom, max(p[1] for p in r.pts))
        for m in r.marks:
            content_bottom = max(content_bottom, m['bbox'][1] + m['bbox'][3])
        if r.labelbox:
            content_bottom = max(content_bottom, r.labelbox['rect'][1] + 12)
    legend_y = r4(content_bottom + 56)
    vb_h = legend_y + 44
    vb_w = frame_w(ents)
    if vb_w > VB_W:
        print(f'   ! {d["slug"]} is {vb_w}px wide, over the {VB_W}px frame')
    slug = d['slug']
    out.append(f'<svg viewBox="0 0 {vb_w} {vb_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="erd-{slug}-title erd-{slug}-desc">')
    out.append(f'  <title id="erd-{slug}-title">{t(d["title"])}</title>')
    out.append(f'  <desc id="erd-{slug}-desc">{t(d["desc"])}</desc>')
    out.append(f'  <rect width="100%" height="100%" fill="{PAPER}"/>')
    out.append('  <!-- relationships (drawn before boxes) -->')
    for r in rels:
        dash = ' stroke-dasharray="5,4"' if r.dashed else ''
        out.append(f'  <path d="{path_d(r.pts)}" fill="none" stroke="{MUTED}" stroke-width="1"{dash}/>')
    out.append('  <!-- cardinality -->')
    for r in rels:
        for m in r.marks:
            out.append(f'  <text x="{m["x"]}" y="{m["y"]}" fill="{MUTED}" font-size="10" font-weight="600" font-family="{MONO}" text-anchor="{m["anchor"]}">{t(m["text"])}</text>')
    out.append('  <!-- relationship labels -->')
    for r in rels:
        lb = r.labelbox
        if lb:
            x, y, w, h = lb['rect']
            out.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{PAPER}"/>')
            out.append(f'  <text x="{lb["x"]}" y="{lb["y"]}" fill="{SOFT}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.12em">{t(lb["text"])}</text>')
    out.append('  <!-- entities -->')
    for e in ents.values():
        out.extend(render_entity(e))
    out.extend(render_legend(d, legend_y))
    out.append('</svg>')
    return '\n'.join(out), vb_h


def frame_w(ents):
    return max(VB_W, max(e.x + e.w for e in ents.values()) + MARGIN)


def path_d(pts, r=8):
    if len(pts) == 2:
        return f'M {pts[0][0]},{pts[0][1]} L {pts[1][0]},{pts[1][1]}'
    s = f'M {pts[0][0]},{pts[0][1]}'
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        dx1, dy1 = sign(b[0] - a[0]), sign(b[1] - a[1])
        dx2, dy2 = sign(c[0] - b[0]), sign(c[1] - b[1])
        s += f' L {b[0] - dx1 * r},{b[1] - dy1 * r} Q {b[0]},{b[1]} {b[0] + dx2 * r},{b[1] + dy2 * r}'
    s += f' L {pts[-1][0]},{pts[-1][1]}'
    return s


STYLES = {
    'entity': dict(fill='#ffffff', stroke=INK, head='rgba(45,49,66,0.04)', rule='rgba(45,49,66,0.22)', tag=MUTED, tagtext='ENTITY', dash=''),
    'focal': dict(fill='rgba(235,108,54,0.04)', stroke=ACCENT, head='rgba(235,108,54,0.10)', rule='rgba(235,108,54,0.40)', tag=ACCENT, tagtext='ENTITY · AGGREGATE ROOT', dash=''),
    'join': dict(fill='rgba(45,49,66,0.04)', stroke=MUTED, head='rgba(45,49,66,0.06)', rule='rgba(45,49,66,0.22)', tag=MUTED, tagtext='JOIN', dash=' stroke-dasharray="4,3"'),
}


def render_entity(e):
    s = STYLES[e.style]
    x, y, w, h = e.x, e.y, e.w, e.h
    o = [f'  <!-- {e.key} -->']
    o.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>')
    o.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{s["fill"]}" stroke="{s["stroke"]}" stroke-width="1"{s["dash"]}/>')
    o.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{HEAD_H}" rx="6" fill="{s["head"]}"/>')
    o.append(f'  <rect x="{x}" y="{y + HEAD_H - 8}" width="{w}" height="8" fill="{s["head"]}"/>')
    o.append(f'  <line x1="{x}" y1="{y + HEAD_H}" x2="{x + w}" y2="{y + HEAD_H}" stroke="{s["rule"]}" stroke-width="1"/>')
    o.append(f'  <text x="{x + 16}" y="{y + 16}" fill="{s["tag"]}" font-size="8" font-family="{MONO}" letter-spacing="0.14em">{s["tagtext"]}</text>')
    o.append(f'  <text x="{x + 16}" y="{y + 32}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}">{t(e.key)}</text>')
    o.append(f'  <text x="{x + w - 16}" y="{y + 32}" fill="{MUTED}" font-size="10" font-family="{SANS}" text-anchor="end">{t(e.ko)}</text>')
    by = y + 56
    for f in e.fields:
        prefix = {'pk': '# ', 'fk': '→ ', '': ''}[f.kind]
        weight = ' font-weight="600"' if f.kind == 'pk' else ''
        o.append(f'  <text x="{x + 16}" y="{by}" fill="{INK}" font-size="10"{weight} font-family="{MONO}">{t(prefix + f.name)}</text>')
        o.append(f'  <text x="{x + w - 16}" y="{by}" fill="{MUTED}" font-size="10" font-family="{MONO}" text-anchor="end">{t(f.type)}</text>')
        by += ROW_H
    if e.more > 0:
        # this is HTML, so the hidden columns stay reachable: name them in a native
        # tooltip and link the row to the table's full definition in erd-schema.html
        drawn = {f.name for f in e.fields}
        hidden = [c for c in schema_cols(e.key) if c not in drawn]
        assert len(hidden) == e.more, f'{e.key}: {len(hidden)} hidden but more={e.more}'
        o.append(f'  <a href="erd-schema.html#t-{e.key}" class="more">')
        o.append(f'    <title>{t(e.key)}: {t(", ".join(hidden))}</title>')
        o.append(f'    <text x="{x + 16}" y="{by}" fill="{SOFT}" font-size="10" font-family="{MONO}">+{e.more} more</text>')
        o.append('  </a>')
    return o


def render_legend(d, ly):
    ents, rels = d['ents'], d['rels']
    items = []
    if any(e.style == 'focal' for e in ents.values()):
        items.append(('box', 'focal', 'Aggregate root'))
    items.append(('box', 'entity', 'Entity'))
    if any(e.style == 'join' for e in ents.values()):
        items.append(('box', 'join', 'Join table'))
    items.append(('glyph', '#', 'Primary key'))
    items.append(('glyph', '→', 'Foreign key'))
    items.append(('glyph', '1 / N', 'Cardinality'))
    if any(r.dashed for r in rels):
        items.append(('line', 'dashed', d.get('dashed_means', 'Optional')))
    o = ['  <!-- legend -->']
    o.append(f'  <line x1="{MARGIN}" y1="{ly - 8}" x2="{frame_w(ents) - MARGIN}" y2="{ly - 8}" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>')
    o.append(f'  <text x="{MARGIN}" y="{ly + 8}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.18em">LEGEND</text>')
    x = MARGIN
    yy = ly + 24
    for kind, key, text in items:
        if kind == 'box':
            s = STYLES[key]
            o.append(f'  <rect x="{x}" y="{yy}" width="14" height="10" rx="2" fill="{s["fill"]}" stroke="{s["stroke"]}" stroke-width="1"{s["dash"]}/>')
            tx = x + 20
        elif kind == 'glyph':
            o.append(f'  <text x="{x}" y="{yy + 9}" fill="{INK}" font-size="10" font-weight="600" font-family="{MONO}">{t(key)}</text>')
            tx = x + len(key) * 6 + 8
        else:
            o.append(f'  <line x1="{x}" y1="{yy + 5}" x2="{x + 24}" y2="{yy + 5}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="5,4"/>')
            tx = x + 30
        o.append(f'  <text x="{tx}" y="{yy + 8}" fill="{MUTED}" font-size="8.5" font-family="{SANS}">{t(text)}</text>')
        x = r4(tx + len(text) * 5.2 + 36)
    return o


PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --color-paper:   #f5f5f5;   /* white-smoke */
      --color-ink:     #2d3142;   /* jet-black */
      --color-muted:   #4f5d75;   /* blue-slate */
      --color-accent:  #eb6c36;   /* atomic-tangerine */
      --font-sans:     'Geist', system-ui, sans-serif;
      --font-serif:    'Instrument Serif', serif;
      --font-mono:     'Geist Mono', ui-monospace, monospace;
    }}

    body {{
      font-family: var(--font-sans);
      background: var(--color-paper);
      color: var(--color-ink);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 3rem 2rem;
    }}

    .frame {{ max-width: 1200px; width: 100%; }}

    .eyebrow {{
      font-family: var(--font-mono);
      font-size: 0.66rem;
      font-weight: 500;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--color-muted);
      margin-bottom: 0.5rem;
    }}

    h1 {{
      font-family: var(--font-serif);
      font-size: clamp(1.5rem, 2.4vw + 0.75rem, 2rem);
      font-weight: 400;
      letter-spacing: -0.02em;
      line-height: 1.15;
      color: var(--color-ink);
      margin-bottom: 0.5rem;
    }}

    .sub {{
      font-size: 0.8rem;
      color: var(--color-muted);
      margin-bottom: 1.5rem;
    }}
    .sub a {{ color: inherit; }}

    svg {{ width: 100%; min-width: 900px; display: block; }}
    svg a.more {{ cursor: pointer; }}
    svg a.more text {{ text-decoration: underline dotted; text-underline-offset: 3px; }}
    svg a.more:hover text, svg a.more:focus-visible text {{ fill: var(--color-accent); }}

    .fk {{ margin-top: 2.5rem; border-top: 1px solid rgba(45,49,66,0.10); padding-top: 1rem; }}
    .fk h2 {{
      font-family: var(--font-mono);
      font-size: 0.5rem;
      font-weight: 500;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--color-muted);
      margin-bottom: 0.75rem;
    }}
    .fk table {{ border-collapse: collapse; width: 100%; font-size: 0.7rem; }}
    .fk th, .fk td {{ text-align: left; padding: 0.3rem 1rem 0.3rem 0; border-bottom: 1px solid rgba(45,49,66,0.07); vertical-align: top; }}
    .fk th {{
      font-family: var(--font-mono);
      font-size: 0.5rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--color-muted);
      white-space: nowrap;
    }}
    .fk td:first-child, .fk td:nth-child(2) {{ white-space: nowrap; font-weight: 500; }}
    .fk td:last-child {{ font-family: var(--font-mono); color: var(--color-muted); font-size: 0.66rem; }}
    .fk tr:last-child td {{ border-bottom: none; }}
    .fk .note {{ font-size: 0.7rem; color: var(--color-muted); margin-top: 0.75rem; }}
    .fk .note code {{ font-family: var(--font-mono); font-size: 0.92em; }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{h1}</h1>
    <p class="sub">{sub}</p>

{svg}
{extra}
  </div>
</body>
</html>
'''


def build(d):
    layout(d)
    for r in d['rels']:
        route(d, r)
        r.marks = [card_mark(r.pts[0], r.pts[1], r.sc), card_mark(r.pts[-1], r.pts[-2], r.dc)]
        r.labelbox = label_box(d, r.pts, r.label, r.lab) if r.label else None
    errs = check(d)
    if errs:
        print(f'[{d["slug"]}] FAILED')
        for e in errs:
            print('   -', e)
        return False
    svg, vb_h = render_svg(d)
    svg = '\n'.join('    ' + line for line in svg.splitlines())
    page = PAGE.format(title=t(d['title']), eyebrow=t(d['eyebrow']), h1=t(d['h1']), sub=d['sub'], svg=svg, extra=d.get('extra', ''))
    path = ROOT / f'erd-{d["slug"]}.html'
    path.write_text(page)
    print(f'[{d["slug"]}] ok  entities={len(d["ents"])} rels={len(d["rels"])} viewBox=1280x{vb_h} -> {path.name}')
    return True


SUB_SCHEMA = 'Columns are a subset; the full list is in <a href="erd-schema.html">erd-schema.html</a>.'


# ================================================================= specs
def ents(*es):
    return {e.key: e for e in es}


DIAGRAMS = []

# ---------------------------------------------------------------- overview
DIAGRAMS.append(dict(
    slug='overview',
    eyebrow='ER · SPAO FO/BO IA · 도메인 개요',
    h1='Eight aggregates behind the SPAO menu tree',
    title='SPAO brand mall · domain overview',
    desc='Entity-relationship overview: vendors supply products, display categories present them and shops stock them; members place orders that contain products; promotions apply to orders and issue coupons to members; events collect entries from members.',
    sub='Domain-level view. 테이블 85개 전체는 <a href="erd-map.html">도메인 맵</a>에 있다. '
        'Each aggregate has its own detail ERD: '
        '<a href="erd-member.html">member</a> · <a href="erd-product.html">product</a> · <a href="erd-display.html">display</a> · '
        '<a href="erd-order.html">order</a> · <a href="erd-promotion.html">promotion</a> · <a href="erd-settlement.html">settlement</a> · '
        '<a href="erd-system.html">system</a>. ' + SUB_SCHEMA,
    dashed_means='Optional (0..1)',
    ents=ents(
        E('vendor', '업체', ['# id bigint', 'code text', 'name text', 'vendor_type text']),
        E('product', '상품', ['# id bigint', '→ vendor_id bigint', '→ std_category_id bigint', 'product_code text', 'name text', 'sale_price int']),
        E('display_category', '전시 카테고리', ['# id bigint', '→ parent_id bigint', 'category_type text', 'home_type text', 'name text']),
        E('shop', '매장', ['# id bigint', 'code text', 'name text', 'pickup_yn bool']),
        E('orders', '주문', ['# id bigint', 'order_no text', '→ member_id bigint', '→ pickup_shop_id bigint', 'order_type text', 'status text', 'pay_amount int'], 'focal'),
        E('member', '회원', ['# id bigint', 'login_id text', 'name text', 'grade_code text', 'status text']),
        E('promotion', '프로모션', ['# id bigint', 'name text', 'promo_type text', 'discount_type text', 'status text']),
        E('event', '이벤트', ['# id bigint', 'title text', 'entry_mode text', 'entry_type text', 'status text']),
    ),
    grid=[
        ['vendor', 'product', 'display_category'],
        ['shop', 'orders', 'member'],
        [None, 'promotion', 'event'],
    ],
    rels=[
        R('vendor', 'R', 'match', 'product', 'L', 0.3, '1', 'N', 'SUPPLIES'),
        R('product', 'R', 0.3, 'display_category', 'L', 'match', 'N', 'N', 'DISPLAYS'),
        R('shop', 'R', 0.3, 'product', 'L', 0.7, 'N', 'N', 'SHOP_STOCK', via=('x', 0)),
        R('shop', 'R', 0.7, 'orders', 'L', 'match', '0..1', 'N', 'PICKUP', dashed=True),
        R('product', 'B', None, 'orders', 'T', 'match', 'N', 'N', 'ORDER_ITEM'),
        R('member', 'L', 0.5, 'orders', 'R', 'match', '1', 'N', 'PLACES'),
        R('member', 'L', 0.2, 'product', 'R', 0.7, 'N', 'N', 'WISHLIST', via=('x', 1, -8)),
        R('promotion', 'T', None, 'orders', 'B', 'match', 'N', 'N', 'ORDER_BENEFIT'),
        R('promotion', 'R', 0.5, 'member', 'L', 0.8, 'N', 'N', 'MEMBER_COUPON', via=('x', 1, 8), lab=(1, 'right')),
        R('event', 'T', None, 'member', 'B', 'match', 'N', 'N', 'EVENT_ENTRY'),
    ],
))

# ---------------------------------------------------------------- member
DIAGRAMS.append(dict(
    slug='member',
    eyebrow='ER · SPAO FO/BO IA · 회원',
    h1='A member and everything the member owns',
    title='SPAO brand mall · member',
    desc='Entity-relationship diagram: a member owns delivery addresses, child profiles, app devices, wishlist entries, recently viewed products and restock alerts.',
    sub='FO 회원가입·로그인·마이페이지 계정정보·활동 정보, BO 회원관리. ' + SUB_SCHEMA,
    ents=ents(
        E('member', '회원', ['# id bigint', 'login_id text', 'name text', 'phone text', 'grade_code text', 'status text', '→ favorite_shop_id bigint', 'marketing_agree bool'], 'focal'),
        E('member_address', '배송지', ['# id bigint', '→ member_id bigint', 'recipient text', 'phone text', 'address1 text', 'is_default bool']),
        E('member_child', '우리 아이정보', ['# id bigint', '→ member_id bigint', 'name text', 'birth_date date']),
        E('member_device', '앱 기기', ['# id bigint', '→ member_id bigint', 'device_token text', 'push_agree bool']),
        E('wishlist', '찜', ['# id bigint', '→ member_id bigint', 'target_type text', 'target_id bigint']),
        E('recent_view', '최근 본 상품', ['# id bigint', '→ member_id bigint', '→ product_id bigint', 'viewed_at timestamptz']),
        E('restock_alert', '재입고 알림', ['# id bigint', '→ member_id bigint', '→ product_sku_id bigint', 'status text']),
    ),
    grid=[
        ['member_address', 'member', 'wishlist'],
        ['member_child', None, 'recent_view'],
        ['member_device', None, 'restock_alert'],
    ],
    rels=[
        R('member', 'L', 0.25, 'member_address', 'R', 'match', '1', 'N'),
        R('member', 'L', 0.5, 'member_child', 'R', 0.5, '1', 'N', via=('x', 0, -8)),
        R('member', 'L', 0.75, 'member_device', 'R', 0.5, '1', 'N', via=('x', 0, 8)),
        R('member', 'R', 0.25, 'wishlist', 'L', 'match', '1', 'N'),
        R('member', 'R', 0.5, 'recent_view', 'L', 0.5, '1', 'N', via=('x', 1, 8)),
        R('member', 'R', 0.75, 'restock_alert', 'L', 0.5, '1', 'N', via=('x', 1, -8)),
    ],
))

# ---------------------------------------------------------------- product
DIAGRAMS.append(dict(
    slug='product',
    eyebrow='ER · SPAO FO/BO IA · 상품',
    h1='Product, its SKUs, and where stock sits',
    title='SPAO brand mall · product',
    desc='Entity-relationship diagram: a vendor supplies products classified by standard category; each product has SKUs keyed by standard color and size, and shops hold stock per SKU.',
    sub='FO 상품상세·옵션선택·매장재고, BO 상품관리·상품기초정보관리·업체관리. ' + SUB_SCHEMA,
    ents=ents(
        E('vendor', '업체', ['# id bigint', '→ parent_vendor_id bigint', 'code text', 'name text', 'vendor_type text']),
        E('std_category', '표준 카테고리', ['# id bigint', '→ parent_id bigint', 'name text', 'depth smallint']),
        E('product', '상품', ['# id bigint', '→ vendor_id bigint', '→ std_category_id bigint', 'product_code text', 'name text', 'product_type text', 'sale_price int', 'sale_status text'], 'focal'),
        E('product_sku', '단품', ['# id bigint', '→ product_id bigint', 'sku_code text', 'barcode text', '→ std_color_id bigint', '→ std_size_id bigint', 'stock_qty int']),
        E('std_color', '표준 색상', ['# id bigint', 'code text', 'name text', 'hex char(7)']),
        E('std_size', '표준 사이즈', ['# id bigint', 'code text', 'name text', 'sort_order int']),
        E('shop_stock', '매장 재고', ['→ shop_id bigint', '→ product_sku_id bigint', 'qty int', 'synced_at timestamptz'], 'join'),
        E('shop', '매장', ['# id bigint', 'code text', 'name text', 'address text', 'pickup_yn bool']),
    ),
    grid=[
        ['vendor', 'product', 'product_sku', 'std_color'],
        ['std_category', None, 'shop_stock', 'std_size'],
        [None, None, 'shop', None],
    ],
    rels=[
        R('vendor', 'R', 'match', 'product', 'L', 0.25, '1', 'N', 'SUPPLIES'),
        R('std_category', 'R', 0.5, 'product', 'L', 0.75, '1', 'N', via=('x', 0)),
        R('product', 'R', 0.25, 'product_sku', 'L', 'match', '1', 'N'),
        R('std_color', 'L', 'match', 'product_sku', 'R', 0.3, '1', 'N'),
        R('std_size', 'L', 0.5, 'product_sku', 'R', 0.7, '1', 'N', via=('x', 2)),
        R('product_sku', 'B', None, 'shop_stock', 'T', 'match', '1', 'N'),
        R('shop', 'T', None, 'shop_stock', 'B', 'match', '1', 'N'),
    ],
))

# ---------------------------------------------------------------- display
DIAGRAMS.append(dict(
    slug='display',
    eyebrow='ER · SPAO FO/BO IA · 전시',
    h1='How a display corner is composed',
    title='SPAO brand mall · display',
    desc='Entity-relationship diagram: a display corner holds ordered items that point polymorphically at banners, snaps, planshops or display categories; categories, planshops and snaps all list products, and IP categories belong to a collaboration IP.',
    sub='BO 전시카테고리관리·전시코너구성관리·배너/기획전/스냅관리, FO 홈·카테고리·기획전·스타일링 클립. ' + SUB_SCHEMA,
    dashed_means='Polymorphic (item_type + item_id)',
    row_gap=72,
    ents=ents(
        E('display_corner', '전시 코너', ['# id bigint', 'store_type text', 'home_type text', 'corner_code text', 'name text', 'display_yn bool'], 'focal'),
        E('display_corner_item', '코너 항목', ['# id bigint', '→ display_corner_id bigint', 'item_type text', 'item_id bigint', 'html text', 'sort_order int']),
        E('banner', '배너', ['# id bigint', 'name text', 'image_url text', 'link_url text', 'start_at timestamptz', 'end_at timestamptz']),
        E('planshop', '기획전', ['# id bigint', 'title text', 'template_type text', 'thumbnail_url text', 'start_at timestamptz', 'status text']),
        E('snap', '스타일링 클립', ['# id bigint', 'title text', 'gender_type text', 'media_type text', 'media_url text', 'status text']),
        E('display_category', '전시 카테고리', ['# id bigint', '→ parent_id bigint', 'category_type text', 'home_type text', '→ collab_ip_id bigint', 'name text', 'depth smallint']),
        E('collab_ip', '컬래버 IP', ['# id bigint', 'name text', 'logo_url text', 'launch_date date', 'status text']),
        E('product', '상품', ['# id bigint', 'product_code text', 'name text'], w=240),
    ),
    grid=[
        ['banner', 'display_corner_item', 'display_corner', None],
        ['planshop', 'snap', 'display_category', 'collab_ip'],
        [None, 'product', None, None],
    ],
    rels=[
        R('display_corner', 'L', 'match', 'display_corner_item', 'R', 0.5, '1', 'N'),
        R('display_corner_item', 'L', 'match', 'banner', 'R', 0.5, 'N', '0..1', dashed=True),
        R('display_corner_item', 'B', 0.25, 'planshop', 'T', 0.5, 'N', '0..1', dashed=True, via=('y', 0, -16)),
        R('display_corner_item', 'B', None, 'snap', 'T', 'match', 'N', '0..1', dashed=True),
        R('display_corner_item', 'B', 0.75, 'display_category', 'T', 0.5, 'N', '0..1', dashed=True, via=('y', 0, 16)),
        R('collab_ip', 'L', 'match', 'display_category', 'R', 0.5, '1', 'N'),
        R('display_category', 'B', None, 'product', 'T', 0.9, 'N', 'N', 'CATEGORY_PRODUCT', via=('y', 1, -16), lab=(1, 'above')),
        R('snap', 'B', None, 'product', 'T', 'match', 'N', 'N', 'SNAP_PRODUCT', lab=(0, None, ('y', 1))),
        R('planshop', 'B', None, 'product', 'T', 0.1, 'N', 'N', 'PLANSHOP_PRODUCT', via=('y', 1, 16), lab=(1, 'below')),
    ],
))

# ---------------------------------------------------------------- order
DIAGRAMS.append(dict(
    slug='order',
    eyebrow='ER · SPAO FO/BO IA · 주문',
    h1='An order, its lines, and what happens to them',
    title='SPAO brand mall · order',
    desc='Entity-relationship diagram: a member places an order made of order items for product SKUs; the order carries delivery legs and applied benefits, and claims (cancel, exchange, return) select order items, optionally naming an exchange SKU.',
    sub='FO 장바구니·주문서·주문내역·취소/교환/반품, BO 주문관리·배송관리·클레임관리. ' + SUB_SCHEMA,
    dashed_means='Optional (0..1)',
    ents=ents(
        E('member', '회원', ['# id bigint', 'login_id text', 'name text']),
        E('orders', '주문', ['# id bigint', 'order_no text', '→ member_id bigint', '→ channel_id bigint', 'order_type text', 'status text', '→ pickup_shop_id bigint', 'pay_amount int'], 'focal'),
        E('order_delivery', '배송', ['# id bigint', '→ order_id bigint', 'seq smallint', 'recipient text', 'address1 text', 'invoice_no text', 'status text']),
        E('claim', '클레임', ['# id bigint', 'claim_no text', '→ order_id bigint', 'claim_type text', 'status text', '→ pickup_shop_id bigint', 'requested_at timestamptz']),
        E('order_benefit', '적용 혜택', ['# id bigint', '→ order_id bigint', '→ order_item_id bigint', 'benefit_type text', '→ member_coupon_id bigint', '→ promotion_id bigint', 'amount int']),
        E('order_item', '주문 상품', ['# id bigint', '→ order_id bigint', '→ product_sku_id bigint', 'qty int', 'unit_price int', 'status text', 'promised_date date']),
        E('claim_item', '클레임 상품', ['# id bigint', '→ claim_id bigint', '→ order_item_id bigint', 'qty int', '→ exchange_sku_id bigint']),
        E('product_sku', '단품', ['# id bigint', '→ product_id bigint', 'sku_code text', 'stock_qty int']),
    ),
    grid=[
        [None, 'member', None],
        ['order_delivery', 'orders', 'claim'],
        ['order_benefit', 'order_item', 'claim_item'],
        [None, 'product_sku', None],
    ],
    rels=[
        R('member', 'B', None, 'orders', 'T', 'match', '1', 'N', 'PLACES'),
        R('orders', 'L', 0.3, 'order_delivery', 'R', 'match', '1', 'N'),
        R('orders', 'R', 0.3, 'claim', 'L', 'match', '1', 'N'),
        R('orders', 'B', None, 'order_item', 'T', 'match', '1', 'N'),
        R('orders', 'B', 0.2, 'order_benefit', 'T', 0.5, '1', 'N', via=('y', 1)),
        R('order_item', 'L', 0.5, 'order_benefit', 'R', 'match', '0..1', 'N', dashed=True),
        R('order_item', 'R', 0.5, 'claim_item', 'L', 'match', '1', 'N'),
        R('claim', 'B', None, 'claim_item', 'T', 'match', '1', 'N'),
        R('order_item', 'B', None, 'product_sku', 'T', 'match', 'N', '1'),
        R('claim_item', 'B', None, 'product_sku', 'T', 0.8, 'N', '0..1', 'EXCHANGE_SKU', dashed=True, via=('y', 2), lab=(1, 'above')),
    ],
))

# ---------------------------------------------------------------- promotion
DIAGRAMS.append(dict(
    slug='promotion',
    eyebrow='ER · SPAO FO/BO IA · 마케팅',
    h1='Promotions, the coupons they issue, and events',
    title='SPAO brand mall · promotion and event',
    desc='Entity-relationship diagram: a promotion targets products or categories and is issued to members as member coupons, optionally through a coupon code; events collect member entries and pick winners from those entries.',
    sub='BO 프로모션관리·이벤트관리·회원혜택관리, FO 쿠폰받기·쿠폰 적용·이벤트 응모. ' + SUB_SCHEMA,
    dashed_means='Optional (0..1)',
    ents=ents(
        E('promotion_target', '적용 대상', ['# id bigint', '→ promotion_id bigint', 'target_type text', 'target_id bigint']),
        E('promotion', '프로모션', ['# id bigint', 'name text', 'promo_type text', 'discount_type text', 'discount_value int', '→ gift_product_id bigint', 'start_at timestamptz', 'status text'], 'focal'),
        E('coupon_code', '쿠폰 코드', ['# id bigint', '→ promotion_id bigint', 'code text', 'max_issue int', 'issued_count int']),
        E('member', '회원', ['# id bigint', 'login_id text', 'name text', 'grade_code text']),
        E('member_coupon', '발급 쿠폰', ['# id bigint', '→ member_id bigint', '→ promotion_id bigint', '→ coupon_code_id bigint', 'use_channel text', 'issue_source text', 'status text', '→ order_id bigint']),
        E('event_entry', '이벤트 응모', ['# id bigint', '→ event_id bigint', '→ member_id bigint', 'entry_data text', 'entered_at timestamptz']),
        E('event', '이벤트', ['# id bigint', 'title text', 'entry_mode text', 'entry_type text', 'start_at timestamptz', 'status text']),
        E('event_winner', '이벤트 당첨', ['# id bigint', '→ event_id bigint', '→ event_entry_id bigint', 'rank smallint', 'prize_type text', 'prize_ref_id bigint', 'status text']),
    ),
    grid=[
        ['promotion_target', 'promotion', 'coupon_code'],
        ['member', 'member_coupon', None],
        ['event_entry', 'event', 'event_winner'],
    ],
    rels=[
        R('promotion', 'L', 'match', 'promotion_target', 'R', 0.5, '1', 'N'),
        R('promotion', 'R', 'match', 'coupon_code', 'L', 0.5, '1', 'N'),
        R('promotion', 'B', 0.35, 'member_coupon', 'T', 'match', '1', 'N', 'ISSUES'),
        R('coupon_code', 'B', None, 'member_coupon', 'T', 0.75, '0..1', 'N', dashed=True, via=('y', 0)),
        R('member', 'R', 'match', 'member_coupon', 'L', 0.5, '1', 'N'),
        R('member', 'B', None, 'event_entry', 'T', 'match', '1', 'N', 'ENTERS'),
        R('event', 'L', 'match', 'event_entry', 'R', 0.5, '1', 'N'),
        R('event', 'R', 'match', 'event_winner', 'L', 0.5, '1', 'N'),
        R('event_entry', 'B', None, 'event_winner', 'B', None, '1', '0..1', 'WINS', dashed=True, via=('y', 2), lab=(1, 'below')),
    ],
))

# ---------------------------------------------------------------- settlement
DIAGRAMS.append(dict(
    slug='settlement',
    eyebrow='ER · SPAO FO/BO IA · 결제·포인트·정산',
    h1='Where the money goes: payment, points, settlement',
    title='SPAO brand mall · payment, point and settlement',
    desc='Entity-relationship diagram: an order in a sales channel is paid by payments and may earn or spend member points in a ledger; refunds reverse payments, and settlements per channel aggregate payment and order lines.',
    sub='FO 주문서 결제·포인트, BO 결제관리·정산관리·채널관리. ' + SUB_SCHEMA,
    dashed_means='Optional (0..1)',
    ents=ents(
        E('member', '회원', ['# id bigint', 'login_id text', 'name text', 'grade_code text']),
        E('orders', '주문', ['# id bigint', 'order_no text', '→ member_id bigint', '→ channel_id bigint', 'status text', 'pay_amount int']),
        E('channel', '채널', ['# id bigint', 'code text', 'name text', 'channel_type text']),
        E('point_ledger', '포인트 원장', ['# id bigint', '→ member_id bigint', 'point_type text', 'tx_type text', 'amount int', 'balance_after int', 'available_at timestamptz', '→ order_id bigint']),
        E('payment', '결제', ['# id bigint', '→ order_id bigint', 'pay_method text', 'pg_tid text', 'amount int', 'status text', 'approved_at timestamptz'], 'focal'),
        E('settlement', '정산', ['# id bigint', 'settle_type text', 'settle_date date', '→ vendor_id bigint', '→ channel_id bigint', 'amount int', 'status text', 'sap_sent_at timestamptz']),
        E('refund', '환불', ['# id bigint', '→ claim_id bigint', '→ payment_id bigint', 'amount int', 'refund_method text', 'account_verified bool', 'status text']),
        E('settlement_line', '정산 명세', ['# id bigint', '→ settlement_id bigint', '→ order_id bigint', '→ payment_id bigint', 'line_type text', 'amount int']),
    ),
    grid=[
        ['member', 'orders', 'channel'],
        ['point_ledger', 'payment', 'settlement'],
        [None, 'refund', 'settlement_line'],
    ],
    rels=[
        R('member', 'R', 'match', 'orders', 'L', 0.5, '1', 'N'),
        R('member', 'B', 0.35, 'point_ledger', 'T', 'match', '1', 'N'),
        R('orders', 'B', 0.2, 'point_ledger', 'T', 0.75, '0..1', 'N', dashed=True, via=('y', 0)),
        R('orders', 'B', 0.6, 'payment', 'T', 'match', '1', 'N'),
        R('channel', 'L', 'match', 'orders', 'R', 0.5, '0..1', 'N', dashed=True),
        R('channel', 'B', None, 'settlement', 'T', 'match', '1', 'N'),
        R('settlement', 'B', 0.6, 'settlement_line', 'T', 'match', '1', 'N'),
        R('payment', 'B', 0.75, 'settlement_line', 'T', 0.2, '0..1', 'N', dashed=True, via=('y', 1)),
        R('payment', 'B', 0.3, 'refund', 'T', 'match', '1', 'N'),
    ],
))

# ---------------------------------------------------------------- system
DIAGRAMS.append(dict(
    slug='system',
    eyebrow='ER · SPAO FO/BO IA · BO 시스템',
    h1='Who may open which BO menu and URL',
    title='SPAO brand mall · BO users, roles, menus and URLs',
    desc='Entity-relationship diagram: back-office users hold roles; a role grants menus and URL groups, and each URL master row belongs to one URL group.',
    sub='BO 시스템관리 › 권한관리·사용자관리. ' + SUB_SCHEMA,
    ents=ents(
        E('bo_user', 'BO 사용자', ['# id bigint', 'login_id text', 'name text', 'status text', 'account_expires_at date']),
        E('bo_user_role', '사용자·역할', ['→ bo_user_id bigint', '→ bo_role_id bigint'], 'join'),
        E('bo_role', '역할', ['# id bigint', 'code text', 'name text', 'description text'], 'focal'),
        E('bo_role_menu', '역할·메뉴', ['→ bo_role_id bigint', '→ bo_menu_id bigint'], 'join'),
        E('bo_menu', 'BO 메뉴', ['# id bigint', '→ parent_id bigint', 'name text', 'url text', 'depth smallint', 'use_yn bool']),
        E('bo_role_url_group', 'URL 권한', ['→ bo_role_id bigint', '→ bo_url_group_id bigint'], 'join'),
        E('bo_url_group', 'URL 그룹', ['# id bigint', 'code text', 'name text']),
        E('bo_url', 'URL 마스터', ['# id bigint', '→ bo_url_group_id bigint', 'url_pattern text', 'method text', 'name text']),
    ),
    grid=[
        ['bo_user', 'bo_user_role', 'bo_role'],
        ['bo_menu', 'bo_role_menu', 'bo_role_url_group'],
        [None, 'bo_url', 'bo_url_group'],
    ],
    rels=[
        R('bo_user', 'R', 'match', 'bo_user_role', 'L', 0.5, '1', 'N'),
        R('bo_role', 'L', 'match', 'bo_user_role', 'R', 0.5, '1', 'N'),
        R('bo_role', 'B', 0.3, 'bo_role_menu', 'T', 0.5, '1', 'N', via=('y', 0)),
        R('bo_menu', 'R', 'match', 'bo_role_menu', 'L', 0.5, '1', 'N'),
        R('bo_role', 'B', 0.7, 'bo_role_url_group', 'T', 'match', '1', 'N'),
        R('bo_url_group', 'T', None, 'bo_role_url_group', 'B', 'match', '1', 'N'),
        R('bo_url_group', 'L', 'match', 'bo_url', 'R', 0.5, '1', 'N'),
    ],
))


# ================================================================= domain map
# erd-map.html: all 85 tables at once, grouped into the nine erd-schema.md domains.
# Zone boxes quack like E, so route()/label_box()/check() are reused unchanged.
MAP_VB_W, MAP_MARGIN = 1360, 56
ZONE_W, ZONE_GAP_X, ZONE_GAP_Y = 352, 96, 64
NAME_PAD = 16


def parse_domains():
    """erd-schema.md -> ([(domain, [table, ...]), ...], {table: domain}, {(a, b): [col, ...]})"""
    order, tables, fks = [], {}, collections.defaultdict(list)
    domain = table = None
    in_code = False
    for line in SCHEMA_MD.read_text().splitlines():
        if line.startswith('```'):
            in_code = not in_code
            continue
        if not in_code:
            m = re.match(r'^## \d+\. (.+?) \(', line)
            if m:
                domain = m.group(1)
                order.append((domain, []))
                continue
            m = re.match(r'^### (\S+)', line)
            if m and domain:
                table = m.group(1)
                order[-1][1].append(table)
                tables[table] = domain
            continue
        if table:
            m = re.match(r'^\s*([a-z_][a-z0-9_]*)\s+\S.*?→\s*([a-z_][a-z0-9_]*)', line)
            if m:
                fks[table].append((m.group(1), ALIAS.get(m.group(2), m.group(2))))
    cross = collections.defaultdict(list)
    for src, refs in fks.items():
        for col, dst in refs:
            assert dst in tables, f'{src}.{col} points at unknown table {dst}'
            if tables[src] != tables[dst]:
                cross[(tables[src], tables[dst])].append(f'{src}.{col}')
    return order, tables, cross


class Z:
    """A domain zone. Exposes the E surface that route/label_box/check rely on."""

    def __init__(self, ko, tag, tables, style='entity', href=None, ncols=2, w=ZONE_W):
        self.key, self.ko, self.tag, self.tables = tag, ko, tag, tables
        self.style, self.href, self.ncols, self.w = style, href, ncols, w
        self.fields, self.more = [], 0
        self.x = self.y = self.h = 0

    @property
    def rows(self):
        return -(-len(self.tables) // self.ncols)

    def columns(self):
        """Column-major fill: read down, then across."""
        n = self.rows
        return [self.tables[i:i + n] for i in range(0, len(self.tables), n)]


def build_map():
    order, _, cross = parse_domains()
    by_domain = dict(order)
    meta = {
        '회원': ('MEMBER', 'erd-member.html'),
        '업체·매장': ('VENDOR · SHOP', 'erd-product.html'),
        '상품': ('PRODUCT', 'erd-product.html'),
        '전시': ('DISPLAY', 'erd-display.html'),
        '주문': ('ORDER', 'erd-order.html'),
        '결제·포인트·정산': ('PAYMENT · SETTLEMENT', 'erd-settlement.html'),
        '마케팅': ('MARKETING', 'erd-promotion.html'),
        '고객지원·검색': ('CS · SEARCH', None),
        'BO 시스템': ('BO SYSTEM', 'erd-system.html'),
    }
    assert set(meta) == set(by_domain), 'erd-schema.md domains changed; update meta'

    def zone(name, **kw):
        tag, href = meta[name]
        return Z(name, tag, by_domain[name], href=href, **kw)

    grid = [
        ['업체·매장', '상품', '전시'],
        ['회원', '주문', '마케팅'],
        ['고객지원·검색', '결제·포인트·정산', None],
    ]
    zones = {}
    for name in meta:
        if name == 'BO 시스템':
            zones[name] = zone(name, style='join', ncols=4, w=MAP_VB_W - 2 * MAP_MARGIN)
        else:
            zones[name] = zone(name, style='focal' if name == '주문' else 'entity')

    # geometry: uniform box height per grid row, BO system as a full-width foundation bar
    for i, row in enumerate(grid):
        for j, name in enumerate(row):
            if name:
                zones[name].x = MAP_MARGIN + j * (ZONE_W + ZONE_GAP_X)
    y = TOP
    for row in grid:
        h = 60 + 20 * max(zones[n].rows for n in row if n)
        for name in row:
            if name:
                zones[name].y, zones[name].h = y, h
        y += h + ZONE_GAP_Y
    bo = zones['BO 시스템']
    bo.x, bo.y, bo.h = MAP_MARGIN, y, 60 + 20 * bo.rows

    ents = {z.key: z for z in zones.values()}
    Q = {name: zones[name].key for name in zones}
    rels = [
        R(Q['업체·매장'], 'R', 96, Q['상품'], 'L', 96, '1', 'N', 'SUPPLIES'),
        R(Q['상품'], 'R', 96, Q['전시'], 'L', 96, 'N', 'N', 'DISPLAYS'),
        R(Q['상품'], 'B', 160, Q['주문'], 'T', 160, 'N', 'N', 'ORDER_ITEM'),
        R(Q['회원'], 'R', 88, Q['주문'], 'L', 88, '1', 'N', 'PLACES'),
        R(Q['주문'], 'R', 88, Q['마케팅'], 'L', 88, 'N', 'N', 'ORDER_BENEFIT'),
        R(Q['주문'], 'B', 160, Q['결제·포인트·정산'], 'T', 160, '1', 'N', 'PAYMENT'),
        R(Q['회원'], 'T', 160, Q['업체·매장'], 'B', 160, 'N', '0..1', 'FAVORITE_SHOP', dashed=True),
        R(Q['회원'], 'B', 160, Q['고객지원·검색'], 'T', 160, '1', 'N', 'INQUIRY'),
    ]
    d = dict(
        slug='map', max_ents=9,
        eyebrow='ER · SPAO FO/BO IA · 전체 도메인 맵',
        h1='All 85 tables, nine domains, one page',
        title='SPAO brand mall · domain map',
        desc='Domain map of the whole schema: nine domain zones list every table, and eight labelled relationships join them along the spine from vendor and product through order to payment and settlement, over a shared BO system foundation.',
        sub='도메인 존을 클릭하면 해당 상세 ERD로 이동한다. 컬럼은 <a href="erd-schema.html">erd-schema.html</a>, '
            '도메인 간 관계는 아래 표에 전부 적혀 있다.',
        dashed_means='Optional (0..1)',
        ents=ents, rels=rels,
    )
    for r in rels:
        route(d, r)
        r.marks = [card_mark(r.pts[0], r.pts[1], r.sc), card_mark(r.pts[-1], r.pts[-2], r.dc)]
        r.labelbox = label_box(d, r.pts, r.label, r.lab)
    errs = check(d)
    for z in ents.values():
        room = (z.w - 2 * NAME_PAD) // z.ncols
        for name in z.tables:
            if len(name) * CH10 > room - 8:
                errs.append(f'{z.ko}: "{name}" needs {len(name) * CH10:.0f}px, column holds {room - 8}')
    if errs:
        print('[map] FAILED')
        for e in errs:
            print('   -', e)
        return False
    d['extra'] = fk_table(cross)
    svg, vb_h = render_map(d)
    page = PAGE.format(title=t(d['title']), eyebrow=t(d['eyebrow']), h1=t(d['h1']),
                       sub=d['sub'], svg='\n'.join('    ' + l for l in svg.splitlines()),
                       extra=d['extra'])
    path = ROOT / 'erd-map.html'
    path.write_text(page)
    total = sum(len(z.tables) for z in zones.values())
    print(f'[map] ok  zones={len(zones)} tables={total} rels={len(rels)} '
          f'viewBox={MAP_VB_W}x{vb_h} -> {path.name}')
    return True


def render_map(d):
    ents, rels = d['ents'], d['rels']
    bottom = max(z.y + z.h for z in ents.values())
    legend_y = r4(bottom + 56)
    vb_h = legend_y + 44
    out = [f'<svg viewBox="0 0 {MAP_VB_W} {vb_h}" xmlns="http://www.w3.org/2000/svg" '
           f'role="img" aria-labelledby="erd-map-title erd-map-desc">',
           f'  <title id="erd-map-title">{t(d["title"])}</title>',
           f'  <desc id="erd-map-desc">{t(d["desc"])}</desc>',
           f'  <rect width="100%" height="100%" fill="{PAPER}"/>',
           '  <!-- relationships (drawn before boxes) -->']
    for r in rels:
        dash = ' stroke-dasharray="5,4"' if r.dashed else ''
        out.append(f'  <path d="{path_d(r.pts)}" fill="none" stroke="{MUTED}" stroke-width="1"{dash}/>')
    for r in rels:
        for m in r.marks:
            out.append(f'  <text x="{m["x"]}" y="{m["y"]}" fill="{MUTED}" font-size="10" font-weight="600" '
                       f'font-family="{MONO}" text-anchor="{m["anchor"]}">{t(m["text"])}</text>')
    for r in rels:
        lb = r.labelbox
        x, y, w, h = lb['rect']
        out.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{PAPER}"/>')
        out.append(f'  <text x="{lb["x"]}" y="{lb["y"]}" fill="{SOFT}" font-size="8" font-family="{MONO}" '
                   f'text-anchor="middle" letter-spacing="0.12em">{t(lb["text"])}</text>')
    for z in ents.values():
        out.extend(render_zone(z))
    out.extend(render_map_legend(legend_y))
    out.append('</svg>')
    return '\n'.join(out), vb_h


def render_zone(z):
    s = STYLES[z.style]
    x, y, w = z.x, z.y, z.w
    o = [f'  <!-- {z.ko} -->']
    if z.href:
        o.append(f'  <a href="{z.href}">')
    o.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{z.h}" rx="6" fill="{PAPER}"/>')
    o.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{z.h}" rx="6" fill="{s["fill"]}" '
             f'stroke="{s["stroke"]}" stroke-width="1"{s["dash"]}/>')
    o.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{HEAD_H}" rx="6" fill="{s["head"]}"/>')
    o.append(f'  <rect x="{x}" y="{y + HEAD_H - 8}" width="{w}" height="8" fill="{s["head"]}"/>')
    o.append(f'  <line x1="{x}" y1="{y + HEAD_H}" x2="{x + w}" y2="{y + HEAD_H}" stroke="{s["rule"]}" stroke-width="1"/>')
    o.append(f'  <text x="{x + 16}" y="{y + 16}" fill="{s["tag"]}" font-size="8" font-family="{MONO}" '
             f'letter-spacing="0.14em">{t(z.tag)}</text>')
    o.append(f'  <text x="{x + 16}" y="{y + 32}" fill="{INK}" font-size="12" font-weight="600" '
             f'font-family="{SANS}">{t(z.ko)}</text>')
    o.append(f'  <text x="{x + w - 16}" y="{y + 32}" fill="{MUTED}" font-size="10" font-family="{MONO}" '
             f'text-anchor="end">{len(z.tables)} tables</text>')
    colw = (w - 2 * NAME_PAD) // z.ncols
    for ci, col in enumerate(z.columns()):
        cx = x + NAME_PAD + ci * colw
        for ri, name in enumerate(col):
            o.append(f'  <text x="{cx}" y="{y + 58 + ri * ROW_H}" fill="{INK}" font-size="10" '
                     f'font-family="{MONO}">{t(name)}</text>')
    if z.href:
        o.append('  </a>')
    return o


def render_map_legend(ly):
    items = [('box', 'entity', '도메인 존 — 클릭하면 상세 ERD'),
             ('box', 'focal', '주문 — 도메인이 모이는 허브'),
             ('box', 'join', '전 도메인이 참조하는 공통 기반'),
             ('line', 'dashed', 'Optional (0..1)'),
             ('glyph', '1 / N', 'Cardinality')]
    o = ['  <!-- legend -->',
         f'  <line x1="{MAP_MARGIN}" y1="{ly - 8}" x2="{MAP_VB_W - MAP_MARGIN}" y2="{ly - 8}" '
         f'stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>',
         f'  <text x="{MAP_MARGIN}" y="{ly + 8}" fill="{MUTED}" font-size="8" font-family="{MONO}" '
         f'letter-spacing="0.18em">LEGEND</text>']
    x, yy = MAP_MARGIN, ly + 24
    for kind, key, text in items:
        if kind == 'box':
            s = STYLES[key]
            o.append(f'  <rect x="{x}" y="{yy}" width="14" height="10" rx="2" fill="{s["fill"]}" '
                     f'stroke="{s["stroke"]}" stroke-width="1"{s["dash"]}/>')
            tx = x + 20
        elif kind == 'glyph':
            o.append(f'  <text x="{x}" y="{yy + 9}" fill="{INK}" font-size="10" font-weight="600" '
                     f'font-family="{MONO}">{t(key)}</text>')
            tx = x + len(key) * 6 + 8
        else:
            o.append(f'  <line x1="{x}" y1="{yy + 5}" x2="{x + 24}" y2="{yy + 5}" stroke="{MUTED}" '
                     f'stroke-width="1" stroke-dasharray="5,4"/>')
            tx = x + 30
        o.append(f'  <text x="{tx}" y="{yy + 8}" fill="{MUTED}" font-size="8.5" font-family="{SANS}">{t(text)}</text>')
        x = r4(tx + len(text) * 7.4 + 36)
    return o


def fk_table(cross):
    """Every cross-domain FK. bo_user audit columns are one note, not 6 rows."""
    audit = sorted(c for (a, b), cols in cross.items() if b == 'BO 시스템' for c in cols)
    rows = sorted(((a, b, cols) for (a, b), cols in cross.items() if b != 'BO 시스템'),
                  key=lambda r: (-len(r[2]), r[0]))
    body = '\n'.join(
        f'        <tr><td>{t(a)}</td><td>{t(b)}</td><td>{t(", ".join(sorted(cols)))}</td></tr>'
        for a, b, cols in rows)
    n = sum(len(c) for _, _, c in rows) + len(audit)
    return f'''    <section class="fk">
      <h2>도메인 간 외래키 · {n}개 컬럼</h2>
      <table>
        <thead><tr><th>참조하는 도메인</th><th>참조되는 도메인</th><th>외래키 컬럼</th></tr></thead>
        <tbody>
{body}
        </tbody>
      </table>
      <p class="note">위 {len(rows)}쌍 외에, <code>bo_user</code>를 가리키는 감사 컬럼 {len(audit)}개(<code>{t(", ".join(audit))}</code>)가
      모든 도메인에서 <b>BO 시스템</b>을 참조한다. 선으로 그리면 전 도메인이 한 점에 모여 읽을 수 없으므로 그리지 않았다.
      <code>common_code</code>와 <code>holiday</code>도 같은 이유로 문자열 코드로만 참조된다.</p>
    </section>'''

# ================================================================= schema page
# erd-schema.md -> erd-schema.html. Handles only the markdown this doc uses:
# #/##/### headings, paragraphs, - bullets, | tables |, ``` fences, ---, **bold**,
# `code`, [text](url). Same shell and tokens as docs/convention/coding-convention.html.

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    return s


def section_id(title, n):
    m = re.search(r'\(([a-z_, ]+)\)\s*$', title)
    return re.sub(r'[^a-z_]+', '-', m.group(1)).strip('-') if m else f's{n}'


def md_blocks(md):
    """Yield (kind, payload) blocks from the markdown source."""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            j = i + 1
            while not lines[j].startswith('```'):
                j += 1
            yield 'pre', '\n'.join(lines[i + 1:j])
            i = j + 1
        elif line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            yield f'h{level}', line[level:].strip()
            i += 1
        elif line.startswith('|'):
            j = i
            while j < len(lines) and lines[j].startswith('|'):
                j += 1
            rows = [[c.strip() for c in r.strip('|').split('|')] for r in lines[i:j] if not re.match(r'^\|[-| ]+\|$', r)]
            yield 'table', rows
            i = j
        elif line.startswith('- '):
            j = i
            while j < len(lines) and lines[j].startswith('- '):
                j += 1
            yield 'ul', [l[2:] for l in lines[i:j]]
            i = j
        elif line.strip() in ('', '---'):
            i += 1
        else:
            j = i
            while j < len(lines) and lines[j].strip() and not lines[j].startswith(('#', '|', '- ', '```')):
                j += 1
            yield 'p', ' '.join(l.strip() for l in lines[i:j])
            i = j


def render_schema_page():
    md = SCHEMA_MD.read_text()
    blocks = list(md_blocks(md))
    title = next(p for k, p in blocks if k == 'h1')
    head, sections, cur = [], [], None
    for kind, payload in blocks:
        if kind == 'h1':
            continue
        if kind == 'h2':
            cur = dict(title=payload, id=section_id(payload, len(sections) + 1), body=[])
            sections.append(cur)
            continue
        (cur['body'] if cur else head).append((kind, payload))

    def render_body(body, in_rule=False):
        out, rule_open = [], False
        for kind, payload in body:
            if kind == 'h3':
                if rule_open:
                    out.append('        </div>')
                name = payload.split(' ')[0]
                out.append(f'        <div class="rule" id="t-{html.escape(name)}">')
                out.append(f'          <h3>{inline(payload)}</h3>')
                rule_open = True
            elif kind == 'p':
                if payload.startswith('IA:'):
                    out.append(f'          <p class="why"><b>IA</b>{inline(payload[3:].strip())}</p>')
                elif payload.startswith('**') and not rule_open:
                    lead, rest = re.match(r'\*\*(.+?)\*\*\s*(.*)', payload).groups()
                    out.append(f'      <div class="hazard"><b>{inline(lead)}</b>{inline(rest)}</div>')
                else:
                    out.append(f'      <p>{inline(payload)}</p>')
            elif kind == 'pre':
                out.append(f'<pre><code>{html.escape(payload, quote=False)}</code></pre>')
            elif kind == 'ul':
                out.append('      <ul class="plain">')
                out.extend(f'        <li>{inline(item)}</li>' for item in payload)
                out.append('      </ul>')
            elif kind == 'table':
                hdr, rows = payload[0], payload[1:]
                out.append('      <div class="tw"><table>')
                out.append('        <thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in hdr) + '</tr></thead>')
                out.append('        <tbody>')
                out.extend('          <tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in rows)
                out.append('        </tbody>')
                out.append('      </table></div>')
        if rule_open:
            out.append('        </div>')
        return out

    nav = '\n'.join(f'      <li><a href="#{s["id"]}">{inline(s["title"])}</a></li>' for s in sections)
    header = []
    for kind, payload in head:
        if kind == 'p' and payload.startswith('**'):
            lead, rest = re.match(r'\*\*(.+?)\*\*\s*(.*)', payload).groups()
            header.append(f'      <div class="hazard"><b>{inline(lead)}</b>{inline(rest)}</div>')
        elif kind == 'p':
            header.append(f'      <p class="standfirst">{inline(payload)}</p>')
    body = []
    for s in sections:
        body.append(f'    <section id="{s["id"]}">')
        body.append(f'      <h2>{inline(s["title"])}</h2>')
        rules = [b for b in s['body'] if b[0] == 'h3']
        if rules:
            body.append('      <div class="rules">')
            body.extend(render_body(s['body']))
            body.append('      </div>')
        else:
            body.extend(render_body(s['body']))
        body.append('    </section>')
    page = SCHEMA_PAGE.format(title=html.escape(title), nav=nav, header='\n'.join(header), body='\n'.join(body))
    path = ROOT / 'erd-schema.html'
    path.write_text(page)
    print(f'[schema] ok  sections={len(sections)} tables={sum(1 for k, _ in blocks if k == "h3")} -> {path.name}')


SCHEMA_PAGE = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
  :root {{
    --ground:      #f1f4f3;
    --surface:     #ffffff;
    --surface-alt: #e9edec;
    --ink:         #17201e;
    --ink-soft:    #596764;
    --ink-faint:   #7f8c89;
    --rule:        #d7dedc;
    --rule-strong: #b9c4c1;
    --accent:      #0f6b5c;
    --accent-soft: #e0eeea;
    --warn:        #8a5311;
    --warn-soft:   #f6ecdd;
    --shadow:      0 1px 2px rgba(23, 32, 30, .05);
    --sans: "IBM Plex Sans KR", system-ui, -apple-system, "Apple SD Gothic Neo", sans-serif;
    --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --ground: #0e1514; --surface: #161f1d; --surface-alt: #1d2725;
      --ink: #e4eae8; --ink-soft: #97a5a1; --ink-faint: #74827f;
      --rule: #26302e; --rule-strong: #38443f;
      --accent: #4ec9b0; --accent-soft: #16302b;
      --warn: #d99a4e; --warn-soft: #2c2216;
      --shadow: 0 1px 2px rgba(0, 0, 0, .3);
    }}
  }}
  :root[data-theme="dark"] {{
    --ground: #0e1514; --surface: #161f1d; --surface-alt: #1d2725;
    --ink: #e4eae8; --ink-soft: #97a5a1; --ink-faint: #74827f;
    --rule: #26302e; --rule-strong: #38443f;
    --accent: #4ec9b0; --accent-soft: #16302b;
    --warn: #d99a4e; --warn-soft: #2c2216;
    --shadow: 0 1px 2px rgba(0, 0, 0, .3);
  }}

  *, *::before, *::after {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{ margin: 0; background: var(--ground); color: var(--ink); font-family: var(--sans); font-size: 16px; line-height: 1.72; }}
  a {{ color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }}
  a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }}

  .shell {{ display: grid; grid-template-columns: 232px minmax(0, 1fr); gap: 56px; max-width: 1140px; margin: 0 auto; padding: 0 32px 120px; }}
  .nav {{ position: sticky; top: 0; align-self: start; max-height: 100vh; overflow-y: auto; padding: 48px 0; }}
  .nav-eyebrow {{ font-family: var(--mono); font-size: 11px; font-weight: 500; text-transform: uppercase; color: var(--ink-faint); margin: 0 0 14px; }}
  .nav ol {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px; }}
  .nav a {{ display: block; padding: 5px 12px; font-size: 14px; line-height: 1.45; color: var(--ink-soft); text-decoration: none; border-left: 2px solid var(--rule); }}
  .nav a:hover {{ color: var(--ink); background: var(--surface-alt); }}
  .nav a[aria-current="true"] {{ color: var(--accent); border-left-color: var(--accent); font-weight: 600; background: var(--accent-soft); }}

  main {{ padding: 48px 0 0; max-width: 78ch; }}
  header.page {{ padding-bottom: 40px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 8px; }}
  .kicker {{ font-family: var(--mono); font-size: 12px; font-weight: 500; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); margin: 0 0 12px; }}
  h1 {{ font-size: 40px; line-height: 1.18; font-weight: 700; letter-spacing: -.02em; margin: 0 0 16px; text-wrap: balance; }}
  .standfirst {{ font-size: 17px; color: var(--ink-soft); margin: 0 0 12px; max-width: 60ch; }}
  section {{ padding-top: 52px; scroll-margin-top: 24px; }}
  h2 {{ font-size: 24px; font-weight: 600; letter-spacing: -.012em; margin: 0 0 18px; text-wrap: balance; }}
  h3 {{ font-size: 16.5px; font-weight: 600; margin: 0 0 8px; letter-spacing: -.005em; }}
  h3 code {{ font-size: 15px; background: none; padding: 0; color: var(--accent); }}
  p {{ margin: 0 0 14px; }}
  .rules {{ display: flex; flex-direction: column; gap: 32px; }}
  .rule {{ scroll-margin-top: 24px; }}
  .rule > :last-child {{ margin-bottom: 0; }}
  .why {{ border-left: 2px solid var(--rule-strong); padding: 2px 0 2px 14px; margin: 0 0 12px; color: var(--ink-soft); font-size: 14.5px; }}
  .why b {{ font-family: var(--mono); font-size: 10.5px; font-weight: 600; text-transform: uppercase; color: var(--ink-faint); display: block; margin-bottom: 2px; }}
  .hazard {{ background: var(--warn-soft); border: 1px solid color-mix(in srgb, var(--warn) 28%, transparent); border-radius: 4px; padding: 16px 18px; margin: 24px 0 0; font-size: 15.5px; }}
  .hazard b {{ font-family: var(--mono); font-size: 10.5px; font-weight: 600; text-transform: uppercase; color: var(--warn); display: block; margin-bottom: 4px; }}

  pre {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 4px; padding: 14px 16px; margin: 0 0 14px; overflow-x: auto; font-family: var(--mono); font-size: 13px; line-height: 1.66; box-shadow: var(--shadow); }}
  code {{ font-family: var(--mono); font-size: .875em; background: var(--surface-alt); padding: 1px 5px; border-radius: 3px; }}
  pre code {{ background: none; padding: 0; font-size: inherit; }}

  .tw {{ overflow-x: auto; margin: 0 0 16px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14.5px; min-width: 460px; }}
  th, td {{ text-align: left; padding: 9px 14px 9px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }}
  th {{ font-family: var(--mono); font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--ink-faint); border-bottom-color: var(--rule-strong); white-space: nowrap; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  ul.plain {{ margin: 0 0 14px; padding-left: 20px; }}
  ul.plain li {{ margin-bottom: 7px; }}

  @media (max-width: 900px) {{
    .shell {{ grid-template-columns: 1fr; gap: 0; padding: 0 22px 80px; }}
    .nav {{ position: static; max-height: none; padding: 32px 0 0; border-bottom: 1px solid var(--rule); }}
    .nav ol {{ flex-direction: row; flex-wrap: wrap; gap: 6px; padding-bottom: 20px; }}
    .nav a {{ border-left: none; border: 1px solid var(--rule); border-radius: 3px; padding: 4px 10px; font-size: 13px; }}
    main {{ padding-top: 32px; }}
    h1 {{ font-size: 31px; }}
  }}
  @media (prefers-reduced-motion: no-preference) {{ html {{ scroll-behavior: smooth; }} }}
</style>
</head>
<body>

<div class="shell">

  <nav class="nav" aria-label="목차">
    <p class="nav-eyebrow">목차</p>
    <ol>
{nav}
    </ol>
  </nav>

  <main>
    <header class="page">
      <p class="kicker">docs/diagrams · from docs/ref IA</p>
      <h1>{title}</h1>
{header}
    </header>

{body}

    <footer>
      <p><code>erd-schema.md</code>에서 <code>erd-gen.py</code>가 생성한 페이지. 원문을 고치고 다시 생성한다.</p>
    </footer>
  </main>

</div>

<script>
  (function () {{
    var links = Array.prototype.slice.call(document.querySelectorAll('.nav a[href^="#"]'));
    var map = {{}};
    links.forEach(function (a) {{
      var el = document.querySelector(a.getAttribute('href'));
      if (el) {{ map[el.id] = a; }}
    }});
    var sections = Object.keys(map).map(function (id) {{ return document.getElementById(id); }});
    if (!sections.length || !('IntersectionObserver' in window)) {{ return; }}
    var visible = new Set();
    function paint() {{
      var current = sections.filter(function (s) {{ return visible.has(s.id); }})[0];
      links.forEach(function (a) {{ a.removeAttribute('aria-current'); }});
      if (current) {{ map[current.id].setAttribute('aria-current', 'true'); }}
    }}
    var io = new IntersectionObserver(function (entries) {{
      entries.forEach(function (e) {{
        if (e.isIntersecting) {{ visible.add(e.target.id); }} else {{ visible.delete(e.target.id); }}
      }});
      paint();
    }}, {{ rootMargin: '0px 0px -70% 0px' }});
    sections.forEach(function (s) {{ io.observe(s); }});
  }})();
</script>

</body>
</html>
'''


if __name__ == '__main__':
    only = set(sys.argv[1:])
    ok = True
    for d in DIAGRAMS:
        if only and d['slug'] not in only:
            continue
        ok &= build(d)
    if not only or 'map' in only:
        ok &= build_map()
    if not only or 'schema' in only:
        render_schema_page()
    sys.exit(0 if ok else 1)
