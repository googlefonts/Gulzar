# MenuTitle: Lint Arabic font
# -*- coding: utf-8 -*-
__doc__ = """
Check for errors in a Qalmi-style Arabic font
"""

import sys
import re

if "Glyphs" not in globals():
  import glyphsLib
  infile = sys.argv[1]
  gsfont = glyphsLib.GSFont(infile)
else:
  gsfont = Glyphs.font

def has_anchor(n, anchors):
  for a in anchors:
    if a.name == n: return True
  return False

reachable = set([])
rules = {}

for g in gsfont.glyphs:
  l = g.layers[0]
  if re.search(r"^.*f\d+$", g.name):
    if not has_anchor("entry", l.anchors):
      print("Final glyph %s has no entry anchor" % g.name)
  if re.search(r"^.*i\d+$", g.name):
    if not has_anchor("exit", l.anchors):
      print("Initial glyph %s has no exit anchor" % g.name)
  if re.search(r"^.*m\d+$", g.name):
    if not has_anchor("exit", l.anchors):
      print("Medial glyph %s has no exit anchor" % g.name)
    if not has_anchor("entry", l.anchors):
      print("Medial glyph %s has no entry anchor" % g.name)

  if not g.category == "Mark":
    continue
  for a in l.anchors:
    if a.position.x == 0 and a.position.y == 0:
      print("Badly positioned anchor %s on glyph %s" % (a, g.name))
  if g.name not in ["sda", "dda", "tda", "sdb", "ddb", "tdb", "sdb.yb", "ddb.yb", "tdb.yb"]:
    if has_anchor("top", l.anchors) and g.name != "SHADDA":
      print("%s should not have a top anchor" % g.name)
    if has_anchor("bottom", l.anchors):
      print("%s should not have a bottom anchor" % g.name)

  if not has_anchor("top", l.anchors) and g.name == "SHADDA":
    print("%s should have a top anchor" % g.name)

  # Ensure above marks have _top anchors
  if g.name in ["SHADDA", "DAMMA"]:
    if not has_anchor("_top", l.anchors):
      print("%s should have a _top anchor" % g.name)

  if g.name in []:
    if not has_anchor("_bottom", l.anchors):
      print("%s should have a _bottom anchor" % g.name)
