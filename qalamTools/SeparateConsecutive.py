import fontFeatures
from glyphtools import get_glyph_metrics
import warnings

from fez import FEZVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: glyphselector integer_container integer_container integer_container
"""

VERBS = ["SeparateConsecutive"]


class SeparateConsecutive(FEZVerb):
    def action(self, args):
        parser = self.parser
        marks, maxlen, distance, drop = args
        if "behs" not in parser.fontfeatures.namedClasses:
            raise ValueError("Needs @behs class defined")
        risemax = 400
        marks = marks.resolve(parser.fontfeatures, parser.font)
        if ".yb" in marks[0]:
            risemax = 9999
        dot_carriers = parser.fontfeatures.namedClasses["behs"]
        initial_glyphs = [g for g in dot_carriers if "i" in g]
        non_initial_glyphs = [g for g in dot_carriers if "i" not in g]

        max_dotwidth = max(
            [
                get_glyph_metrics(parser.font, g)["xMax"]
                - get_glyph_metrics(parser.font, g)["xMin"]
                for g in marks
            ]
        )
        # Filter glyphs
        # dot_carriers = [
        #     g
        #     for g in dot_carriers
        #     if get_glyph_metrics(parser.font, g)["run"] < max_dotwidth
        # ]
        rules = []

        def make_rule(i, do_initials, marks_at):
            inputs_positions = []
            for j in range(0, i):
                adjustment = (i - (j + 1)) * distance

                inputs_positions.append((dot_carriers, fontFeatures.ValueRecord(0)))
                if j == i-1:
                    adjustment = 0
                if (i-j+1) % 2 == 1:
                    yPlacement = -int(drop)
                else:
                    yPlacement = 0
                inputs_positions.append(
                    (marks, fontFeatures.ValueRecord(adjustment, yPlacement, 0, 0))
                )

                if j in marks_at:
                    inputs_positions.append(
                        (marks, fontFeatures.ValueRecord(0, 0, 0, 0))
                    )

            if do_initials:
                inputs_positions[0] = (
                    initial_glyphs,
                    fontFeatures.ValueRecord(0, 0, (i - 1) * distance, 0),
                )
            else:
                inputs_positions[0] = (non_initial_glyphs, fontFeatures.ValueRecord(0))
            return fontFeatures.Positioning(
                [x[0] for x in inputs_positions], [x[1] for x in inputs_positions]
            )

        for i in reversed(range(2, maxlen + 1)):
            for j in range(0, 2 ** (i - 1)):
                binary = "{0:0%ib}" % (i - 1)
                marksequence = [
                    x[0]
                    for x in list(zip(range(i - 1), binary.format(j)))
                    if x[1] == "1"
                ]
                rules.append(make_rule(i, False, marksequence))
                rules.append(make_rule(i, True, marksequence))

        return rules
