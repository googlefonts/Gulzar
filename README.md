# Gulzar

Gulzar is a Nastaliq font for Urdu text with a typographic, rather than calligraphic feel.

## Note to other font designers

We hope that Gulzar will serve as a reference and model for other Nastaliq font designs, in particular in terms of its engineering and shaping rules. If you are looking to design a Nastaliq font, you will find some documentation on the Gulzar system and how it works in [engineering.md](engineering.md).

## Set up instructions

Only needs to be done once:

```
sudo pip3 install -r requirements.txt
```

## Build instructions

Don't try exporting from Glyphs! It's not going to work!

* Run `make`
* Output can be found in `fonts/ttf/Gulzar-Regular.ttf`

## Makefile targets

* `make` produces a debug version of the font.
* `make release` produces a version of the font suitable for release.
* `make test-shaping` checks the shaping rules and produces a report in `qa/shaping_tests/report.html`.
* `make test` runs a full fontbakery check on the font.
* `make proof` produces `urdu-john.pdf`, a comparison between Noto Nastaliq and GS Nastaliq.
* `make testproof` produces `test-failures.pdf`, PDF containing words with collisions.

## Fixing dot collisions

If you find a colliding sequence between two "words" (i.e. final glyph -> initial glyph + dots), you need to:

* Add the sequence to `qa/shaping_tests/collisions.json` so it can be tested.
* Create a debug build of the font; the `Makefile` by default turns on `FONTTOOLS_LOOKUP_DEBUGGING=1` which creates a `Debg` table in the final font. This is stripped when building the release version.
* Strip the sequence down to the smallest possible string which collides. Paste that string into [Crowbar](http://www.corvelsoftware.co.uk/crowbar/) with the debug build of the font.
* Look down the list of trigged lookups to determine the sequence height. The list will include lookup names like `At_600_800_AtHeight600sub` and `At_600_800_AtHeight600pos` - this tells you the height-specific lookup routines you need to modify to mitigate the collision.
* Find those lookups in `anchor-attachment.fez`.
* Decide how you want to mitigate the collision. You can either:
    *  drop the dot one position (call `DropOne` in the `sub` lookup)
    *  drop it two positions (`DropTwo` in `sub`)
* and/or:
    *  open a short space (`OpenSmallSpaceBeforeKern` in `pos`) 
    *  open a large space (`OpenSpaceBeforeKern` in `pos)`
    *  bring the final glyph closer to the initial glyph (`Tighten` in `pos`)
    *  move the dots down a little further (`DropATinyBitMore`) or a lot further (`DropALotMore`, both in `pos`)
    *  raise the dots a little (`Raise` in `pos`)
    *  or do something more fancy, and create a new routine to reposition the dots elsewhere.
* Add a Chain rule call the appropriate routine(s). This is a bit of an art form. It should be as general as possible to avoid proliferating unnecessary rules, but as specific as possible to avoid interacting with other sequences in bad ways. Some hints:
    * Try to use the shape-based classes (e.g. `@dal_like`) to address the final glyph and all other glyphs like it.
    * Check out other similar sequences to see how best to address the initial glyph.
    * Consider using `DoNothing` and `DoNothingPos` (ignore rules) to create exceptions for existing situations.
* Rebuild the font and run `make test-shaping` to make sure there are no unwanted interactions with other sequences.

## Scripts

This repository also contains FEZ plugins for Nastaliq as well as scripts to build the font file:

* `dump-glyphs-rules.py` turns the Nastaliq Connection information within the `.glyphs` file into a CSV file so that it can be processed by the `nastaliqTools.NastaliqConnections` plugin.
* `find-notdefs.py` finds characters not currently mapped in the font.
* `lint-arabic.py` finds missing entry/exit anchors (and will, in the future, also detect other anchor issues.)
