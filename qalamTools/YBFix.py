import re
import fontFeatures
import warnings
from fez import FEZVerb
from beziers.point import Point
from glyphtools import bin_glyphs_by_metric, get_glyph_metrics
from collidoscope import Collidoscope
import shelve

PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action:
"""
VERBS = ["FixYBPositions", "DetectAndSwapYB"]


class FixYBPositions(FEZVerb):
    def action(self, args):
        glyphs = self.parser.font.exportedGlyphs()
        ybs = [x for x in glyphs if ".yb" in x]
        rules = []
        positions = {}
        for g in glyphs:
            if not re.search(r"[A-Z]+[mi]", g):
                continue
            if g not in self.parser.fontfeatures.anchors:
                continue
            if "bottom" not in self.parser.fontfeatures.anchors[g]:
                continue
            anchor = self.parser.fontfeatures.anchors[g]["bottom"]
            positions.setdefault(anchor[0], []).append(g)
        for placement, glyphs in positions.items():
            rules.append(
                fontFeatures.Positioning(
                    [ybs],
                    [fontFeatures.ValueRecord(xPlacement=placement)],
                    precontext=[glyphs],
                )
            )
        return rules


class DetectAndSwapYB(FEZVerb):
    def action(self, args):
        glyphs = self.parser.font.exportedGlyphs()
        self.contexts = self.get_contexts()
        self.shelve = shelve.open("ybcollisioncache.db")
        self.c = Collidoscope(
            "Gulzar",
            {"marks": True, "bases": False, "faraway": True},
            ttFont=self.parser.font,
            scale_factor=1.1,
        )
        medis_inits = [
            x for x in glyphs if re.search(r"[A-Z]+[mi].*\d", x) and x in self.contexts
        ]
        self.dot_carriers = [x for x in medis_inits if "JIM" in x or "BE" in x]
        self.haydb_carriers = [x for x in medis_inits if "HAYC" in x]
        self.kasra_carriers = [
            x for x in medis_inits if not ("JIM" in x or "BE" in x or "HAYC" in x)
        ]
        binned_glyphs = (
            bin_glyphs_by_metric(self.parser.font, self.dot_carriers, "run", 50)
            + bin_glyphs_by_metric(self.parser.font, self.haydb_carriers, "run", 15)
            + bin_glyphs_by_metric(self.parser.font, self.kasra_carriers, "run", 15)
        )
        self.ybs = [x for x in glyphs if x.endswith(".yb") or x.endswith(".yb.collides")]
        sequences = []
        for right_glyph in binned_glyphs:
            for right_dot in self.ybs_for(right_glyph):
                for left_glyph in binned_glyphs:
                    for left_dot in self.ybs_for(left_glyph):
                        sequences.append([right_glyph, right_dot, left_glyph, left_dot])
        cycle_dot = fontFeatures.Routine(
            name="cycle_YB_dot",
            rules=[
                fontFeatures.Substitution(
                    [[x for x in self.ybs if x.endswith(".yb")]], [[self.cycle(x) for x in self.ybs if x.endswith(".yb")]]
                )
            ],
        )
        result = []
        pruned = 0
        collides = 0
        failed = []
        import tqdm

        for seq in tqdm.tqdm(sequences):
            if not self.any_possible_sequence(seq):
                pruned += 1
                continue
            if not self.collides(seq):
                continue
            collides = collides + 1
            mitigated = self.try_mitigate(seq)
            if not mitigated:
                # warnings.warn(
                #     "Nothing worked for %s/%s/%s/%s"
                #     % (seq[0][0][0], seq[1], seq[2][0][0], seq[1])
                # )
                failed.append(seq)
                continue
            dot_position, orig_dot, newdot, times = mitigated
            result.append(
                fontFeatures.Chaining(
                    [[orig_dot]],
                    lookups=[[cycle_dot]],
                    precontext=[seq[0][0], [seq[1]], seq[2][0]],
                )
            )
        warnings.warn(
            "Mitigated %i / %i YB collisions (%i pruned)"
            % (len(result), collides, pruned,)
        )
        r = fontFeatures.Routine(name="DotAvoidance_YB", rules=result, flags=0x10)
        r.markFilteringSet = self.ybs
        return [r]

    def any_possible_sequence(self, seq):
        rights, rdot, lefts, ldot = seq
        for right in rights[0]:
            for left in lefts[0]:
                if self.possible_sequence(right, rdot, left, ldot):
                    return True
        return False

    def draw(self, glyphs):
        positioned_glyphs = self.position_glyphs(glyphs)
        import matplotlib.pyplot as plt
        from beziers.path.geometricshapes import Rectangle

        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        for g in positioned_glyphs:
            for p_ in g["paths"]:
                p_.plot(ax, drawNodes=True, fill=True)
            for pb in g["pathbounds"]:
                rect = Rectangle(pb.width, pb.height, pb.centroid)
                rect.plot(ax, drawNodes=False, fill=False)
        plt.show()

    def possible_sequence(self, right, rdot, left, ldot):
        if left not in self.contexts[right]:
            return False
        if "haydb" in rdot and "HAYC" not in right:
            return False
        if "haydb" in ldot and "HAYC" not in left:
            return False
        if re.search(r"^[sdt]db", rdot) and ("JIM" not in right and "BE" not in right):
            return False
        if re.search(r"^[sdt]db", ldot) and ("JIM" not in left and "BE" not in left):
            return False
        return True

    def collides(self, seq):
        key = str(seq)
        if key not in self.shelve:
            positioned = self.position_glyphs(seq)
            self.shelve[key] = bool(self.c.has_collisions(positioned))
        return self.shelve[key]

    def ybs_for(self, binned_glyph):
        representative_glyph = binned_glyph[0][0]
        if representative_glyph in self.haydb_carriers:
            return [x for x in self.ybs if "haydb" in x]
        if representative_glyph in self.dot_carriers:
            return self.ybs
        else:
            return [x for x in self.ybs if "KASRA" in x]

    def position_glyphs(self, glyphs):
        avg_distance = 0
        for r in glyphs[0][0]:
            for l in glyphs[2][0]:
                avg_distance += self.compute_distance(r, l) / (
                    len(glyphs[0][0]) * len(glyphs[2][0])
                )
        position1 = Point(avg_distance, 0)
        position2 = Point(0, 0)
        g1 = self.c.get_positioned_glyph(glyphs[1], position1)
        g2 = self.c.get_positioned_glyph(glyphs[3], position2)
        return [g1, g2]

    def compute_distance(self, r, l):
        fallback_l = [get_glyph_metrics(self.parser.font, l)["xMax"]]
        l_distance = (
            self.parser.fontfeatures.anchors[l].get("entry", fallback_l)[0]
            - self.parser.fontfeatures.anchors[l]["bottom"][0]
        )
        r_distance = (
            self.parser.fontfeatures.anchors[r]["bottom"][0]
            - self.parser.fontfeatures.anchors[r].get("exit", [0])[0]
        )
        return l_distance + r_distance

    def try_mitigate(self, glyphs):
        newglyphs = list(glyphs)
        move_position = 3
        orig_dot = glyphs[move_position]
        for times in range(1, 4):
            newdot = self.cycle(newglyphs[move_position])
            if newdot == orig_dot:
                return
            if not newdot or newdot not in self.parser.font.glyphs:
                continue
            newglyphs[move_position] = newdot
            return move_position, orig_dot, newdot, times

    def cycle(self, dot):
        if dot.endswith(".collides"):
            return
        else:
            return dot + ".collides"

    def get_contexts(self):
        from qalamTools.NastaliqConnections import load_rules

        rules = load_rules("rules.csv", self.parser.font.exportedGlyphs(), full=True)
        # possible = set([])
        self.rasm_glyphs = set([])
        possible_contexts = {}

        for old in rules:
            for new in rules[old]:
                for context in rules[old][new]:
                    # possible.add((new, context))
                    possible_contexts.setdefault(new, []).append(context)
                    self.rasm_glyphs.add(new)
                    self.rasm_glyphs.add(context)
        return possible_contexts
