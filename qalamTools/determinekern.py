from glyphtools import get_beziers, get_glyph_metrics
from beziers.point import Point
from beziers.line import Line
from itertools import product
import logging

logger = logging.getLogger("NastaliqKerning")

bezier_cache = {}
metrics_cache = {}
min_bubble = 0

from kurbopy import BezPath, TranslateScale, Point, Vec2, Line
from itertools import product
glyphcache = {}

def get_beziers_new(font, glyph):
    if glyph in glyphcache:
        return glyphcache[glyph]
    glyphset = {k: font.default_master.get_glyph_layer(k) for k in font.glyphs.keys()}
    layer = font.default_master.get_glyph_layer(glyph)
    rv = BezPath.fromDrawable(layer, glyphset)
    glyphcache[glyph] = rv
    return rv


def horizontal_distance(p1, p2):
    min_dist = None
    lowest = None

    miny = int(max(p1.bounding_box().min_y(), p2.bounding_box().min_y()))
    logger.debug("P1 bounding box: %i,%i -- %i,%i" % (p1.bounding_box().min_x(),p1.bounding_box().min_y(),p1.bounding_box().max_x(),p1.bounding_box().max_y()))
    logger.debug("P2 bounding box: %i,%i -- %i,%i" % (p2.bounding_box().min_x(),p2.bounding_box().min_y(),p2.bounding_box().max_x(),p2.bounding_box().max_y()))
    maxy = int(min(p1.bounding_box().max_y(), p2.bounding_box().max_y()))
    for y in range(miny, maxy, 50):
        line = Line(Point(-2000, y), Point(2000,y))
        i1 = p1.intersections(line)
        i2 = p2.intersections(line)
        logger.debug("I1 intersections at %i: %s" % (y, i1))
        logger.debug("I2 intersections at %i: %s" % (y, i2))
        if i1 and i2:
            local_min = min(a.distance(b) for a,b in product(i1, i2))
            if local_min is not None and (min_dist is None or local_min < min_dist):
                min_dist = local_min
                lowest = (y,[l.x for l in i1],[l.x for l in i2])
    return min_dist, lowest


def circular_distance(p1, p2):
    return p1.min_distance(p2), None


def path_distance(font, left_glyph, right_glyph, x_offset, y_offset, algorithm="circular"):
    # Compute min distance
    # Note that this is *not* in logical order
    left_paths = get_beziers_new(font, left_glyph)
    right_paths = get_beziers_new(font, right_glyph)
    metrics1 = get_glyph_metrics(font, left_glyph)
    metrics2 = get_glyph_metrics(font, right_glyph)

    offset1 = TranslateScale.translate(Vec2(0, y_offset))
    offset2 = TranslateScale.translate(Vec2(metrics1["width"] + x_offset, 0))
    min_distance = None
    outdebuginfo = None
    for p1 in left_paths:
        moved_p1 = offset1 * p1
        logger.debug("Unmoved P1 bounding box: %i,%i -- %i,%i" % (p1.bounding_box().min_x(),p1.bounding_box().min_y(),p1.bounding_box().max_x(),p1.bounding_box().max_y()))
        for p2 in right_paths:
            logger.debug("Unmoved P2 bounding box: %i,%i -- %i,%i" % (p2.bounding_box().min_x(),p2.bounding_box().min_y(),p2.bounding_box().max_x(),p2.bounding_box().max_y()))
            moved_p2 = offset2 * p2
            if algorithm == "hybrid":
                d,debuginfo = horizontal_distance(moved_p1, moved_p2)
                if d is None:
                    d,debuginfo = circular_distance(moved_p1, moved_p2)
            elif algorithm == "horizontal":
                d,debuginfo = horizontal_distance(moved_p1, moved_p2)
            else:
                d,debuginfo = circular_distance(moved_p1, moved_p2)
            # d = cached_distance(p1, p2)
            if d is None:
                logger.debug("d was None")
            elif debuginfo is not None:
                logger.debug("d was %i at %i (%s, %s)" % (d, *debuginfo))
            else:
                logger.debug("d was %i" % d)
            # logger.debug("offset1 was %s" % offset1)
            # logger.debug("offset2 was %s" % offset2)
            if d is not None and (min_distance is None or d < min_distance):
                min_distance = d
                outdebuginfo = debuginfo
    return min_distance, outdebuginfo

