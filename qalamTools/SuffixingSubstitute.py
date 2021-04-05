import fontFeatures
import re

from fontFeatures.feeLib import FEEVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: glyphselector+ "->" BARENAME
"""

VERBS = ["SuffixingSubstitute"]

class SuffixingSubstitute(FEEVerb):
    def action(self, args):
        parser = self.parser
        inputs  = [g.resolve(parser.fontfeatures, parser.font) for g in args[:-1]]
        suffix  = args[-1]
        outputs = []
        for place in inputs:
            output = []
            for g in place:
                output.append(re.sub(r'\w\d+$', suffix, g))
            outputs.append(output)
        return [fontFeatures.Substitution(inputs, outputs)]
