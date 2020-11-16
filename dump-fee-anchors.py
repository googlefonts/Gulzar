#!/usr/bin/env python3

from glyphsLib import GSFont
import sys

font = GSFont(sys.argv[1])
glyphs = [g.layers[0] for g in font.glyphs if len(g.layers[0].anchors) > 0]
for g in glyphs:
	print("Anchors %s {" % g.parent.name)
	for a in g.anchors:
		print("   %s  <%i %i>" % (a.name, *a.position))
	print("};\n")
