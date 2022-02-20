import os
import csv
import fontFeatures
import warnings

from fez import FEZVerb

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: ESCAPED_STRING
"""
VERBS = ["NastaliqConnections"]


def load_rules(trypath, glyphlist, full=False):
    rules = {}
    with open(trypath) as csvfile:
        reader = csv.DictReader(csvfile)
        for line in reader:
            left_glyph = line["Left Glyph"]
            if not left_glyph in glyphlist:
                continue
            remainder = list(line.items())[1:]
            for (g, v) in remainder:
                old = g + "1"
                if old not in glyphlist:
                    continue
                if not full and (v == "1" or v == 1 or not v):
                    continue
                replacement = g + str(v)
                if not replacement in glyphlist:
                    warnings.warn(
                        f"{left_glyph}->{old} goes to {replacement} which does not exist"
                    )
                    continue
                if not old in rules:
                    rules[old] = {}
                if not replacement in rules[old]:
                    rules[old][replacement] = []
                rules[old][replacement].append(left_glyph)
                # if "KAF" in left_glyph:
                #    left_glyph2 = "G" + left_glyph[1:]
                #    rules[old][replacement].append(left_glyph2)

    if full:
        # Raised tooth manual rules
        rules["BEm1"]["BEmsd3"] = ["AINm1", "AINf1"]+ [x for x in glyphlist if "AINm" in x]
        rules["TEm1"]["TEmsd3"] = ["AINm1", "AINf1"]+ [x for x in glyphlist if "AINm" in x]
        rules["BEm1"]["BEmsd12"] = ["BEf1", "TEf1"] + [x for x in glyphlist if "BEm" in x or "TEm" in x]
        rules["TEm1"]["TEmsd12"] = ["BEf1", "TEf1"] + [x for x in glyphlist if "BEm" in x or "TEm" in x]
        rules["BEm1"]["BEmsd10"] = ["SADf1", "TOEf1"] + [x for x in glyphlist if "SADm" in x or "TOEm" in x]
        rules["TEm1"]["TEmsd10"] = ["SADf1", "TOEf1"] + [x for x in glyphlist if "SADm" in x or "TOEm" in x]
        rules["BEm1"]["BEmsd4"] = ["FEf1"] + [x for x in glyphlist if "FEm" in x]
        rules["TEm1"]["TEmsd4"] = ["FEf1"] + [x for x in glyphlist if "FEm" in x]
        rules["BEm1"]["BEmsd15"] = ["QAFf1", "VAOf1"]
        rules["TEm1"]["TEmsd15"] = ["QAFf1", "VAOf1"]

    return rules


class NastaliqConnections(FEZVerb):
    def action(self, args):
        parser = self.parser
        filename = args[0].value[1:-1]
        rules = {}
        reachable = set([])
        basedir = os.path.dirname(parser.current_file)
        trypath = os.path.join(basedir, filename)

        if not os.path.exists(trypath):
            trypath = filename
            if not os.path.exists(trypath):
                raise ValueError("Couldn't find connections file %s" % trypath)

        rules = load_rules(trypath, parser.font.exportedGlyphs())

        r = fontFeatures.Routine(name="connections", flags=0x8)
        for oldglyph in rules:
            if oldglyph not in parser.font.exportedGlyphs():
                continue
            for replacement in rules[oldglyph]:
                context = rules[oldglyph][replacement]

                reachable |= set(context)
                reachable |= set([oldglyph, replacement])
                r.addRule(
                    fontFeatures.Substitution(
                        [[oldglyph]],
                        [[replacement]],
                        postcontext=[context],
                        reverse=True,
                    )
                )
        parser.fontfeatures.namedClasses["reachable_glyphs"] = tuple(sorted(reachable))

        return [r]
