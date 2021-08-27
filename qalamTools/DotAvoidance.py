import fontFeatures
import warnings
import re
from fez import FEZVerb
from collidoscope import Collidoscope
from beziers.point import Point
from fontFeatures.shaperLib.Shaper import Shaper
from fontFeatures.shaperLib.Buffer import Buffer
from qalamTools.NastaliqConnections import load_rules
from glyphtools import get_glyph_metrics
import tqdm
import logging

# logging.basicConfig(format='%(message)s')
# logging.getLogger("fontFeatures.shaperLib").setLevel(logging.DEBUG)


PARSEOPTS = dict(use_helpers=True)

GRAMMAR = ""

AddSpacedAnchors_GRAMMAR = """
?start: action
action: integer_container
"""

DetectAndSwap_GRAMMAR = """
?start: action
action: BARENAME
"""

VERBS = ["AddSpacedAnchors", "DetectAndSwap"]


max_sequence_length = 3
max_run = 200


class AddSpacedAnchors(FEZVerb):
    def action(self, args):
        (spacing,) = args
        anchors = self.parser.fontfeatures.anchors
        glyphs = self.parser.font.glyphs.keys()
        for g in glyphs:
            if g not in anchors: continue
            this_anchors = anchors[g]
            if "top" in this_anchors:
                topx, topy = this_anchors["top"]
                this_anchors["top.one"] = topx, topy + spacing
                this_anchors["top.two"] = topx, topy + spacing * 2
            if "bottom" in this_anchors:
                bottomx, bottomy = this_anchors["bottom"]
                this_anchors["bottom.one"] = bottomx, bottomy - spacing
                this_anchors["bottom.two"] = bottomx, bottomy - spacing * 2
        return []

