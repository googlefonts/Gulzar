import glyphsLib
import sys
import copy


infile = sys.argv[1]
feafile = sys.argv[2]
gsfont = glyphsLib.GSFont(infile)

for mark in ["sdb", "ddb", "tdb", "KASRA"]:
	if not mark+".yb" in gsfont.glyphs:
		newglyph = copy.deepcopy(gsfont.glyphs[mark])
		newglyph.name = mark+".yb"
		newglyph.unicode = None
		# Delete anchors
		newglyph.layers[0].anchors = []
		gsfont.glyphs.append(newglyph)


gsfont.features = []
fp = glyphsLib.GSFeaturePrefix()
fp.code = 'include(%s);' % feafile
gsfont.featurePrefixes = [fp]
gsfont.save(infile)
