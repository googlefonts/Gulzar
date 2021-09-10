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
import shelve


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

taskil_above = ["HAMZA_ABOVE", "DAMMA"]
taskil_below = ["KASRA"]

max_sequence_length = 3
max_run = 200
margin = 0


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
            if "comma" in this_anchors:
                commax, commay = this_anchors["comma"]
                this_anchors["comma.one"] = commax, commay - spacing
                this_anchors["comma.two"] = commax, commay - spacing * 2

        return []

class DetectAndSwap(FEZVerb):
    def action(self, args):
        (anchor,) = args
        self.anchor = anchor
        if anchor == "bottom":
            self.dots = ["haydb", "sdb", "sdb.one", "sdb.two", "ddb", "ddb.one", "ddb.two", "tdb", "tdb.one", "tdb.two"] + taskil_below
        else:
            self.dots = ["toeda", "sda", "sda.one", "sda.two", "dda", "dda.one", "dda.two", "tda", "tda.one", "tda.two"] + taskil_above
        self.shelve = shelve.open("collisioncache.db")
        self.c = Collidoscope("Gulzar", { "marks": True, "bases": False, "faraway": True}, ttFont=self.parser.font, scale_factor = 1.1)
        self.contexts = self.get_contexts()
        seq = self.generate_glyph_sequence(max_sequence_length)
        drop_one = fontFeatures.Routine(
            name = "cycle_dots_1_"+self.anchor,
        )
        drop_two = fontFeatures.Routine(
            name = "cycle_dots_2_"+self.anchor,
        )
        drop_three = fontFeatures.Routine(
            name = "cycle_dots_3_"+self.anchor,
        )

        for dot in self.dots:
            nextdot = self.cycle(dot)
            if nextdot in self.parser.font.glyphs:
                drop_one.rules.append(fontFeatures.Substitution(
                    [[dot]], [[nextdot]]
                ))
                nextdot = self.cycle(nextdot)
                if nextdot in self.parser.font.glyphs:
                    drop_two.rules.append(fontFeatures.Substitution(
                        [[dot]], [[nextdot]]
                    ))
                    nextdot = self.cycle(nextdot)
                    if nextdot in self.parser.font.glyphs:
                        drop_three.rules.append(fontFeatures.Substitution(
                            [[dot]], [[nextdot]]
                        ))

        count = 0
        rules = set({})
        result = []
        nc = self.parser.fontfeatures.namedClasses
        self.parser.fontfeatures.namedClasses = {}

        # import IPython;IPython.embed()

        for sequence in tqdm.tqdm(seq):
            if tuple(sequence) in rules:
                continue
            collides = self.collides(sequence)
            if collides:
                mitigated = self.try_mitigate(sequence)
                count += 1
                if mitigated:
                    last_dot, orig_dot, newdot, times = mitigated
                    goto = drop_one
                    if times == 2:
                        goto = drop_two
                    if times == 3:
                        goto = drop_three
                    rules.add(tuple(sequence))
                    result.append(fontFeatures.Chaining(
                        [[orig_dot]],
                        lookups=[[goto]],
                        precontext=[[x] for x in sequence[:last_dot]],
                        postcontext=[[x] for x in sequence[last_dot+1:]],
                    ))
                # else:
                #     warnings.warn("Nothing helped %s" % sequence)
        self.parser.fontfeatures.namedClasses = nc

        # OK, we have a set of rules, which is nice. But they're massive and
        # overflow. What we need to do is split them into a set of routines,
        # one per target

        # XXX No we don't. The problem is that if we split them into one per
        # target, the rules don't "cascade"; each target gets one pass over
        # the glyphstream in order. So a target in a later substitution won't
        # cause another substitution if that happens to be "earlier".

        # So we need a dispatch routine.

        results = { }
        for rule in result:
            target = rule.input[0][0]
            results.setdefault(target, fontFeatures.Routine(
                name="DotAvoidance_"+target,
                flags=0x10,
                markFilteringSet=self.dots
            )).rules.append(rule)


        dispatch = fontFeatures.Routine(
                name="DotAvoidance_dispatch_"+self.anchor
        )
        for k,v in results.items():
            dispatch.rules.append(fontFeatures.Chaining(
                [[k]],
                lookups=[[v]]
            ))

        return [dispatch]

    def collides(self, glyphs):
        key = "/".join(glyphs)
        if key not in self.shelve:
            pos = self.position_glyphs(glyphs)
            pos = [x for x in pos if x["category"] == "mark"]
            # if any(["toeda" in g["name"] or "HAMZA_ABOVE" in g["name"] for g in pos]):
            self.shelve[key] = self.c.has_collisions(pos)
        return self.shelve[key]

        # for ix in range(len(pos)):
        #     if pos[ix]["category"] != "mark":
        #         continue
        #     gb1 = pos[ix]["glyphbounds"]
        #     gb1.addMargin(margin)
        #     for jx in range(ix+1, len(pos)):
        #         if pos[jx]["category"] != "mark":
        #             continue
        #         gb2 = pos[jx]["glyphbounds"]
        #         gb2.addMargin(margin)
        #         if gb1.overlaps(gb2):
        #             return True
        # return False

    def try_mitigate(self, glyphs):
        newglyphs = list(glyphs)
        last_dot = len(glyphs) - 1 - ([x in self.dots for x in glyphs])[::-1].index(True)
        # last_dot = [x in self.dots for x in glyphs].index(True)
        orig_dot = glyphs[last_dot]
        for times in range(1, 4):
            newdot = self.cycle(newglyphs[last_dot])
            if newdot == orig_dot:
                return
            if not newdot or newdot not in self.parser.font.glyphs:
                return
            newglyphs[last_dot] = newdot
            # Check it again
            if not self.collides(newglyphs):
                return last_dot, orig_dot, newdot, times

    def cycle(self, dot):
        if dot.endswith(".two"):
            return dot[:-4]
        if dot.endswith(".one"):
            return dot[:-4] + ".two"
        else:
            return dot+".one"


    def draw(self, glyphs):
        positioned_glyphs = self.position_glyphs(glyphs)
        import matplotlib.pyplot as plt
        from beziers.path.geometricshapes import Rectangle
        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        for g in positioned_glyphs:
            for p_ in g["paths"]:
                p_.plot(ax, drawNodes=True,fill=True)
            for pb in g["pathbounds"]:
                rect = Rectangle(pb.width, pb.height, pb.centroid)
                rect.plot(ax, drawNodes=False,fill=False)
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
            "HAYC": ([], ["haydb"]),
            "SIN": (tda, []),
            "TE": (dda+tda, []),
            "SAD": (sda, []),
            "DAL": (sda+["toeda"], []),
            "RE": (sda + tda + ["toeda"], []),
            "AIN": (sda, []),
            "FE": (sda+dda, []),
            "QAF": (dda, []),
            "BE": (sda+dda+tda+["toeda"], sdb+ddb+tdb),
            "TOE": (sda, []),
            "JIM": (sda, sdb+tdb),
            "MIM": ([],[]),
            "KAF": ([],[]),
            "GAF": ([],[]),
        }

        def dotsfor(t):
            for k,v in dot_combinations.items():
                if k in t:
                    if self.anchor == "top":
                        return v[0] + taskil_above
                    else:
                        return v[1] + taskil_below
            if self.anchor == "top":
                return taskil_above
            else:
                return taskil_below

        stems = dot_combinations.keys()
        stem_re = r"^(" + ("|".join(stems)) + r")[mif]"
        starters = [x for x in self.parser.font.glyphs.keys() if re.match(stem_re,x)]

        sequences = []
        for left in list(set(starters) & set(self.rasm_glyphs)):
#            for mid in list(set(self.contexts.get(left,[])) & set(thin)):
#                for right in list(set(self.contexts.get(mid,[])) & set(starters)):
#                    for left_dot in dotsfor(left):
#                        for right_dot in dotsfor(right):
#                            sequences.append([left, left_dot, mid, right, right_dot ])
            for right in list(set(self.contexts.get(left,[])) & set(self.rasm_glyphs)):
                for left_dot in dotsfor(left):
                    for right_dot in dotsfor(right):
                        sequences.append([left, left_dot, right, right_dot ])
        return sequences
