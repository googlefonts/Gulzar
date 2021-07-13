# Gulzar

Gulzar is a Nastaliq font for Urdu text with a typographic, rather than calligraphic feel.

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

* `make` produces the font.
* `make proof` produces `urdu-john.pdf`, a comparison between Noto Nastaliq and GS Nastaliq.
* `make testproof` produces `test-failures.pdf`, PDF containing words with collisions.

## Scripts

This repository also contains FEZ plugins for Nastaliq as well as scripts to build the font file:

* `dump-glyphs-rules.py` turns the Nastaliq Connection information within the `.glyphs` file into a CSV file so that it can be processed by the `nastaliqTools.NastaliqConnections` plugin.
* `find-notdefs.py` finds characters not currently mapped in the font.
* `lint-arabic.py` finds missing entry/exit anchors (and will, in the future, also detect other anchor issues.)
