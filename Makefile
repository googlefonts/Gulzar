GLYPHS_FILE=sources/Gulzar.glyphs
FINAL_FONT=fonts/ttf/Gulzar-Regular.ttf
FEA_FILES=sources/build/fea/languagesystem.fea sources/build/fea/decomposition.fea sources/build/fea/connections.fea sources/build/fea/bariye-drop.fea sources/build/fea/bariye-drop2.fea  sources/build/fea/kerning.fea sources/build/fea/anchor-attachment.fea sources/build/fea/latin-kerning.fea sources/build/fea/post-mkmk-repositioning.fea sources/build/fea/bariye-overhang.fea
RELEASE_ARG=
PYTHON=python3

export FONTTOOLS_LOOKUP_DEBUGGING=1
export PYTHONPATH=.
#export FONTTOOLS_GPOS_COMPACT_MODE=9
.DELETE_ON_ERROR:

$(FINAL_FONT): venv sources/build/features.fea $(GLYPHS_FILE)
	. venv/bin/activate; fontmake -f --master-dir . -g $(GLYPHS_FILE) --filter DecomposeTransformedComponentsFilter --no-production-names -o ttf --output-path $(FINAL_FONT)
	. venv/bin/activate; $(PYTHON) -m fontTools.feaLib -o $(FINAL_FONT) -v -v sources/build/features.fea $(FINAL_FONT)

venv: venv/touchfile

build.stamp: venv
	. venv/bin/activate

venv/touchfile: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	touch venv/touchfile

replace: venv sources/build/features.fea
	. venv/bin/activate; fonttools feaLib -o $(FINAL_FONT) -v -v sources/build/features.fea $(FINAL_FONT)

release: venv $(FINAL_FONT)
	hb-subset --unicodes='*' --glyph-names $(FINAL_FONT) --layout-features="*"  -o $(FINALFONT)
	. venv/bin/activate; ttfautohint $(FINAL_FONT) $(FINAL_FONT).autohint
	. venv/bin/activate; gftools-fix-font.py --include-source-fixes -o $(FINAL_FONT) $(FINAL_FONT).autohint
	. venv/bin/activate; font-v write --sha1 $(RELEASE_ARG) $(FINAL_FONT)

sources/build/features.fea: $(FEA_FILES)
	cat $^ > sources/build/features.fea

clean:
	rm -f $(FINAL_FONT) sources/build/features.fea sources/build/rules.csv sources/build/fea/*

specimen: specimen/specimen.pdf

sources/build/rules.csv: $(GLYPHS_FILE)
	python3 scripts/dump-glyphs-rules.py $(GLYPHS_FILE)

test: $(FINAL_FONT)
	. venv/bin/activate; fontbakery check-googlefonts -l WARN --html fontbakery-report.html --ghmarkdown fontbakery-report.md $(FINAL_FONT)

test-shaping: $(FINAL_FONT)
	. venv/bin/activate; fontbakery check-profile --html report.html --config fontbakery.yml --ghmarkdown report.md fontbakery.profiles.shaping $(FINAL_FONT)

testproof: $(FINAL_FONT) regressions.txt
	gnipahs $(FINAL_FONT) regressions.txt

proof: $(FINAL_FONT) qa/urdu-john.sil
	sile qa/urdu-john.sil

specimen/specimen.pdf: $(FINAL_FONT) specimen/specimen.sil
	cd specimen ; sile specimen.sil

sources/build/fea/languagesystem.fea: sources/build/fez/languages.fez venv
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/decomposition.fea: sources/build/fez/decomposition.fez venv
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/connections.fea: sources/build/fez/connections.fez sources/build/rules.csv venv
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/anchor-attachment.fea: sources/build/fez/anchor-attachment.fez venv $(GLYPHS_FILE)
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/kerning.fea: sources/build/fez/kerning.fez sources/build/fez/shared.fez venv qalamTools/NastaliqKerning.py $(GLYPHS_FILE)
	. venv/bin/activate; fez2fea -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/latin-kerning.fea: sources/build/fez/latin-kerning.fez $(GLYPHS_FILE) venv
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/post-mkmk-repositioning.fea: sources/build/fez/post-mkmk-repositioning.fez sources/build/fez/shared.fez venv
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

# Technically these two should depend on the Glyphs file, but since the design
# and width of glyphs is mostly fixed, I'm removing that dependency for now.
sources/build/fea/bariye-drop.fea: sources/build/fez/bariye-drop.fez sources/build/fez/shared.fez venv qalamTools/YBFix.py
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/bariye-drop2.fea: sources/build/fez/bariye-drop2.fez sources/build/fez/shared.fez venv qalamTools/YBFix.py
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

sources/build/fea/bariye-overhang.fea: sources/build/fez/bariye-overhang.fez sources/build/fez/shared.fez venv
	. venv/bin/activate; fez2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@
