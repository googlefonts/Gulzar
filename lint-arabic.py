import glyphsLib
import sys
import copy
import re
import csv


infile = sys.argv[1]
gsfont = glyphsLib.GSFont(infile)

def has_anchor(n, anchors):
  for a in anchors:
    if a.name == n: return True
  return False

reachable = set([])
rules = {}

with open("rules.csv") as csvfile:
    reader = csv.DictReader(csvfile)
    for line in reader:
        left_glyph = line["Left Glyph"]
        if not left_glyph in gsfont.glyphs:
            continue
        remainder = list(line.items())[1:]
        for (g, v) in remainder:
            old = g + "1"
            if v == "1" or v == 1 or not v:
                continue
            replacement = g + str(v)
            if not replacement in gsfont.glyphs:
                continue
            if not old in rules:
                rules[old] = {}
            if not replacement in rules[old]:
                rules[old][replacement] = []
            rules[old][replacement].append(left_glyph)

for oldglyph in rules:
    for replacement in rules[oldglyph]:
        context = rules[oldglyph][replacement]
        reachable |= set(context)
        reachable |= set([oldglyph, replacement])


for g in gsfont.glyphs:
  l = g.layers[0]
  if not l.paths:
    continue
  if not g.name in reachable:
    continue
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
