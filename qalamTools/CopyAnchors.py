import fontFeatures
import warnings
from fontFeatures.feeLib import FEEVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: BARENAME BARENAME
"""
VERBS = ["CopyAnchors"]


class CopyAnchors(FEEVerb):
    def action(self, args):
        fromprefix, toprefix = args
        glyphs = self.parser.font.keys()
        for g in glyphs:
            if g not in self.parser.fontfeatures.anchors: continue
            if g.startswith(fromprefix):
                g2 = g.replace(fromprefix, toprefix)
                if g2 in glyphs:
                    self.parser.fontfeatures.anchors[g2] = self.parser.fontfeatures.anchors[g]
        return []
