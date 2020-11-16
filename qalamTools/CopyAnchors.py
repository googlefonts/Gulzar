import fontFeatures

GRAMMAR = """
CopyAnchors_Args = <letter+>:fromprefix ws <letter+>:toprefix -> (fromprefix, toprefix)
"""
VERBS = ["CopyAnchors"]


class CopyAnchors:
    @classmethod
    def action(self, parser, fromprefix, toprefix):
        glyphs = parser.font.keys()
        for g in glyphs:
        	if g not in parser.fontfeatures.anchors: continue
        	if g.startswith(fromprefix):
        		g2 = g.replace(fromprefix, toprefix)
        		if g2 in glyphs:
	        		parser.fontfeatures.anchors[g2] = parser.fontfeatures.anchors[g]
        return []
