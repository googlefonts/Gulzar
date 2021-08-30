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

min_bubble = 200

bezier_cache = {}
metrics_cache = {}
distance_cache = {}

spaceglyph = "space.urdu"

distance_cache = {}

def actually_joins(left, right):
    if left.startswith("VAO") or left.startswith("RE") or left.startswith("DAL") or "ALIF" in left:
        return False
    return True

def determine_kern(
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
        topmarks = self.parser.fontfeatures.namedClasses["all_above_marks"]
        isols_finas = isols + finas

        binned_medis = bin_glyphs_by_metric(
            self.parser.font, medis, "rise", bincount=accuracy1
        )
        binned_finas = bin_glyphs_by_metric(
            self.parser.font, finas, "rise", bincount=accuracy1
        )

        kern_at_rise = {}

        def generate_kern_table_for_rise(r, filt, name, do_space_kern=False):
            r = quantize(r, rise_quantization)
            # logger.warn("Computing table for rise %i" % r)
            # kerntable = Hashabledict({ ("ALIFf1",): {("ALIFf1",): -50 }})
            kerntable = {}
            my_isols_finas = list(filter(filt, isols_finas))
            with tqdm.tqdm(total=len(inits) * len(my_isols_finas), miniters=30) as pbar:
                for end_of_previous_word in my_isols_finas:
                    kerntable[end_of_previous_word] = {}
                    for initial in sorted(inits):
                        if initial == spaceglyph:
                            continue
                        if actually_joins(end_of_previous_word, initial) and not do_space_kern:
                            continue
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

                    # Compress right side to groups
                    kerntable[end_of_previous_word] = compress(
                        kerntable[end_of_previous_word]
                    )

            kerntable = compress(kerntable)

            kernroutine = fontFeatures.Routine(
                rules=[],
                name="kern_at_%i_%s" % (r,name),
            )
            if do_space_kern:
                kernroutine.name = kernroutine.name+"_space"
            #kernroutine.flags=0x8
            kernroutine.flags=0x10
            kernroutine.markFilteringSet=belowmarks

            for left, kerns in kerntable.items():
                for right, value in kerns.items():
                    if not do_space_kern:
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
                                [left, [spaceglyph], right],
                                [
                                    fontFeatures.ValueRecord(),
                                    fontFeatures.ValueRecord(),
                                    fontFeatures.ValueRecord(xAdvance=value),
                                ],
                            )
                        )

            kernroutine = self.parser.fontfeatures.referenceRoutine(kernroutine)
            kernroutine._table = kerntable
            return (kernroutine, kerntable)


        def generate_dispatch_table_for_rise(r):
            if r in kern_at_rise:
                return kern_at_rise[r]
            dispatch_routine = fontFeatures.Routine(
                rules=[],
                name="kern_at_%i_dispatch" % r,
            )
            dispatch_routine.flags=0x8
            # dispatch_routine.markFilteringSet=belowmarks

            sharding_table = [
                (lambda name: re.match(r"^[A-K]", name), "atok"),
                (lambda name: re.match(r"^[L-Z]", name), "ltoz"),
            ]

            for filt,name in sharding_table:

                # First, no space
                kernroutine, kerntable = generate_kern_table_for_rise(r, filt,name, do_space_kern=False)
                lefts =  list(chain(*kerntable.keys()))
                rights = []
                for kerns in kerntable.values():
                    rights.extend(kerns.keys())
                rights = list(set(chain(*rights)))
                rights = [r for r in rights if r not in isols]
                # precontext = [medis]
                precontext = []
                postcontext = [medis+finas]
                targets = [lefts, rights]
                lookups = [[kernroutine], None]

                if lefts and kernroutine.routine.rules:
                    dispatch_routine.rules.append(fontFeatures.Chaining(
                        targets,
                        precontext = precontext,
                        postcontext = postcontext,
                        lookups = lookups
                    ))

                # Next, with space
                kernroutine, kerntable = generate_kern_table_for_rise(r, filt,name, do_space_kern=True)
                lefts =  list(chain(*kerntable.keys()))
                rights = []
                for kerns in kerntable.values():
                    rights.extend(kerns.keys())
                rights = list(set(chain(*rights)))
                rights = [r for r in rights if r not in isols]
                # precontext = [medis]
                precontext = []
                postcontext = [medis+finas]

                if lefts and kernroutine.routine.rules:
                    targets = [lefts, [spaceglyph], rights]
                    lookups = [[kernroutine], None, None]
                    dispatch_routine.rules.append(fontFeatures.Chaining(
                        targets,
                        precontext = precontext,
                        postcontext = postcontext,
                        lookups = lookups
                    ))


            dispatch_routine = self.parser.fontfeatures.referenceRoutine(dispatch_routine)
            kern_at_rise[r] = dispatch_routine
            return dispatch_routine

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
        # pool = Pool()
        # pool.map(generate_kern_table_for_rise, rises)
        # for i in rises:
            # generate_dispatch_table_for_rise(i)

        routines = []
        for i in range(maximum_word_length, -1, -1):
            routine = fontFeatures.Routine(name="NastaliqKerning_"+str(i))
            routines.append(routine)
            postcontext_options = [binned_finas] + [binned_medis] * i
            all_options = product(*postcontext_options)
            for postcontext_plus_rise in all_options:
                word_tail_rise = quantize(
                    sum([x[1] for x in postcontext_plus_rise]), rise_quantization
                )
                if word_tail_rise > maximum_rise:
                    word_tail_rise = maximum_rise
                # logger.warn("Rise = %i" % word_tail_rise)
                # logger.warn("Combinations == %i" % (len(isols_finas) * len(inits)))
                # XXX Flags
                postcontext = list(reversed([x[0] for x in postcontext_plus_rise]))
                # add space kerning rule

                target = [isols_finas, inits]
                lookups = [[generate_dispatch_table_for_rise(word_tail_rise)]] + [None] * (len(target)-1)
                routine.rules.append(
                    fontFeatures.Chaining(
                        target,
                        postcontext=postcontext,
                        lookups=lookups,
                        flags=0x08,
                    )
                )
                target = [isols_finas, [spaceglyph], inits]
                lookups = [[generate_dispatch_table_for_rise(word_tail_rise)]] + [None] * (len(target)-1)
                routine.rules.append(
                    fontFeatures.Chaining(
                        target,
                        postcontext=postcontext,
                        lookups=lookups,
                        flags=0x08,
                    )
                )


        if spacekern:
            routine.name = routine.name + "_space"
        self.shelve.close()
        return routines

    def determine_kern_cached(self, font, glyph1, glyph2, targetdistance, offset1=(0, 0), offset2=(0, 0), maxtuck=0.4):
        key = "/".join([glyph1, glyph2,str(offset1[1])])
        if key in self.shelve:
            return self.shelve[key]
        result = determine_kern(font, glyph1, glyph2, targetdistance, offset1, offset2, maxtuck)
        self.shelve[key] = result
        return result
