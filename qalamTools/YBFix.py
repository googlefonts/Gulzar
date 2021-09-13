import re
import fontFeatures
import warnings
from fez import FEZVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action:
"""
VERBS = ["FixYBPositions"]


class FixYBPositions(FEZVerb):
    def action(self, args):
        glyphs = self.parser.font.glyphs.keys()
        ybs = [x for x in glyphs if ".yb" in x]
        rules = []
        for g in glyphs:
            if not re.search(r"[A-Z]+[mi]", g): continue
            if g not in self.parser.fontfeatures.anchors: continue
            if "bottom" not in self.parser.fontfeatures.anchors[g]: continue
            anchor = self.parser.fontfeatures.anchors[g]["bottom"]
            rules.append(fontFeatures.Positioning(
                [ ybs ],
                [ fontFeatures.ValueRecord(xPlacement=anchor[0]) ],
                precontext=[[g]],
                
            ))
        return rules
