GLYPHS_FILE=Qalmi_Borna_Latest.glyphs
PROJECT_NAME=gs-nastaliq
FINAL_FONT=Qalmi_Borna-Regular.ttf
export PYTHONPATH=.

.DELETE_ON_ERROR:

master_ttf/Qalmi_Borna-Regular.ttf: features.fea $(GLYPHS_FILE)
	fontmake --master-dir . -g $(GLYPHS_FILE) -o ttf

features.fea: $(PROJECT_NAME).fee anchors.fee rules.csv $(GLYPHS_FILE)
	# python3 fixup-glyphs-file.py $(GLYPHS_FILE) features.fea
	fee2fea -O0 $(GLYPHS_FILE) $(PROJECT_NAME).fee > features.fea

clean:
	rm -f master_ttf/Qalmi_Borna-Regular.ttf features.fea anchors.fee rules.csv

anchors.fee: $(GLYPHS_FILE)
	python3 dump-fee-anchors.py $(GLYPHS_FILE) > anchors.fee

rules.csv: $(GLYPHS_FILE)
	python3 dump-glyphs-rules.py $(GLYPHS_FILE) > rules.csv

test: master_ttf/$(FINAL_FONT) regressions.txt
	fontbakery check-profile -m FAIL -v ./gnipahs.py master_ttf/$(FINAL_FONT)

testproof: master_ttf/$(FINAL_FONT) regressions.txt
	gnipahs master_ttf/$(FINAL_FONT) regressions.txt

proof: master_ttf/$(FINAL_FONT) urdu-john.sil
	sile urdu-john.sil
