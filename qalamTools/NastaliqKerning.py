import fontFeatures
import sys
from glyphtools import bin_glyphs_by_metric, get_glyph_metrics
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

from qalamTools.determinekern import determine_kern


PARSEOPTS = dict(use_helpers=True)

GRAMMAR = ""

NastaliqKerning_GRAMMAR="""
?start: action
action: integer_container integer_container "%"
"""

AtHeight_GRAMMAR="""
?start: action
action: integer_container "-" integer_container BARENAME
"""

VERBS = ["NastaliqKerning", "AtHeight"]

logging.basicConfig(format='%(message)s')
logger = logging.getLogger("NastaliqKerning")
logger.setLevel(logging.WARN)

# This only affects the accuracy of computing the rise?
accuracy1 = 3
rise_quantization = 100
kern_quantization = 10
maximum_rise = 600
maximum_word_length = 5

spaceglyph = "space.urdu"

class Hashabledict(dict):
    def __hash__(self):
        return hash(frozenset(self))


def quantize(number, degree):
    return degree * round(number / degree)


class NastaliqKerning(FEZVerb):
    def action(self, args):
        self.distance_at_closest = args[0].resolve_as_integer()
        self.maxtuck = args[1].resolve_as_integer() / 100.0
        self.shelve = shelve.open("kerncache.db")
        from qalamTools.NastaliqConnections import load_rules
        rules = load_rules("rules.csv", self.parser.font.exportedGlyphs(), full=True)

        self.inits = self.parser.fontfeatures.namedClasses["inits"]
        medis = self.parser.fontfeatures.namedClasses["medis"]
        self.isols = [x for x in self.parser.fontfeatures.namedClasses["isols"] if "BARI_YE" not in x]
        bariye = self.parser.fontfeatures.namedClasses["bariye"]
        finas = [x for x in self.parser.fontfeatures.namedClasses["finas"] if x not in bariye]
        # self.isols_finas = ["DALf1", "REu1", "ALIFu1"]
        # self.isols = ["ALIFu1"]
        # finas = ["ALIFf1"]
        # self.inits = ["BEi3"]
        blockers = ["AINf1", "JIMf1"]
        self.isols_finas = self.isols + finas


        binned_medis = bin_glyphs_by_metric(
            self.parser.font, medis, "rise", bincount=accuracy1
        )
        binned_finas = bin_glyphs_by_metric(
            self.parser.font, finas, "rise", bincount=accuracy1
        )
        binned_isols = bin_glyphs_by_metric(
            self.parser.font, self.isols, "rise", bincount=accuracy1
        )
        self.kern_at_rise = {}

        routines = []
        routine = fontFeatures.Routine(name="NastaliqKerning")
        routine.flags = 0x04 | 0x08

        routines.append(routine)

        for i in range(maximum_word_length, -1, -1):
            postcontext_options = [binned_finas] + [binned_medis] * i
            warnings.warn("Length "+str(i))
            all_options = product(*postcontext_options)
            for postcontext_plus_rise in all_options:
                word_tail_rise = quantize(
                    sum([x[1] for x in postcontext_plus_rise]), rise_quantization
                )
                postcontext = list(reversed([x[0] for x in postcontext_plus_rise]))
                # warnings.warn("%s - %i" % (postcontext, word_tail_rise))
                if word_tail_rise >= maximum_rise:
                    word_tail_rise = maximum_rise
                    if i == maximum_word_length:
                        # Drop the fina
                        postcontext.pop()


                target = [self.isols_finas]
                if word_tail_rise >= 400 and i > 4:
                   # HACK
                   postcontext[-1] = postcontext[-1] + ["BARI_YEf1"]

                if len(postcontext) < 2:
                   # ANOTHER HACK
                   postcontext[-1] = list(set(postcontext[-1]) - set(blockers))

                lookups = [[self.generate_kern_table_for_rise(word_tail_rise)]]
                routine.rules.append(
                    fontFeatures.Chaining(
                        target,
                        postcontext=[self.inits] + postcontext,
                        lookups=lookups,
                    )
                )

        target = [self.isols_finas]
        lookups = [[self.generate_kern_table_for_rise(0)]]
        routine.rules.append(
            fontFeatures.Chaining(
                target,
                lookups=lookups,
                postcontext = [self.isols]
            )
        )
        self.shelve.close()
        return routines

    def determine_kern_cached(self, font, glyph1, glyph2, targetdistance, height, maxtuck=0.4):
        key = "/".join(str(x) for x in [glyph1, glyph2, targetdistance, height, maxtuck])
        if key in self.shelve:
            return self.shelve[key]
        result = determine_kern(font, glyph1, glyph2, targetdistance, height, maxtuck=maxtuck)
        self.shelve[key] = result
        return result


    def generate_kern_table_for_rise(self, r):
        if r in self.kern_at_rise:
            return self.kern_at_rise[r]
        r = quantize(r, rise_quantization)
        kerntable = {}
        belowmarks = self.parser.fontfeatures.namedClasses["below_dots"]
        abovemarks = self.parser.fontfeatures.namedClasses["all_above_marks"]
        print("Generating table for rise %s" %r, file=sys.stderr)
        if r > 0:
            ends = self.inits
        else:
            ends = self.inits + self.isols
        maxtuck = self.maxtuck
        with tqdm.tqdm(total=len(ends) * len(self.isols_finas), miniters=30) as pbar:
            for end_of_previous_word in self.isols_finas:
                kerntable[end_of_previous_word] = {}
                for initial in sorted(ends): # initial of "long" sequence, i.e. left glyph
                    logger.info("Left glyph: %s" % initial)
                    logger.info("Right glyph: %s" % end_of_previous_word)
                    kern = self.determine_kern_cached(
                        self.parser.font,
                        initial,
                        end_of_previous_word,
                        self.distance_at_closest,
                        height=r,
                        maxtuck=maxtuck,
                    )# - max(get_glyph_metrics(self.parser.font, initial)["rsb"],0)
                    logger.info("%s - %s @ %i : %i" % (initial, end_of_previous_word, r, kern))
                    if kern < -10:
                        kerntable[end_of_previous_word][initial] = quantize(kern, kern_quantization)
                    pbar.update(1)

        kernroutine = fontFeatures.Routine(
            rules=[],
            name="kern_at_%i" % r,
        )
        #kernroutine.flags=0x8
        kernroutine.flags=0x08 | 0x04
        kernroutine.markFilteringSet=abovemarks

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
        self.kern_at_rise[r] = kernroutine
        return kernroutine


