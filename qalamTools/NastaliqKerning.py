import fontFeatures
from glyphtools import bin_glyphs_by_metric, get_beziers, get_glyph_metrics
from itertools import product, chain
import warnings
import math
import bidict
import tqdm
from functools import lru_cache
from fontFeatures.feeLib import FEEVerb
from beziers.path import BezierPath
from beziers.point import Point
import shelve


PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: integer_container integer_container "%" spacekern?
spacekern: "spacekern"
"""
VERBS = ["NastaliqKerning"]

accuracy1 = 4
rise_quantization = 150
kern_quantization = 20
maximum_rise = 450

bezier_cache = {}
metrics_cache = {}
distance_cache = {}

reachable_glyphs = [
    "AINf1",
    "AINi1",
    "AINi10",
    "AINi11",
    "AINi12",
    "AINi13",
    "AINi14",
    "AINi2",
    "AINi20",
    "AINi21",
    "AINi3",
    "AINi4",
    "AINm1",
    "AINm12",
    "AINm13",
    "AINm14",
    "AINm18",
    "AINm19",
    "AINm2",
    "AINm20",
    "AINm21",
    "AINm3",
    "AINm4",
    "AINm5",
    "AINm6",
    "ALIFf1",
    "ALIFf2",
    "BARI_YEf1",
    "BARI_YEf2",
    "BARI_YEf3",
    "BEf1",
    "BEf2",
    "BEi1",
    "BEi12",
    "BEi13",
    "BEi14",
    "BEi2",
    "BEi20",
    "BEi21",
    "BEi22",
    "BEi3",
    "BEi4",
    "BEi5",
    "BEi8",
    "BEi9",
    "BEm1",
    "BEm12",
    "BEm13",
    "BEm14",
    "BEm15",
    "BEm18",
    "BEm2",
    "BEm20",
    "BEm21",
    "BEm3",
    "BEm4",
    "BEm5",
    "BEm6",
    "BEm7",
    "BEm8",
    "CH_YEf1",
    "CH_YEf2",
    "DALf1",
    "FEf1",
    "FEi1",
    "FEi12",
    "FEi13",
    "FEi14",
    "FEi15",
    "FEi2",
    "FEi20",
    "FEi21",
    "FEi3",
    "FEi4",
    "FEi7",
    "FEm1",
    "FEm10",
    "FEm11",
    "FEm12",
    "FEm14",
    "FEm15",
    "FEm18",
    "FEm19",
    "FEm2",
    "FEm20",
    "FEm21",
    "FEm3",
    "FEm4",
    "FEm5",
    "FEm6",
    "FEm7",
    "FEm8",
    "FEm9",
    "GAFf1",
    "GAFi1",
    "GAFi10",
    "GAFi13",
    "GAFi14",
    "GAFi15",
    "GAFi16",
    "GAFi17",
    "GAFi2",
    "GAFi20",
    "GAFi21",
    "GAFi6",
    "GAFi8",
    "GAFm1",
    "GAFm10",
    "GAFm11",
    "GAFm12",
    "GAFm13",
    "GAFm14",
    "GAFm15",
    "GAFm16",
    "GAFm17",
    "GAFm19",
    "GAFm2",
    "GAFm20",
    "GAFm21",
    "GAFm3",
    "GAFm4",
    "GAFm5",
    "GAFm6",
    "GAFm7",
    "GAFm8",
    "GAFm9",
    "HAYAf1",
    "HAYAi1",
    "HAYAi11",
    "HAYAi12",
    "HAYAi13",
    "HAYAi14",
    "HAYAi15",
    "HAYAi20",
    "HAYAi21",
    "HAYAi3",
    "HAYAi4",
    "HAYAi5",
    "HAYAm1",
    "HAYAm10",
    "HAYAm11",
    "HAYAm12",
    "HAYAm13",
    "HAYAm14",
    "HAYAm15",
    "HAYAm19",
    "HAYAm2",
    "HAYAm20",
    "HAYAm21",
    "HAYAm3",
    "HAYAm4",
    "HAYAm5",
    "HAYAm6",
    "HAYAm7",
    "HAYAm8",
    "HAYAm9",
    "HAYCf1",
    "HAYCf2",
    "HAYCf3",
    "HAYCi1",
    "HAYCi10",
    "HAYCi12",
    "HAYCi13",
    "HAYCi14",
    "HAYCi2",
    "HAYCi20",
    "HAYCi21",
    "HAYCi3",
    "HAYCi4",
    "HAYCi6",
    "HAYCm1",
    "HAYCm10",
    "HAYCm12",
    "HAYCm19",
    "HAYCm2",
    "HAYCm20",
    "HAYCm21",
    "HAYCm3",
    "HAYCm4",
    "HAYCm5",
    "HAYCm6",
    "HAYCm7",
    "HAYCm8",
    "HAYCm9",
    "Hei1",
    "Hei12",
    "Hei13",
    "Hei14",
    "Hei15",
    "Hei2",
    "Hei20",
    "Hei21",
    "Hei3",
    "Hei4",
    "JIMf1",
    "JIMi1",
    "JIMi10",
    "JIMi12",
    "JIMi14",
    "JIMi17",
    "JIMi18",
    "JIMi19",
    "JIMi2",
    "JIMi20",
    "JIMi21",
    "JIMi3",
    "JIMi4",
    "JIMi5",
    "JIMi7",
    "JIMm1",
    "JIMm10",
    "JIMm11",
    "JIMm12",
    "JIMm13",
    "JIMm14",
    "JIMm15",
    "JIMm16",
    "JIMm17",
    "JIMm2",
    "JIMm20",
    "JIMm21",
    "JIMm3",
    "JIMm4",
    "JIMm5",
    "JIMm6",
    "JIMm7",
    "JIMm8",
    "KAFf1",
    "KAFi1",
    "KAFi10",
    "KAFi12",
    "KAFi13",
    "KAFi14",
    "KAFi15",
    "KAFi16",
    "KAFi17",
    "KAFi2",
    "KAFi20",
    "KAFi21",
    "KAFi3",
    "KAFi6",
    "KAFi8",
    "KAFm1",
    "KAFm10",
    "KAFm11",
    "KAFm12",
    "KAFm13",
    "KAFm14",
    "KAFm15",
    "KAFm17",
    "KAFm18",
    "KAFm19",
    "KAFm2",
    "KAFm20",
    "KAFm21",
    "KAFm3",
    "KAFm4",
    "KAFm5",
    "KAFm6",
    "KAFm7",
    "KAFm8",
    "KAFm9",
    "LAM_ALIFf1",
    "LAMf1",
    "LAMi1",
    "LAMi10",
    "LAMi11",
    "LAMi12",
    "LAMi13",
    "LAMi14",
    "LAMi15",
    "LAMi16",
    "LAMi17",
    "LAMi2",
    "LAMi20",
    "LAMi21",
    "LAMi4",
    "LAMm1",
    "LAMm10",
    "LAMm11",
    "LAMm12",
    "LAMm13",
    "LAMm14",
    "LAMm16",
    "LAMm17",
    "LAMm2",
    "LAMm20",
    "LAMm21",
    "LAMm3",
    "LAMm4",
    "LAMm5",
    "LAMm7",
    "LAMm8",
    "LAMm9",
    "MIMf1",
    "MIMi1",
    "MIMi12",
    "MIMi13",
    "MIMi16",
    "MIMi17",
    "MIMi2",
    "MIMi20",
    "MIMi21",
    "MIMi3",
    "MIMi4",
    "MIMi7",
    "MIMi8",
    "MIMm1",
    "MIMm10",
    "MIMm11",
    "MIMm12",
    "MIMm13",
    "MIMm14",
    "MIMm15",
    "MIMm16",
    "MIMm2",
    "MIMm20",
    "MIMm21",
    "MIMm3",
    "MIMm4",
    "MIMm5",
    "MIMm6",
    "MIMm7",
    "MIMm8",
    "MIMm9",
    "NUNf1",
    "REf1",
    "REf2",
    "REf3",
    "REf4",
    "SADf1",
    "SADi1",
    "SADi14",
    "SADi15",
    "SADi16",
    "SADi17",
    "SADi2",
    "SADi20",
    "SADi21",
    "SADi3",
    "SADi4",
    "SADi5",
    "SADm1",
    "SADm10",
    "SADm11",
    "SADm12",
    "SADm13",
    "SADm14",
    "SADm15",
    "SADm16",
    "SADm17",
    "SADm2",
    "SADm20",
    "SADm21",
    "SADm3",
    "SADm4",
    "SADm5",
    "SADm6",
    "SADm7",
    "SADm8",
    "SADm9",
    "SINf1",
    "SINi1",
    "SINi12",
    "SINi13",
    "SINi14",
    "SINi15",
    "SINi2",
    "SINi20",
    "SINi21",
    "SINi3",
    "SINi4",
    "SINi5",
    "SINm1",
    "SINm12",
    "SINm13",
    "SINm14",
    "SINm15",
    "SINm2",
    "SINm20",
    "SINm21",
    "SINm3",
    "SINm4",
    "SINm5",
    "SINm6",
    "SINm7",
    "SINm8",
    "TEf1",
    "TEf2",
    "TEi1",
    "TEi12",
    "TEi13",
    "TEi14",
    "TEi2",
    "TEi20",
    "TEi21",
    "TEi22",
    "TEi3",
    "TEi4",
    "TEi5",
    "TEi8",
    "TEi9",
    "TEm1",
    "TEm12",
    "TEm13",
    "TEm14",
    "TEm15",
    "TEm2",
    "TEm20",
    "TEm21",
    "TEm3",
    "TEm4",
    "TEm5",
    "TEm6",
    "TEm7",
    "TEm8",
    "TOEf1",
    "TOEi1",
    "TOEi11",
    "TOEi13",
    "TOEi17",
    "TOEi20",
    "TOEi21",
    "TOEi3",
    "TOEi4",
    "TOEi5",
    "TOEi6",
    "TOEi9",
    "TOEm1",
    "TOEm10",
    "TOEm11",
    "TOEm12",
    "TOEm13",
    "TOEm14",
    "TOEm15",
    "TOEm16",
    "TOEm17",
    "TOEm2",
    "TOEm20",
    "TOEm21",
    "TOEm3",
    "TOEm4",
    "TOEm5",
    "TOEm6",
    "TOEm7",
    "TOEm8",
    "TOEm9",
]


class Hashabledict(dict):
    def __hash__(self):
        return hash(frozenset(self))


def quantize(number, degree):
    return degree * math.floor(number / degree)


def compress(d):
    newkerns = bidict.bidict({})
    for right, value in d.items():
        if value in newkerns.inverse:
            cur_tuple = newkerns.inverse[value]
            new_tuple = cur_tuple + tuple([right])
            del newkerns[cur_tuple]
            newkerns[new_tuple] = value
        else:
            newkerns[tuple([right])] = value
    return Hashabledict(newkerns)


def right_joining(x):
    for k in ["DAL", "RE", "VAO"]:
        if k in x:
            return True
    return False


class NastaliqKerning(FEEVerb):
    def action(self, args):
        distance_at_closest = args[0]
        maxtuck = args[0] / 100.0
        spacekern = (len(args) == 3)
        self.shelve = shelve.open("kerncache.db")

        inits = [
            x
            for x in self.parser.fontfeatures.namedClasses["inits"]
            if x in reachable_glyphs
        ]
        medis = [
            x
            for x in self.parser.fontfeatures.namedClasses["medis"]
            if x in reachable_glyphs
        ]
        isols = self.parser.fontfeatures.namedClasses["isols"]
        bariye = self.parser.fontfeatures.namedClasses["bariye"]
        finas = [x for x in self.parser.fontfeatures.namedClasses["finas"] if x not in bariye]
        belowmarks = self.parser.fontfeatures.namedClasses["below_dots"]
        topmarks = self.parser.fontfeatures.namedClasses["all_above_marks"]
        isols_finas = isols + finas

        binned_medis = bin_glyphs_by_metric(
            self.parser.font, medis, "rise", bincount=accuracy1
        )
        binned_finas = bin_glyphs_by_metric(
            self.parser.font, finas, "rise", bincount=accuracy1
        )

        kern_at_rise = {}

        def generate_kern_table_for_rise(r):
            r = quantize(r, rise_quantization)
            if r in kern_at_rise:
                return kern_at_rise[r]
            # warnings.warn("Computing table for rise %i" % r)
            # kerntable = Hashabledict({ ("ALIFf1",): {("ALIFf1",): -50 }})
            kerntable = {}
            with tqdm.tqdm(total=len(inits) * len(isols_finas), miniters=30) as pbar:
                for end_of_previous_word in isols_finas:
                    kerntable[end_of_previous_word] = {}
                    for initial in sorted(inits):
                        if initial == "space":
                            continue
                        kern = self.determine_kern(
                            self.parser.font,
                            initial,
                            end_of_previous_word,
                            distance_at_closest,
                            (0, r),
                            (0, 0),
                            maxtuck,
                        )
                        if kern < -10:
                            # warnings.warn("%s - %s @ %i : %i" % (initial, end_of_previous_word, r, kern))
                            kerntable[end_of_previous_word][initial] = quantize(kern, kern_quantization)
                        pbar.update(1)

                    # Compress right side to groups
                    kerntable[end_of_previous_word] = compress(
                        kerntable[end_of_previous_word]
                    )

            kerntable = compress(kerntable)

            kernroutine = fontFeatures.Routine(
                rules=[],
                name="kern_at_%i" % r,
            )
            if spacekern:
                kernroutine.name = kernroutine.name+"_space"
            kernroutine.flags=0x10
            kernroutine.markFilteringSet=belowmarks

            for left, kerns in kerntable.items():
                for right, value in kerns.items():
                    precontext = []
                    if right in inits:
                        precontext = [medis]
                    else:
                        precontext = [ isols_finas+["space"] ]
                    postcontext = [medis+finas]
                    if not spacekern:
                        kernroutine.rules.append(
                            fontFeatures.Positioning(
                                [left, right],
                                [
                                    fontFeatures.ValueRecord(),
                                    fontFeatures.ValueRecord(xAdvance=value),
                                ],
                            )
                        )
                    else: 
                        # Also add space kerning rule
                        kernroutine.rules.append(
                            fontFeatures.Positioning(
                                [left, ["space"], right],
                                [
                                    fontFeatures.ValueRecord(),
                                    fontFeatures.ValueRecord(),
                                    fontFeatures.ValueRecord(xAdvance=value),
                                ],
                            )
                        )

            kernroutine = self.parser.fontfeatures.referenceRoutine(kernroutine)
            kernroutine._table = kerntable


            dispatch_routine = fontFeatures.Routine(
                rules=[],
                name="kern_at_%i_dispatch" % r,
            )
            if spacekern:
                dispatch_routine.name = dispatch_routine.name+"_space"
            dispatch_routine.flags=0x10
            dispatch_routine.markFilteringSet=belowmarks

            # Dispatch rule 1
            lefts =  list(chain(*kerntable.keys()))
            rights = list(set(chain(*[r for r in kerns.keys() for kerns in kerntable.values()])))
            rights = [r for r in rights if r not in isols]
            # precontext = [medis]
            precontext = []
            postcontext = [medis+finas]
            if spacekern:
                targets = [lefts, ["space"], rights]
                lookups = [[kernroutine], None, None]
            else:
                targets = [lefts, rights]
                lookups = [[kernroutine], None]

            if lefts:
                dispatch_routine.rules.append(fontFeatures.Chaining(
                    targets,
                    precontext = precontext,
                    postcontext = postcontext,
                    lookups = lookups
                ))

            # Dispatch rule 2
            rights = list(set(chain(*[r for r in kerns.keys() for kerns in kerntable.values()])))
            lefts =  list(chain(*kerntable.keys()))
            rights = [r for r in rights if r not in isols]
            # precontext = [ isols_finas+["space"] ]
            precontext = []
            postcontext = [medis+finas]
            if spacekern:
                targets = [lefts, ["space"], rights]
                lookups = [[kernroutine], None, None]
            else:
                targets = [lefts, rights]
                lookups = [[kernroutine], None]

            if lefts:
                dispatch_routine.rules.append(fontFeatures.Chaining(
                    targets,
                    precontext = precontext,
                    postcontext = postcontext,
                    lookups = lookups
                ))
            kern_at_rise[r] = dispatch_routine
            dispatch_routine = self.parser.fontfeatures.referenceRoutine(dispatch_routine)
            return dispatch_routine

        routines = []
        rises = []
        if spacekern:
            target = [isols_finas, ["space"], inits]
        else:
            target = [isols_finas, inits]
        for i in range(5):
            postcontext_options = [binned_finas] + [binned_medis] * i
            all_options = product(*postcontext_options)
            for postcontext_plus_rise in all_options:
                word_tail_rise = quantize(
                    sum([x[1] for x in postcontext_plus_rise]), rise_quantization
                )
                if word_tail_rise > maximum_rise:
                    word_tail_rise = maximum_rise
                if not word_tail_rise in rises:
                    rises.append(word_tail_rise)
        warnings.warn("To do: %s" % list(sorted(rises)))
        # pool = Pool()
        # pool.map(generate_kern_table_for_rise, rises)
        for i in rises:
            generate_kern_table_for_rise(i)

        for i in range(5):
            postcontext_options = [binned_finas] + [binned_medis] * i
            all_options = product(*postcontext_options)
            for postcontext_plus_rise in all_options:
                word_tail_rise = quantize(
                    sum([x[1] for x in postcontext_plus_rise]), rise_quantization
                )
                if word_tail_rise > maximum_rise:
                    word_tail_rise = maximum_rise
                # warnings.warn("Rise = %i" % word_tail_rise)
                # warnings.warn("Combinations == %i" % (len(isols_finas) * len(inits)))
                # XXX Flags
                postcontext = list(reversed([x[0] for x in postcontext_plus_rise]))
                # add space kerning rule
                lookups = [[generate_kern_table_for_rise(word_tail_rise)]] + [None] * (len(target)-1)
                routines.append(
                    fontFeatures.Chaining(
                        target,
                        postcontext=postcontext,
                        lookups=lookups,
                        flags=0x08,
                    )
                )
        # also kern isols to isols
        routine = fontFeatures.Routine(rules=routines, name="NastaliqKerning")
        if spacekern:
            routine.name = routine.name + "_space"
        self.shelve.close()
        return [routine]

    def determine_kern(
        self,
        font,
        glyph1,
        glyph2,
        targetdistance,
        offset1=(0, 0),
        offset2=(0, 0),
        maxtuck=0.4,
    ):
        """Determine a kerning value required to set two glyphs at given ink-to-ink distance.

        The value is bounded by the ``maxtuck`` parameter. For example, if
        ``maxtuck`` is 0.20, the right glyph will not be placed any further
        left than 80% of the width of left glyph, even if this places the
        ink further than ``targetdistance`` units away.

        Args:
            font: a ``fontTools`` TTFont object or a ``glyphsLib`` GSFontMaster
                  object OR a ``babelfont`` Font object.
            glyph1: name of the left glyph.
            glyph2: name of the right glyph.
            targetdistance: distance to set the glyphs apart.
            offset1: offset (X-coordinate, Y-coordinate) to place left glyph.
            offset2: offset (X-coordinate, Y-coordinate) to place right glyph.
            maxtuck: maximum proportion of the left glyph's width to kern.

        Returns: A kerning value, in units.
        """
        key = "/".join([glyph1, glyph2,str(offset1[1])])
        if key in self.shelve:
            return self.shelve[key]
        def cached_distance(p1, p2):
            if (p1, p2) not in distance_cache:
                distance_cache[(p1, p2)] = p1.distanceToPath(p2, samples=3)
            return distance_cache[(p1, p2)]

        paths1 = get_beziers(font, glyph1)
        paths2 = get_beziers(font, glyph2)
        metrics1 = get_glyph_metrics(font, glyph1)
        offset1 = Point(*offset1)
        offset2 = Point(offset2[0] + metrics1["width"], offset2[1])
        kern = 0
        last_best = None

        iterations = 0
        while True:
            # Compute min distance
            min_distance = None
            for p1 in paths1:
                p1 = p1.clone().translate(offset1)
                for p2 in paths2:
                    p2 = p2.clone().translate(Point(offset2.x + kern, offset2.y))
                    # d = p1.distanceToPath(p2, samples=3)
                    d = cached_distance(p1, p2)
                    if not min_distance or d[0] < min_distance:
                        min_distance = d[0]
            if not last_best or min_distance < last_best:
                last_best = min_distance
            else:
                break  # Nothing helped
            if abs(min_distance - targetdistance) < 1 or iterations > 10:
                break
            iterations = iterations + 1
            kern = kern + (targetdistance - min_distance)
        kern = kern -  metrics1["rsb"]
        if maxtuck:
            kern = max(kern, -(metrics1["xMax"] * (1+maxtuck)) + metrics1["rsb"])
        else:
            kern = max(kern, -(metrics1["xMax"]) + metrics1["rsb"])
        kern = max(kern, -metrics1["width"])
        self.shelve[key]=int(kern)
        return int(kern)
