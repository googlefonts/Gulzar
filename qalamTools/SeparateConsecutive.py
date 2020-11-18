import fontFeatures
from glyphtools import get_glyph_metrics
from copy import copy


GRAMMAR = """
SeparateConsecutive_Args = glyphselector:nuktaset ws integer:maxlen ws integer:distance ws integer:drop -> (nuktaset, maxlen, distance, drop)
"""
VERBS = ["SeparateConsecutive"]


class SeparateConsecutive:
    @classmethod
    def action(cls, parser, nuktaset, maxlen, distance, drop):
        if "behs" not in parser.fontfeatures.namedClasses:
            raise ValueError("Needs @behs class defined")
        risemax = 200
        nuktaset = nuktaset.resolve(parser.fontfeatures, parser.font)
        if ".yb" in nuktaset[0]:
            risemax = 9999
        dot_carriers = parser.fontfeatures.namedClasses["behs"]
        initial_glyphs = [g for g in dot_carriers if "i" in g]
        non_initial_glyphs = [g for g in dot_carriers if "i" not in g]

        max_dotwidth = max(
            [
                get_glyph_metrics(parser.font, g)["xMax"]
                - get_glyph_metrics(parser.font, g)["xMin"]
                for g in nuktaset
            ]
        )
        # Filter glyphs with a certain amount of rise
        dot_carriers = [
            g
            for g in dot_carriers
            if get_glyph_metrics(parser.font, g)["rise"] < risemax and
             get_glyph_metrics(parser.font, g)["width"] < max_dotwidth
        ]
        rules = []
        for i in reversed(range(2, maxlen + 1)):
            positions = [fontFeatures.ValueRecord(0, 0, 0, 0) for _ in range(i * 2)]
            input_ = [dot_carriers, nuktaset] * i
            for j in range(0, i):
                adjustment = (i - (j + 1)) * distance
                positions[j * 2 + 1].xPlacement = adjustment
                if j % 2 == 1:
                    positions[j * 2 + 1].yPlacement -= drop

            # Do this twice, for initials (which gain an advance) and noninitials
            # (which don't)
            input_[0] = non_initial_glyphs
            rules.append(fontFeatures.Positioning(input_, positions))

            input_ = copy(input_)
            positions = copy(positions)
            input_[0] = initial_glyphs
            positions[0] = fontFeatures.ValueRecord(0, 0, 0, 0)
            positions[0].xAdvance = i * distance

            rules.append(fontFeatures.Positioning(input_, positions))

        return rules