class DetectAndSwap(FEZVerb):
    def action(self, args):
        (anchor,) = args
        self.anchor = anchor
        if anchor == "bottom":
            self.dots = ["haydb", "sdb", "sdb.one", "sdb.two", "ddb", "ddb.one", "ddb.two", "tdb", "tdb.one", "tdb.two"]
        else:
            self.dots = ["toeda", "sda", "sda.one", "sda.two", "dda", "dda.one", "dda.two", "tda", "tda.one", "tda.two"]

        self.c = Collidoscope("Gulzar", { "marks": True, "bases": False, "faraway": True}, ttFont=self.parser.font)
        self.contexts = self.get_contexts()
        seq = self.generate_glyph_sequence(max_sequence_length)
        count = 0
        rules = set({})
        result = []
        nc = self.parser.fontfeatures.namedClasses
        self.parser.fontfeatures.namedClasses = {}
        for sequence in tqdm.tqdm(seq):
            if tuple(sequence) in rules:
                continue
            print("# %s" % sequence)
            collides = self.collides(sequence)
            if collides:
                mitigated = self.try_mitigate(sequence)
                count += 1
                if mitigated:
                    last_dot, orig_dot, newdot = mitigated
                    rules.add(tuple(sequence))
                    result.append(fontFeatures.Substitution(
                        [[orig_dot]],
                        [[newdot]],
                        precontext=[[x] for x in sequence[:last_dot]],
                        postcontext=[[x] for x in sequence[last_dot+1:]],
                    ))
                # else:
                #     warnings.warn("Nothing helped %s" % sequence)
            # if count > 500:
                # break
        self.parser.fontfeatures.namedClasses = nc
        return result

    def collides(self, glyphs):
        pos = self.position_glyphs(glyphs)
        for ix in range(len(pos)):
            if pos[ix]["category"] != "mark":
                continue
            gb1 = pos[ix]["glyphbounds"]
            for jx in range(ix+1, len(pos)):
                if pos[jx]["category"] != "mark":
                    continue
                gb2 = pos[jx]["glyphbounds"]
                if gb1.overlaps(gb2):
                    return True
        return False

    def try_mitigate(self, glyphs):
        newglyphs = list(glyphs)
        last_dot = len(glyphs) - 1 - ([x in self.dots for x in glyphs])[::-1].index(True)
        # last_dot = [x in self.dots for x in glyphs].index(True)
        orig_dot = glyphs[last_dot]
        while True:
            newdot = self.cycle(newglyphs[last_dot])
            if not newdot or newdot not in self.parser.font.glyphs:
                return
            newglyphs[last_dot] = newdot
            # Check it again
            if not self.collides(newglyphs):
                return last_dot, orig_dot, newdot

    def cycle(self, dot):
        if dot.endswith(".two"):
            return
        if dot.endswith(".one"):
            return dot[:-4] + ".two"
        else:
            return dot+".one"


    def draw(self, glyphs):
        positioned_glyphs = self.position_glyphs(glyphs)
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        for g in positioned_glyphs:
            for p_ in g["paths"]:
                p_.plot(ax, drawNodes=True,fill=True)
        plt.show()

    def position_glyphs(self, glyphs):
        buf = Buffer(self.parser.font, glyphs=glyphs, script="Arabic",direction="RTL")
        shaper = Shaper(self.parser.fontfeatures, self.parser.font)
        shaper.execute(buf)
        cursor = 0
        glyphs = []
        for item in reversed(buf):
            position = Point(cursor + (item.position.xPlacement or 0), item.position.yPlacement or 0)
            g = self.c.get_positioned_glyph(item.glyph, position)
            glyphs.append(g)
            cursor += item.position.xAdvance
        return glyphs

    def get_contexts(self):
        rules = load_rules("rules.csv", self.parser.font.glyphs.keys(), full=True)
        # possible = set([])
        self.rasm_glyphs = set([])
        possible_contexts = {}

        for old in rules:
            for new in rules[old]:
                for context in rules[old][new]:
                    # possible.add((new, context))
                    possible_contexts.setdefault(new,[]).append(context)
                    self.rasm_glyphs.add(new)
                    self.rasm_glyphs.add(context)
        return possible_contexts

    def generate_glyph_sequence(self, n):
        thin = [x for x in self.parser.font.glyphs.keys() if get_glyph_metrics(self.parser.font,x)["run"] < max_run and re.search(r"m\d+$", x)]

        sda = ["sda", "sda.one", "sda.two"]
        dda = ["dda", "dda.one", "dda.two"]
        tda = ["tda", "tda.one", "tda.two"]
        sdb = ["sdb", "sdb.one", "sdb.two"]
        ddb = ["ddb", "ddb.one", "ddb.two"]
        tdb = ["tdb", "tdb.one", "tdb.two"]

        dot_combinations = {
            "HAYC": (tda, ["haydb"]),
            "TE": (dda+tda, []),
            "SAD": (sda, []),
            "DAL": (sda+["toeda"], []),
            "RE": (sda + tda + ["toeda"], []),
            "AIN": (sda, []),
            "FE": (sda+dda, []),
            "QAF": (dda, []),
            "BE": (sda+dda+tda+["toeda"], sdb+ddb+tdb),
            "TOE": (sda, []),
            "JIM": (sda, sdb+tdb)
        }

        def dotsfor(t):
            for k,v in dot_combinations.items():
                if k in t:
                    if self.anchor == "top":
                        return v[0]
                    else:
                        return v[1]
            return []

        above_stems = [k for k,v in dot_combinations.items() if v[0]]
        above_re = r"^(" + ("|".join(above_stems)) + r")[mi]"
        below_stems = [k for k,v in dot_combinations.items() if v[1]]
        below_re = r"^(" + ("|".join(below_stems)) + r")[mi]"
        below_dots = [x for x in self.parser.font.glyphs.keys() if re.match(below_re,x)]
        above_dots = [x for x in self.parser.font.glyphs.keys() if re.match(above_re,x)]

        # Do it by hand, it's easier to think about
        if self.anchor == "bottom":
            starters = below_dots
        else:
            starters = above_dots
        sequences = []
        for left in list(set(starters) & set(self.rasm_glyphs)):
            for mid in list(set(self.contexts.get(left,[])) & set(thin)):
                for right in list(set(self.contexts.get(mid,[])) & set(starters)):
                    for left_dot in dotsfor(left):
                        for right_dot in dotsfor(right):
                            sequences.append([left, left_dot, mid, right, right_dot ])
            for right in list(set(self.contexts.get(left,[])) & set(starters)):
                for left_dot in dotsfor(left):
                    for right_dot in dotsfor(right):
                        sequences.append([left, left_dot, right, right_dot ])
        return sequences
        # def seq(n, rightmost):
        #     if n == 1:
        #         for t in rightmost:
        #             if t in below_dots:
        #                 for dot in dotsfor(t):
        #                     yield [t] + [dot]
        #     else:
        #         for t in rightmost:
        #             if t in self.contexts and t in usable:
        # #                 print("Generating a subsequence for "+t,self.contexts[t])
        #                 subseq = seq(n-1, self.contexts[t])
        #                 for post in subseq:
        #                     yield [t] + post
        #                     if t in below_dots or t in hayc:
        #                         for dot in dotsfor(t):
        #                             yield [t] + [dot] + post

        # def has_two_dots(glyph_string):
        #     return len([g for g in glyph_string if g in self.dots ]) >1

        # if self.anchor == "bottom":
        #     return list(filter(has_two_dots,seq(n, hayc + dot_carriers)))
        # return list(filter(has_two_dots,seq(n, dot_carriers)))
