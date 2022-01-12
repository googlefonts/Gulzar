from glyphtools import get_glyph_metrics
from glyphtools.babelfont import get_glyph
from beziers.point import Point
from beziers.line import Line
from itertools import product
from kurbopy import BezPath, TranslateScale, Point, Vec2, Line
from itertools import product
import logging

logger = logging.getLogger("NastaliqKerning")

#logging.basicConfig(level=logging.DEBUG)
bezier_cache = {}
metrics_cache = {}
min_bubble = 0

glyphcache = {}

# We use the Rust-based "kurbopy" module to get the beziers because
# it's very fast.
def get_beziers_new(font, glyph):
    if glyph in glyphcache:
        return glyphcache[glyph]
    glyphset = {k: font.default_master.get_glyph_layer(k) for k in font.glyphs.keys()}
    layer = font.default_master.get_glyph_layer(glyph)
    rv = BezPath.fromDrawable(layer, glyphset)
    glyphcache[glyph] = rv
    return rv

# kurbopy also has a built-in function for finding the minimum distance
# between two Bezier paths, which is *super helpful* for what we want.
def circular_distance(p1, p2):
    return p1.min_distance(p2), None

# Testing different approaches. This finds the minimum horizontal distance
# between two Bezier paths. (we don't use this one.)
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


# Determine the distance between two glyphs, with the right glyph
# offset (kerned) by a certain amount and risen on the Y axis by
# a certain amount
def path_distance(font, left_glyph, right_glyph, x_offset, y_offset, algorithm="circular"):
    # Note that "left" and "right" is *not* in logical order but
    # in visual order.
    left_paths = get_beziers_new(font, left_glyph)
    right_paths = get_beziers_new(font, right_glyph)
    metrics1 = get_glyph_metrics(font, left_glyph)
    metrics2 = get_glyph_metrics(font, right_glyph)

    # Create some transformation matrices to raise the left
    # glyph and kern the right glyph
    offset1 = TranslateScale.translate(Vec2(0, y_offset))
    offset2 = TranslateScale.translate(Vec2(metrics1["width"] + x_offset, 0))

    # We find the minimum distance between each pair of (transformed)
    # paths
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

    # Get exit anchor
    lglyph = get_glyph(font, left_glyph)
    lexit = [a.y for a in lglyph.anchors if a.name == "exit"]
    lexit.append(0)
    height -= lexit[0]
    logger.debug("Height without rise is %i" % (height))

    # Work out the minimum (tightest) possible kern value.
    minimum_possible = -1000
    full_width = max(metrics1["run"] - min(0, metrics1["rsb"]), min_bubble)
    logger.debug("Full width of %s is %i" % (left_glyph, full_width))
    if maxtuck:
        maximum_width = metrics1["width"] * maxtuck
        left_edge = min(-metrics2["lsb"], 0)
        logger.debug("Maximum distance into %s is %i" % (left_glyph, maximum_width))
        logger.debug("Left edge of %s is %i" % (right_glyph, left_edge))
        minimum_possible = left_edge - maximum_width
        logger.debug("Biggest kern is %i" % minimum_possible)

    # Now this is just dumb. If the glyphs are 250 units apart, and
    # we want them to be 100 units apart, we move them by -150 units
    # and try again. Normally that gives you the right answer the first
    # time, but it may be that the shape of the glyphs means that when
    # you move them, a different part of the glyph now becomes the
    # closest point, so it's worth checking again.
    iterations = 0
    kern = 0
    min_distance = -9999
    while iterations < 10 and abs(targetdistance - min_distance) > 10:
        min_distance, debuginfo = path_distance(font, left_glyph, right_glyph, kern, height)
        if min_distance is None:
            return minimum_possible
        kern = kern + (targetdistance - min_distance)
        if kern < minimum_possible:
            return minimum_possible
        iterations = iterations + 1
    logger.debug("%s/%s/%i = %i" % (left_glyph, right_glyph, height, kern))
    if kern > 0:
        return 0
    return kern


# End of main code, everything below is for testing

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
        sequence = ["REf1", "BEi16", "REf1"]
        self.assert_height(sequence, 400, 450)
        height = height_of_init(self.font, sequence[1:])
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 0, height)
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
        assert distance == pytest.approx(198, 1)
        self.assert_kern_within(sequence, 100, -120, -90, height=100)

    def test_re_be_re(self):
        import pytest
        logger.setLevel(logging.DEBUG)
        sequence = ["REf2", "BEi16", "REf1"]
        self.assert_height(sequence, 420, 450)
        distance, debuginfo = path_distance(self.font, sequence[1], sequence[0], 62, 264)
        assert distance == pytest.approx(198, 1)
        self.assert_kern_within(sequence, 100, -120, -90, height=420)

if __name__ == '__main__':
    import pytest
    import sys
    pytest.main([sys.argv[0]] + sys.argv[2:])
