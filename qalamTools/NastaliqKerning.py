import fontFeatures
from glyphtools import bin_glyphs_by_metric, get_beziers, get_glyph_metrics
from itertools import product, chain
import warnings
import math
import bidict
import tqdm
from functools import lru_cache
from fez import FEZVerb
from beziers.path import BezierPath
from beziers.point import Point
import shelve
import logging
import re


PARSEOPTS = dict(use_helpers=True)

GRAMMAR = """
?start: action
action: integer_container integer_container "%" spacekern?
spacekern: "spacekern"
"""
VERBS = ["NastaliqKerning"]

logging.basicConfig(format='%(message)s')
logger = logging.getLogger("NastaliqKerning")
# logger.setLevel(logging.WARN)

# This only affects the accuracy of computing the rise?
accuracy1 = 3
rise_quantization = 100
kern_quantization = 50
maximum_rise = 400
maximum_word_length = 4

min_bubble = 250

bezier_cache = {}
metrics_cache = {}
distance_cache = {}

spaceglyph = "space.urdu"

distance_cache = {}

def actually_joins(left, right):
    if left.startswith("VAO") or left.startswith("RE") or left.startswith("DAL") or "ALIF" in left:
        return False
    return True

def determine_kern_old(
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
    def cached_distance(p1, p2):
        if (p1, p2) not in distance_cache:
            distance_cache[(p1, p2)] = p1.distanceToPath(p2, samples=3)
        return distance_cache[(p1, p2)]

    paths1 = get_beziers(font, glyph1)
    paths2 = get_beziers(font, glyph2)
    metrics1 = get_glyph_metrics(font, glyph1)
    metrics2 = get_glyph_metrics(font, glyph2)

    offset1 = Point(*offset1)
    offset2 = Point(offset2[0] + metrics1["width"], offset2[1])
    kern = 0
    last_best = None
    
    minimum_possible = -1000
    full_width = max(metrics1["run"] - min(0, metrics1["rsb"]), min_bubble)
    logger.debug("Full width of %s is %i" % (glyph1, full_width))
    if maxtuck:
        maximum_width = full_width * maxtuck
        logger.debug("Maximum distance into %s is %i" % (glyph1, maximum_width))
        logger.debug("Left edge of %s is %i" % (glyph2, metrics2["xMin"]))
        minimum_possible = -metrics2["xMin"] - maximum_width
        logger.debug("Biggest kern is %i" % minimum_possible)

    iterations = 0
    while True:
        # Compute min distance
        min_distance = None
        for p1 in paths1:
            p1 = p1.clone().translate(offset1)
            for p2 in paths2:
                p2 = p2.clone().translate(Point(offset2.x + kern, offset2.y))
                d = p1.distanceToPath(p2, samples=3)
                #d = cached_distance(p1, p2)
#                 logger.debug("d was", d)
                #logger.debug("offset1 was %s" % offset1)
                #logger.debug("offset2 was %s" % offset2)
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
        if kern < minimum_possible:
            return minimum_possible
#     kern = kern -  metrics1["rsb"]
    if maxtuck:
        kern = max(kern, -(metrics1["xMax"] * (1+maxtuck)) + metrics1["rsb"])
    else:
        kern = max(kern, -(metrics1["xMax"]) + metrics1["rsb"])
    if metrics1["rsb"] < 0:
        kern = kern -  metrics1["rsb"]
    logger.debug("%s/%s/%i = %i" % (glyph1, glyph2, offset2.y, kern))
    return int(kern)

try:
    from kurbopy import BezPath, TranslateScale, Point, Vec2
    glyphcache = {}

    def get_beziers_new(font, glyph):
        if glyph in glyphcache:
            return glyphcache[glyph]
        glyphset = {k: font.default_master.get_glyph_layer(k) for k in font.exportedGlyphs()}
        layer = font.default_master.get_glyph_layer(glyph)
        rv = BezPath.fromDrawable(layer, glyphset)
        glyphcache[glyph] = rv
        return rv


    def determine_kern(
        font, glyph1, glyph2, targetdistance, offset1=(0, 0), offset2=(0, 0), maxtuck=0.4,
    ):
        paths1 = get_beziers_new(font, glyph1)
        paths2 = get_beziers_new(font, glyph2)
        metrics1 = get_glyph_metrics(font, glyph1)
        metrics2 = get_glyph_metrics(font, glyph2)

        offset1 = TranslateScale.translate(Vec2(*offset1))
        offset2 = Vec2(offset2[0] + metrics1["width"], offset2[1])
        kern = 0
        last_best = None

        minimum_possible = -1000
        full_width = max(metrics1["run"] - min(0, metrics1["rsb"]), min_bubble)
        logger.debug("Full width of %s is %i" % (glyph1, full_width))
        if maxtuck:
            maximum_width = full_width * maxtuck
            logger.debug("Maximum distance into %s is %i" % (glyph1, maximum_width))
            logger.debug("Left edge of %s is %i" % (glyph2, metrics2["xMin"]))
            minimum_possible = -metrics2["xMin"] - maximum_width
            logger.debug("Biggest kern is %i" % minimum_possible)

        iterations = 0
        while True:
            # Compute min distance
            min_distance = None
            for p1 in paths1:
                moved_p1 = offset1 * p1
                for p2 in paths2:
                    t2 = TranslateScale.translate(offset2 + Vec2(kern, 0))
                    moved_p2 = t2 * p2
                    d = moved_p1.min_distance(moved_p2)
                    # d = cached_distance(p1, p2)
                    #                 logger.debug("d was", d)
                    # logger.debug("offset1 was %s" % offset1)
                    # logger.debug("offset2 was %s" % offset2)
                    if not min_distance or d < min_distance:
                        min_distance = d
            if not last_best or min_distance < last_best:
                last_best = min_distance
            else:
                break  # Nothing helped
            if abs(min_distance - targetdistance) < 1 or iterations > 10:
                break
            iterations = iterations + 1
            kern = kern + (targetdistance - min_distance)
            if kern < minimum_possible:
                return minimum_possible
        #     kern = kern -  metrics1["rsb"]
        if maxtuck:
            kern = max(kern, -(metrics1["xMax"] * (1 + maxtuck)) + metrics1["rsb"])
        else:
            kern = max(kern, -(metrics1["xMax"]) + metrics1["rsb"])
        if metrics1["rsb"] < 0:
            kern = kern - metrics1["rsb"]
        # logger.debug("%s/%s/%i = %i" % (glyph1, glyph2, offset2.y, kern))
        return kern  # int(kern)
except Exception as e:
    determine_kern = determine_kern_old




class Hashabledict(dict):
    def __hash__(self):
        return hash(frozenset(self))


def quantize(number, degree):
    return degree * math.floor(number / degree)


class NastaliqKerning(FEZVerb):
    def action(self, args):
        distance_at_closest = args[0]
        maxtuck = args[1] / 100.0
        spacekern = (len(args) == 3)
        self.shelve = shelve.open("kerncache.db")
        from qalamTools.NastaliqConnections import load_rules
        rules = load_rules("rules.csv", self.parser.font.glyphs.keys(), full=True)
        reachable_glyphs = set([])

        # import IPython;IPython.embed()
        for old in rules:
            for new in rules[old]:
                for context in rules[old][new]:
                    reachable_glyphs.add(new)
                    reachable_glyphs.add(context)

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
        isols_finas = isols + finas

        binned_medis = bin_glyphs_by_metric(
            self.parser.font, medis, "rise", bincount=accuracy1
        )
        binned_finas = bin_glyphs_by_metric(
            self.parser.font, finas, "rise", bincount=accuracy1
        )

        kern_at_rise = {}

        def generate_kern_table_for_rise(r):
            if r in kern_at_rise:
                return kern_at_rise[r]
            r = quantize(r, rise_quantization)
            kerntable = {}
            with tqdm.tqdm(total=len(inits) * len(isols_finas), miniters=30) as pbar:
                for end_of_previous_word in isols_finas:
                    kerntable[end_of_previous_word] = {}
                    for initial in sorted(inits):
                        kern = self.determine_kern_cached(
                            self.parser.font,
                            initial,
                            end_of_previous_word,
                            distance_at_closest,
                            (0, r),
                            (0, 0),
                            maxtuck,
                        )
                        if kern < -10:
                            logger.debug("%s - %s @ %i : %i" % (initial, end_of_previous_word, r, kern))
                            kerntable[end_of_previous_word][initial] = quantize(kern, kern_quantization)
                        pbar.update(1)

            kernroutine = fontFeatures.Routine(
                rules=[],
                name="kern_at_%i" % r,
            )
            #kernroutine.flags=0x8
            kernroutine.flags=0x10 | 0x04
            kernroutine.markFilteringSet=belowmarks

            for left, kerns in kerntable.items():
                for right, value in kerns.items():
                    kernroutine.rules.append(
                        fontFeatures.Positioning(
                            [ [left], [right] ],
                            [
                                fontFeatures.ValueRecord(),
                                fontFeatures.ValueRecord(xAdvance=value),
                            ],
                        )
                    )
            kernroutine = self.parser.fontfeatures.referenceRoutine(kernroutine)
            kernroutine._table = kerntable
            kern_at_rise[r] = kernroutine
            return kernroutine

        routines = []
        rises = []
        for i in range(maximum_word_length):
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
        logger.warn("To do: %s" % list(sorted(rises)))

        routines = []
        routine = fontFeatures.Routine(name="NastaliqKerning")
        routines.append(routine)

        for i in range(maximum_word_length, -1, -1):
            postcontext_options = [binned_finas] + [binned_medis] * i
            all_options = product(*postcontext_options)
            for postcontext_plus_rise in all_options:
                word_tail_rise = quantize(
                    sum([x[1] for x in postcontext_plus_rise]), rise_quantization
                )
                if word_tail_rise > maximum_rise:
                    word_tail_rise = maximum_rise
                postcontext = list(reversed([x[0] for x in postcontext_plus_rise]))

                target = [isols_finas, inits]
                lookups = [[generate_kern_table_for_rise(word_tail_rise)]] + [None] * (len(target)-1)
                routine.rules.append(
                    fontFeatures.Chaining(
                        target,
                        postcontext=postcontext,
                        lookups=lookups,
                        flags=0x08 | 0x04,
                    )
                )


        self.shelve.close()
        return routines

    def determine_kern_cached(self, font, glyph1, glyph2, targetdistance, offset1=(0, 0), offset2=(0, 0), maxtuck=0.4):
        key = "/".join([glyph1, glyph2,str(offset1[1])])
        if key in self.shelve:
            return self.shelve[key]
        result = determine_kern(font, glyph1, glyph2, targetdistance, offset1, offset2, maxtuck)
        self.shelve[key] = result
        return result
