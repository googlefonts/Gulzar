import fontFeatures
from glyphtools import get_glyph_metrics

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

            rules.append(fontFeatures.Positioning(input_, positions))

        return rules
