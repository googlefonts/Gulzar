from babelfont import Babelfont

f = Babelfont.open("master_ttf/Qalmi_Borna-Regular.ttf")
inchars = set()
notdef = set()
with open("urdu-john.txt") as file:
	for line in file:
		for g in line:
			inchars.add(g)

for c in inchars:
	if not f.glyphForCodepoint(ord(c), fallback = False):
		print("'%c' (U+%04x) notdef" % (c,ord(c)))