def determine_kern(
    font, left_glyph, right_glyph, targetdistance, height=0, maxtuck=0.4,
):
    # Note that this is *not* in logical order
    metrics1 = get_glyph_metrics(font, left_glyph)
    metrics2 = get_glyph_metrics(font, right_glyph)

    kern = 0
    last_best = None
    minimum_possible = -1000
    full_width = max(metrics1["run"] - min(0, metrics1["rsb"]), min_bubble)
    logger.debug("Full width of %s is %i" % (left_glyph, full_width))
    if maxtuck:
        maximum_width = full_width * maxtuck + metrics1["rsb"]
        left_edge = min(-metrics2["lsb"], 0)
        logger.debug("Maximum distance into %s is %i" % (left_glyph, maximum_width))
        logger.debug("Left edge of %s is %i" % (right_glyph, left_edge))
        minimum_possible = left_edge - maximum_width
        logger.debug("Biggest kern is %i" % minimum_possible)

    iterations = 0
    min_distance = -9999
    while iterations < 10 and abs(kern - targetdistance) > 5:
        min_distance, debuginfo = path_distance(font, left_glyph, right_glyph, kern, height)
        if min_distance is None:
            return minimum_possible
        kern = kern + (targetdistance - min_distance)
        if kern < minimum_possible:
            return minimum_possible
        iterations = iterations + 1
    #     kern = kern -  metrics1["rsb"]
    # if maxtuck:
    #     kern = max(kern, -(metrics1["xMax"] * (1 + maxtuck)) + metrics1["rsb"])
    # else:
    #     kern = max(kern, -(metrics1["xMax"]) + metrics1["rsb"])
    # if metrics1["rsb"] < 0:
    #     kern = kern - metrics1["rsb"]
    logger.debug("%s/%s/%i = %i" % (left_glyph, right_glyph, height, kern))
    if kern > 0:
        return 0
    return kern  # int(kern)


def height_of_init(font, sequence):
    # Sequence should be in input order, and begin with init (which is
    # ignored, because we're finding the height of the init)
    metrics = { g: get_glyph_metrics(font, g) for g in sequence }
    word_tail = sequence[1:]
    word_tail_rise = sum(metrics[g]["rise"] for g in word_tail)
    return word_tail_rise

class TestSelf:
    from babelfont import load
    font = load("sources/Gulzar.glyphs")

    def assert_height(self, sequence, lo, hi):
       height = height_of_init(self.font, sequence[1:])
       assert height >= lo
       assert height <= hi

    def assert_kern_within(self, sequence, targetdistance, lo, hi, height=None, maxtuck=0.7):
       if height is None:
          height = height_of_init(self.font, sequence[1:])
       kern = determine_kern(self.font, sequence[1], sequence[0], targetdistance, height, maxtuck=maxtuck)
       assert kern >= lo
       assert kern <= hi

    def test_isols(self):
        import pytest
        sequence = ["VAOu1", "VAOu1"]
        self.assert_height(sequence, 0, 0)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 0, 0)
        assert distance == pytest.approx(195, 1)
        self.assert_kern_within(sequence, 200, -10, 10)

    def test_completely_underneath(self):
        import pytest
        sequence = ["VAOu1", "JIMi7", "JIMm1", "SINm3", "LAMf1"]
        self.assert_height(sequence, 500, 800)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 0, 600)
        self.assert_kern_within(sequence, 100, -500, -400)

    def test_completely_underneath_long(self):
        import pytest
        sequence = ["TOEf1", "BEi1", "SINm1", "SINm1", "SINm3", "LAMf1"]
        self.assert_height(sequence, 700, 900)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 0, 800)
        self.assert_kern_within(sequence, 150, -350, -300, maxtuck=1.0)


    def test_alif_beh_hole(self):
        import pytest
        sequence = ["ALIFf1", "BEi3", "BEmsd1", "NUNf1"]
        self.assert_height(sequence, 300, 400)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 0, 300)
        self.assert_kern_within(sequence, 100, -100, -30)


    def test_alif_lam(self):
        import pytest
        sequence = ["ALIFf1", "LAMi1"]
        self.assert_height(sequence, 0, 0)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 0, 0)
        assert distance == pytest.approx(158, 1)
        self.assert_kern_within(sequence, 150, -10, 0)

    def test_ir_ir(self):
        import pytest
        sequence = ["REf1", "BEi13", "REf1"]
        self.assert_height(sequence, 250, 300)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 0, 264)
        assert distance == pytest.approx(387, 1)
        self.assert_kern_within(sequence, 264, -100, -50)

    def test_mim_kaf(self):
        logger.setLevel(logging.DEBUG)
        sequence = ["REf1", "KAFi1"]
        self.assert_kern_within(sequence, 100, -200, -100, height=595)

    def test_re_be_alif(self):
        import pytest
        logger.setLevel(logging.DEBUG)
        sequence = ["REu1", "BEi3", "ALIFf1"]
        self.assert_height(sequence, 60, 70)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 62, 264)
        assert distance == pytest.approx(198, 5)
        self.assert_kern_within(sequence, 100, -120, -90, height=100)

if __name__ == '__main__':
    import pytest
    import sys
    pytest.main([sys.argv[0]] + sys.argv[2:])