class AtHeight(FEZVerb):
    def action(self, args):
        (height_lower, height_upper, target_routine) = args
        height_lower = height_lower.resolve_as_integer();
        height_upper = height_upper.resolve_as_integer();
        target_routine = self.parser.fontfeatures.routineNamed(target_routine)
        self.inits = self.parser.fontfeatures.namedClasses["inits"]
        medis = self.parser.fontfeatures.namedClasses["medis"]
        isols = self.parser.fontfeatures.namedClasses["isols"]
        finas = self.parser.fontfeatures.namedClasses["finas"]

        self.isols_finas = isols + finas

        binned_medis = bin_glyphs_by_metric(
            self.parser.font, medis, "rise", bincount=accuracy1
        )
        binned_finas = bin_glyphs_by_metric(
            self.parser.font, finas, "rise", bincount=accuracy1
        )

        self.kern_at_rise = {}
        seen = {}

        routine = fontFeatures.Routine(name="At_%s_%s_%s" % (height_lower, height_upper, target_routine.name))
        routine.flags = 0x04 | 0x08

        for i in range(maximum_word_length, -1, -1):
            postcontext_options = [binned_finas] + [binned_medis] * i
            all_options = product(*postcontext_options)
            for postcontext_plus_rise in all_options:
                word_tail_rise = quantize(
                    sum([x[1] for x in postcontext_plus_rise]), rise_quantization
                )
                postcontext = list(reversed([x[0] for x in postcontext_plus_rise]))
                #if word_tail_rise >= maximum_rise:
                #    word_tail_rise = maximum_rise
                #     if i == maximum_word_length:
                #         # Drop the fina
                #         postcontext.pop()
                # if str(postcontext) in seen:
                #     continue
                # seen[str(postcontext)] = True
                if not (word_tail_rise >= height_lower and word_tail_rise <= height_upper):
                    continue

                target = [self.isols_finas, self.inits]
                lookups = [[target_routine]] + [None] * (len(target)-1)
                routine.rules.append(
                    fontFeatures.Chaining(
                        target,
                        postcontext=postcontext,
                        lookups=lookups,
                    )
                )
        return [routine]
