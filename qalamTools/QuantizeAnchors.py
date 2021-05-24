import math
from fontFeatures.feeLib import FEEVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: integer_container
"""
VERBS = ["QuantizeAnchors"]

def quantize(number, degree):
    return degree * math.floor(number / degree)


class QuantizeAnchors(FEEVerb):
    def action(self, args):
        amount = args[0]
        for anchorset in self.parser.fontfeatures.anchors.values():
            for anchorname, pos in anchorset.items():
                anchorset[anchorname] = (quantize(pos[0], amount), quantize(pos[1], amount))
        return []
