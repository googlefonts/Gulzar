import fontFeatures
import re

GRAMMAR = """
SuffixingSubstitute_Args = gsws+:l ws '->' ws? <(letter|digit)+>:suffix -> (l,suffix)

gsws = glyphselector:g ws? -> g
"""

VERBS = ["SuffixingSubstitute", ""]

class SuffixingSubstitute:
    @classmethod
    def action(self, parser, l, suffix):
        inputs  = [g.resolve(parser.fontfeatures, parser.font) for g in l]
        outputs = []
        for place in inputs:
            output = []
            for g in place:
                output.append(re.sub(r'\w\d+$', suffix, g))
            outputs.append(output)
        return [fontFeatures.Substitution(inputs, outputs)]
