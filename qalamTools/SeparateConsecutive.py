import fontFeatures

GRAMMAR = """
SeparateConsecutive_Args = glyphselector:glyphs ws integer:maxlen ws integer:distance -> (glyphs, maxlen, distance)
"""
VERBS = ["SeparateConsecutive"]


class SeparateConsecutive:
    @classmethod
    def action(self, parser, glyphs, maxlen, distance):
        glyphs = glyphs.resolve(parser.fontfeatures, parser.font)
        postcontext = [glyphs]
        rules = []

        # r = fontFeatures.Routine(flags=0x12)
        # r.markFilteringSet = parser.fontfeatures.namedClasses["nuktas"]
        for i in reversed(range(1, maxlen)):
            positions = []
            input_ = [glyphs] * i
            # Only include lo-rise medis
            for j in range(1, i + 1):
                positions.append(
                    fontFeatures.ValueRecord((i - j + 1) * distance, 0, 0, 0)
                )
            rules.append(
                fontFeatures.Positioning(input_, positions, postcontext=postcontext)
            )

        return rules
