import fontFeatures
import sys
from glyphtools import bin_glyphs_by_metric
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
# logger.setLevel(logging.WARN)

# This only affects the accuracy of computing the rise?
accuracy1 = 3
rise_quantization = 100
kern_quantization = 40
maximum_rise = 400
maximum_word_length = 5

spaceglyph = "space.urdu"

class Hashabledict(dict):
    def __hash__(self):
        return hash(frozenset(self))


def quantize(number, degree):
    return degree * math.floor(number / degree)


class NastaliqKerning(FEZVerb):
    def action(self, args):
        self.distance_at_closest = args[0]
        self.maxtuck = args[1] / 100.0
        self.shelve = shelve.open("kerncache.db")
        from qalamTools.NastaliqConnections import load_rules
        rules = load_rules("rules.csv", self.parser.font.glyphs.keys(), full=True)

        self.inits = self.parser.fontfeatures.namedClasses["inits"]
        medis = self.parser.fontfeatures.namedClasses["medis"]
        isols = self.parser.fontfeatures.namedClasses["isols"]
        bariye = self.parser.fontfeatures.namedClasses["bariye"]
        finas = [x for x in self.parser.fontfeatures.namedClasses["finas"] if x not in bariye]
        
        self.isols_finas = isols + finas + bariye

        binned_medis = bin_glyphs_by_metric(
            self.parser.font, medis, "rise", bincount=accuracy1
        )
        binned_finas = bin_glyphs_by_metric(
            self.parser.font, finas, "rise", bincount=accuracy1
        )

        self.kern_at_rise = {}

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
                if word_tail_rise >= maximum_rise:
                    word_tail_rise = maximum_rise
                    if i == maximum_word_length:
                        # Drop the fina
                        postcontext.pop()

                target = [self.isols_finas, self.inits]
                lookups = [[self.generate_kern_table_for_rise(word_tail_rise)]] + [None] * (len(target)-1)
                routine.rules.append(
                    fontFeatures.Chaining(
                        target,
                        postcontext=postcontext,
                        lookups=lookups,
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


    def generate_kern_table_for_rise(self, r):
        if r in self.kern_at_rise:
            return self.kern_at_rise[r]
        r = quantize(r, rise_quantization)
        kerntable = {}
        belowmarks = self.parser.fontfeatures.namedClasses["below_dots"]
        print("Generating table for rise %s" %r, file=sys.stderr)
        with tqdm.tqdm(total=len(self.inits) * len(self.isols_finas), miniters=30) as pbar:
            for end_of_previous_word in self.isols_finas:
                kerntable[end_of_previous_word] = {}
                for initial in sorted(self.inits):
                    kern = self.determine_kern_cached(
                        self.parser.font,
                        initial,
                        end_of_previous_word,
                        self.distance_at_closest,
                        (0, r),
                        (0, 0),
                        self.maxtuck,
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
        self.kern_at_rise[r] = kernroutine
        return kernroutine


class AtHeight(FEZVerb):
    def action(self, args):
        (height_lower, height_upper, target_routine) = args
        target_routine = self.parser.fontfeatures.routineNamed(target_routine)
        self.inits = self.parser.fontfeatures.namedClasses["inits"]
        medis = self.parser.fontfeatures.namedClasses["medis"]
        isols = self.parser.fontfeatures.namedClasses["isols"]
        bariye = self.parser.fontfeatures.namedClasses["bariye"]
        finas = [x for x in self.parser.fontfeatures.namedClasses["finas"] if x not in bariye]
        
        self.isols_finas = isols + finas + bariye

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
                if word_tail_rise >= maximum_rise:
                    word_tail_rise = maximum_rise
                    if i == maximum_word_length:
                        # Drop the fina
                        postcontext.pop()
                if str(postcontext) in seen:
                    continue
                seen[str(postcontext)] = True
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
