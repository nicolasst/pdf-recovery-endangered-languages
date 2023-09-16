
import sys
import re
import json
from collections import Counter

from bs4 import BeautifulSoup
import pandas as pd
import networkx as nx

### Interactive recovery of text associated to a specific font in a corrupted PDF document
###
### requires the installation of the command line tool from PDFMINER: https://pdfminersix.readthedocs.io/en/latest/tutorial/commandline.html
###
### procedure:
### 1) extract codepoint+layout from PDF to xml
###   pdf2txt.py -t xml Nivkh.pdf  > niv.xml
### 2) recover interatctively the text
###   python3 recover_text.py niv.xml
###
### In order to recover the text, it necessary to set the variables:
###
###	list_queries = []       : list of sentences (actually continugous sequence of characters over a line) exactly as seen in the text
###	list_sure_words = []    : list of words (contiguous sequences of characters separated by as space/start of line/end of line) for which the presence in the text is certain
###	map_char_combining = {} : if the text uses combining char to represent letters not existing in unicode, specify the mapping here
###	fixed_map = {}          : mapping of CID to unicode characters (to be avoided to do manually as much as possible, but sometimes faster and sometimes mandatorry)
###	target_font = None      : the font for which the recovery is made must be specified (list of possible fonts displayed when running first time on the document)
###
### This script produce extensive output on stdout and several files:
###   <stdout>                  : contains most of the information useful to selected next char/word/line candidate to add to the input data
###   recovered_text.txt        : contains only the recovered text of the target font with line number to help specify the information in the input data
###   recovered_document.txt    : the final (or partial until recovery is not complete) document contains all the text in the document for all the fonts
###   document_raw.csv          : convertion of PDFMINER output to a csv file for a quick look at the structure
###   bigrams_graph.gexf        : the graph made from the bigrams of all the lines, in case of difficulty to determine the punctuation and characters
###
### These outputs must be checked to consider the best candidate of character, word or line to encode in the input data, several iteration are necessary.
###   It is first mandatory to correctly guess with the implemented heuristics (whose output must be checked) or fix manually in order to further proceed
###   Only after the dot and space characters the recovery can continue with the users updating the iteratively the above mentioned variables
###   Check the 'main' function for more information, where steps are explicitly laid out.
###
### author: Nicolas Stefanovitch (<firstname>.<lastname>@protonmail.com)


def process_document_xml(xml_data):
	""" reads the xml file representation of the PDF document, build internal document representation """

	list_lines = []

	soup = BeautifulSoup(xml_data, features="lxml")

	map_font_alllines = {}

	document_lines = []

	"""
	<page id="1" bbox="0.000,0.000,595.000,842.000" rotate="0">
	<textbox id="0" bbox="271.448,757.374,323.493,767.088">
	<textline bbox="271.448,757.374,323.493,767.088">
	<text font="KJLAKH+CharisSIL" bbox="271.448,757.374,278.364,767.088" colourspace="DeviceGray" ncolour="0" size="9.714">(cid:21)</text>
	"""

	for idx_page, page in enumerate(soup.find_all("page")):

		for idx_line, textline in enumerate(page.find_all("textline")):

			map_font_line = {}
			
			for text in textline.find_all("text"):

				char = text.get_text()

				if char == "\n":
					continue

				has_font = text.has_attr("font")

				if not has_font:
					for font in map_font_line:
						map_font_line[font].append(char)
				else:

					font = text["font"]

					if font not in map_font_line:
						map_font_line[font] = []
					map_font_line[font].append(char)

			for font, line in map_font_line.items():
				if font not in map_font_alllines:
					map_font_alllines[font] = []

				map_font_alllines[font].append(line)

				doc_line = [idx_page, idx_line, font, len(map_font_alllines[font]), len(textline), line]
				document_lines.append(doc_line)

	df_doc = pd.DataFrame(document_lines, columns=["page", "line", "font", "font_line", "len", "text"])
	df_doc.to_csv("document_raw.csv", sep="\t", index=False)

	document_data = [list_lines, document_lines, map_font_alllines]

	return document_data


def produce_document(recovered_text, target_font, recovery_input_data, document_data):
	""" produce the recovered document files based on the infered input data """

	list_lines, document_lines, map_font_alllines = document_data
	list_queries, map_char_combining, list_sure_words, fixed_map = recovery_input_data

	rec_text_lines = recovered_text.split("\n")

	rec_doc = ""

	idx_rec = 0

	for page, line, font, font_line, len, text in document_lines:
		if font != target_font:
			rec_doc += "".join(text)

		else:
			rec_doc += rec_text_lines[idx_rec]
			idx_rec += 1

		rec_doc += "\n"

	for from_, to_ in map_char_combining.items():
		print("FROM", from_, "TO", to_)
		rec_doc = rec_doc.replace(from_, to_)

	with open("recovered_document.txt", "w") as f:
		print(rec_doc, file=f)

				
def search_inside(lines, recovery_input_data, map_cid_char=None):
	""" performs inference using the input data """

	list_queries, map_char_combining, list_sure_words, fixed_map = recovery_input_data

	print("* SEARCH PROFILE")

	map_cid_char = {} if map_cid_char is None else map_cid_char
	
	for query in list_queries:

		print("SEARCH", query)

		if "=>" in query:
			line_cue, query = query.split("=>")
			line_cue = int(line_cue)
		else:
			line_cue = None
		print("cue", line_cue, "query", query)

		profile_query = " ".join([str(len(x)) for x in query.split()])

		print("->", ">>"+profile_query+"<<")

		maybe_matches = []

		for idx, line in enumerate(lines):
			
			profile_line = " ".join([str(len(x.split(":"))) for x in line])
			print("line", idx, "=>", profile_line)

			if profile_query in profile_line:
				maybe_matches.append([idx, profile_line])

		if line_cue is not None:
			for idx, prof in maybe_matches:
				print("??", idx, ">>"+prof+"<<")
				if idx == line_cue and profile_query in prof:
					print("FOUND LINE CUE!")
					maybe_matches = [[idx, prof]]
					break

		if len(maybe_matches) > 1 :
			print("TOO many matches!")
			for idx, prof in maybe_matches:
				print("query", profile_query)
				print("match", idx, "=>", prof)

		elif len(maybe_matches) == 1:
			idx, prof = maybe_matches[0]
			print("* assuming match", idx)
			print("query", profile_query)
			print("match", prof)

			line = lines[idx]

			match_start = prof.index(profile_query)
			match_end = match_start +len(profile_query)
			
			idx_start = prof[:match_start].count(" ")
			idx_end = idx_start + profile_query.count(" ")+1

			list_words_cid = line[idx_start:idx_end]
			list_words_cid = [w.split(":") for w in list_words_cid]

			list_words_char = query.split()
			list_words_char = [ [x for x in w] for w in list_words_char]

			print(line)
			print(idx_start, idx_end)
			print(match_start, match_end)
			print(list_words_char)
			print(list_words_cid)

			for word_cid, word_char in zip(list_words_cid, list_words_char):
				for cid, char in zip(word_cid, word_char):
					if cid in map_cid_char:
						if map_cid_char[cid] != char:
							print("!!! INCONSISTENT !!!", cid, char, map_cid_char[cid])
							lllll
					if cid in fixed_map:
						if fixed_map[cid] != char:
							print("!!! INCONSISTENT WITH FIXED MAP !!!", cid, char, map_cid_char[cid])
					print("new", cid, "->", char)
					map_cid_char[cid] = char

	print(map_cid_char)

	print("* EXPLOITING SURE WORD LIST")

	list_decoded_words = set()
	map_decodedword_re = {}
	map_decodedword_cidword = {}

	for idx, line in enumerate(lines):
		for word in line:
			word = re.sub(r"^:", "", word) # temporary hack until, no word begins with a : because of replacement of space cid
			rec_word = ""
			rec_word_re = r"^"
			previous_cid = False
			is_first = True
			for cid in word.split(":"):
				if cid in map_cid_char:
					rec_word += (":" if previous_cid and not is_first else "") +map_cid_char[cid]
					rec_word_re += map_cid_char[cid]
					previous_cid = False
				else:
					rec_word += (":" if not is_first else "")+cid
					rec_word_re += r"(.{1})"
					previous_cid = True
				is_first = False
			rec_word_re += r"$"
			list_decoded_words.add(rec_word)
			map_decodedword_re[rec_word] = rec_word_re
			map_decodedword_cidword[rec_word] = word 

	print(list_decoded_words)

	for sure_word in list_sure_words:
		list_matches = [ word for word in list_decoded_words if re.search( map_decodedword_re[word], sure_word) ]
		list_matches = [ [word,  re.search( map_decodedword_re[word], sure_word).groups() ] for word in list_decoded_words if re.search( map_decodedword_re[word], sure_word) ]

		list_matches = sorted(list_matches, key=lambda x: len(x[1]), reverse=False)
		print(list_matches)

		if len(list_matches) > 1 and len(list_matches[0][1]) < len(list_matches[1][1]):
			print("find uniq max length match! Houray!")
			list_matches = [list_matches[0]]
			print(list_matches)


		print("search WORD", sure_word)
		if len(list_matches) == 0:
			print("no matches!")
		elif len(list_matches) > 1:
			print("too many matches!")
			print(list_matches)
		else:
			rec_word = list_matches[0][0]
			print("MATCH!", rec_word)
			word_cid = map_decodedword_cidword[rec_word].split(":")
			word_char = sure_word
			for cid, char in zip(word_cid, word_char):
				if cid in map_cid_char:
					if map_cid_char[cid] != char:
						print("!!! INCONSISTENT !!!", cid, char, map_cid_char[cid])
				if cid in fixed_map:
					if fixed_map[cid] != char:
						print("!!! INCONSISTENT WITH FIXED MAP !!!", cid, char, map_cid_char[cid])
				print("new", cid, "->", char)
				map_cid_char[cid] = char



		print(map_cid_char)

	print("GUESS CAPS")

	list_fullydecoded_words = set()
	map_undecodedword_re = {}
	map_undecodedword_cidword = {}

	list_undecoded_words = set()

	rec_text = ""
	for idx, line in enumerate(lines):
		rec_line = ""
		for word in line:
			rec_word = ""
			rec_word_re = r"^"
			previous_cid = False
			has_cid = False
			for cid in word.split(":"):
				if cid in map_cid_char:
					rec_word += (":" if previous_cid else "") +map_cid_char[cid]
					rec_word_re += map_cid_char[cid]
					previous_cid = False
				else:
					rec_word += ":"+cid
					rec_word_re += r"(.{1})"
					previous_cid = True
					has_cid = True
			if has_cid:
				list_undecoded_words.add(rec_word)
			rec_word_re += r"$"

			list_fullydecoded_words.add(rec_word)
			map_undecodedword_re[rec_word] = rec_word_re
			map_undecodedword_cidword[rec_word] = word
			rec_line += " "
		rec_line = rec_line[:-1] + "\n"
		rec_text += rec_line

	for unrec_word in list_undecoded_words:
		print("try", unrec_word)

		unrec_re = map_undecodedword_re[unrec_word]

		is_first_word = re.search(r"(^ *|\. )"+unrec_re[1:-1]+r"\b", rec_text)

		if not is_first_word:
			print("not first word")
			continue

		list_matches = [word for word in list_fullydecoded_words if re.search(map_undecodedword_re[unrec_word], word) ]

		print(map_undecodedword_re[unrec_word])
		print(list_matches)

		if len(list_matches) == 0:
			print("no match :(")
		elif len(list_matches) > 1:
			print("too many matches!")
			print(list_matches)
		else:
			print("Match caps! :D")
			match = re.match(unrec_re).group(0)
			print(match)


	print(sorted(list_fullydecoded_words))


	print("RECOVERED TEXT")

	print("+++++++++++++++++++++++++")

	map_unreccid_line = {}
	map_line_unreccid = {}

	rec_text = ""

	list_reclines = []

	for idx, line in enumerate(lines):
		rec_line = ""
		list_unrec = []
		for word in line:
			previous_cid = False
			for cid in word.split(":"):
				if cid in map_cid_char:
					rec_line += (":" if previous_cid else "") +map_cid_char[cid]
					previous_cid = False
				else:
					rec_line += ":"+cid
					previous_cid = True
					if cid not in map_unreccid_line:
						map_unreccid_line[cid] = []
					map_unreccid_line[cid].append(idx)
					list_unrec += [cid]

			rec_line += " "
		rec_line = rec_line[:-1] + "\n"
		rec_text += rec_line
		list_reclines.append(rec_line)
		if len(list_unrec) > 0:
			map_line_unreccid[idx] = list_unrec

	for from_, to_ in fixed_map.items():
		rec_text = rec_text.replace(from_, to_)

	print(rec_text)
					
	with open("recovered_text.txt", "w") as f:
		print("\n".join([("l.%04d:\t" % idx)+line for idx,line in enumerate(rec_text.split("\n"))]), file=f)

	print("+++++++++++++++++++++++++")

	sorted_unrec_cid = sorted(map_unreccid_line.items(), key=lambda x: len(x[1]), reverse=True)

	print("REMAINING SYMBOLS TO DECODE", len(map_line_unreccid), "lines", len(sorted_unrec_cid), "cid")
	print( len(map_cid_char) ,"done", ("%.3f" % (len(map_cid_char)/(len(map_cid_char)+len(sorted_unrec_cid))) ))

	for cid, list_idxlines in sorted_unrec_cid:
		print("* unrec cid", cid, "count:", len(list_idxlines))
		for idx in list_idxlines[:3]:
			print(idx, list_reclines[idx], end="")
		print()

	print("LINES WITH MOST REMAINING SYMBOLS")

	sorted_unrec_cid = sorted(map_line_unreccid.items(), key=lambda x: len(x[1]), reverse=True)

	for idx, list_cid in sorted_unrec_cid:
		print(idx, list_cid, list_reclines[idx], end="")

	recovery_done = len(sorted_unrec_cid) == 0
	
	return rec_text, recovery_done


def guess_words(all_lines_str, dotspace):
	""" for interactive searching of the right encoding for dot and space characters in order to properly separate word, mandatory for the rest of the procedure to unfold corectly.
	To this aim, this function displays statistics on word lengths assuming the characters specified in parameters. It is up to the user to either rely on automatic guessing, and in case of faillure to either improve it ;) or to manually guess them with the availlable info (mostly the graph, the CSV and the lenght histogram)"""

	dot, space = dotspace.split(":")

	text = all_lines_str.replace("\n", " ")
	text = re.sub(r":?\b"+dotspace +r"\b:?", "   ", text)
	text = re.sub(r":?\b"+space +r"\b:?", " ", text)

	print(text)
	print(dotspace)

	print("==== ALL WORDS")

	count_words = Counter(text.split())
	print(len(count_words))

	print("=== TOP WORDS")

	print(count_words.most_common(50))

	graph = nx.Graph()

	list_words = []

	todo=30
	for w,count in count_words.most_common(200):
		if len(w.split(":")) > 3:
			continue
		if len(w) == 1:
			continue
		todo -= 1
		if not todo:
			break
		chars = w.split(":")
		chars = ["START"] + chars + ["END"]

		count = int(count)

		list_words.append([w,count])

#		for c in chars:
#			graph.add_edge(str(w), c, weight=count)

		for i in range(len(chars)-1):
			c1 = chars[i]
			c2 = chars[i+1]
			weight = 0 if not graph.has_edge(c1, c2) else graph[c1][c2]["weight"]
			graph.add_edge(c1, c2, weight=weight+count)

	nx.write_gexf(graph, "bigrams_graph.gexf")

	print()
	print(list_words)

	print("=== LONGEST WORDS")

	items = count_words.most_common()
	items = sorted(count_words, key=len, reverse=True)

	print(items[:20])

	print("==== len allwords")

	print(Counter([len(x) for x in count_words]))

	###

	# perform actual replacement of space and dots in the text

	text = all_lines_str.replace("\n", " ")
	text = re.sub(r":?\b"+dotspace +r"\b:?", ". ", text)
	text = re.sub(r":?\b"+space +r"\b:?", " ", text)

	return text


def recover_punctuation(all_lines_str, count_all, count_last, count_start, count_cidline):
	""" tries to guess the CID of the dot and space characters """
	
	print(all_lines_str)

	list_lines = all_lines_str.split()
	list_len = [len(line) for line in list_lines]
	max_len = max(list_len)

	count_middlend = Counter([line.split(":")[-1] for line in list_lines if len(line) > max_len * 0.20 and len(line) < max_len * 0.80 ])
	most_middlend = sorted(count_middlend.items(), key=lambda x: x[1], reverse=True)

	print("most common cid in the middle of the lines:")
	print(most_middlend)

	most_common_cidline = sorted(count_cidline.items(), key=lambda x: x[1], reverse=True)
	most_common_start = sorted(count_start.items(), key=lambda x: x[1], reverse=True)
	most_common_final = sorted(count_last.items(), key=lambda x: x[1], reverse=True)
	most_common_all = sorted(count_all.items(), key=lambda x: x[1], reverse=True)

	tot_lines = all_lines_str.count("\n") + 1

	print("most common final cid of the lines:")
	print(most_common_final)

	if len(most_common_final) < 1:
		return None

	# 3 heuristics to guess the cid of " "

	# the most common cid
	maybe_space1 = most_common_all[0][0]

	# the cid appearing on the most lines
	maybe_space2 = most_common_cidline[0][0]

	# the cid that appears on the most lines but is an affix in less than 10% of the lines (if so it is probalby a dot or a comma)
	maybe_space3 = None

	for e in most_common_cidline:
		cid = e[0]
		tot = 0
		tot += count_start[cid] if cid in count_start else 0
		tot += count_last[cid] if cid in count_last else 0
		if tot > 0.1 * tot_lines:
			print("skip too often afix", cid)
			continue
		maybe_space3 = cid
		break

	if maybe_space1 == maybe_space2 and maybe_space1 == maybe_space3:
		print("consistent heuristics")
		print(maybe_space1)
		maybe_space = maybe_space1
	else:
		print("UNCONSISTANT HEURISTICS!!")
		print(maybe_space1, maybe_space2, maybe_space3)
		maybe_space = maybe_space3
		maybe_space = maybe_space2


	count_sb = lambda x: len(list(re.finditer(r"\b"+x+r"\b", all_lines_str)))

	if False:
		count_maybedot = Counter()
		print("most common final", most_common_final)
		for idx in range(min(100, len(most_common_final))):
			maybe_dot = most_common_final[idx][0]
			if  maybe_dot == maybe_space:
				print("skip maybe space", maybe_space)
				continue
			if maybe_dot in count_start:
				print("skip in start", maybe_dot)
				continue
			maybe_dotspace = maybe_dot +":"+ maybe_space
			count_maybedot.update({maybe_dot: count_sb(maybe_dotspace)})
		
		maybe_comma = count_maybedot.most_common()[0][0]
		maybe_dot = most_common_final[0][0]#count_maybedot.most_common()[1][0]
		maybe_dot = maybe_dot if maybe_dot != maybe_comma else most_common_final[1][0]
	else:
		maybe_dot = most_middlend[0][0]
		maybe_comma = None
		

	print("dot", maybe_dot)
	print("comma", maybe_comma)
	print("space", maybe_space)

	print("space dot", maybe_space, maybe_dot)

	maybe_dotspace = maybe_dot +":"+ maybe_space

	print("count space+dot", count_sb(maybe_dotspace))

	return maybe_dotspace


def process_font_allcid(target_font, recovery_input_data, document_data, all_lines, keep_punctuation):
	""" apply knows rule to text and infers new CID-character pairs """
	
	list_queries, map_char_combining, list_sure_words, fixed_map = recovery_input_data

	print("PROCESS ALL CID")

	all_lines = [ [re.sub(r"[^0-9]", "", x) for x in line] for line in all_lines]

	count_cid = Counter()
	count_last = Counter()
	count_start = Counter()
	count_cidline = Counter()

	for line in all_lines:
		print(line)
		count_cid.update(line)
		count_last.update([line[-1]])
		count_start.update([line[0]])
		count_cidline.update(set(line))


	all_lines_str = "\n".join([ ":".join(line) for line in all_lines])

	print(all_lines_str)

	if not keep_punctuation:
		# guess the symbols for "." and " "
		dotspace = recover_punctuation(all_lines_str, count_cid, count_last, count_start, count_cidline)
	else:
		# in case the encoding of these symbols is not corrupted in the document at hand, they can be explicitly defined here
		dotspace = ".: "

	text = guess_words(all_lines_str, dotspace)

	if list_queries is not None or True:
		dot, space = dotspace.split(":")

		text = all_lines_str
		if not keep_punctuation:
			text = re.sub(r"(:|\b)"+space+r"(:|\b)", " ", text)
		else:
			pass

		print(text)

		map_cid_char = {}
		map_cid_char[dot] = "."

		all_lines_worded = [ line.split() for line in text.split("\n")]
		recovered_text, status = search_inside(all_lines_worded, recovery_input_data, map_cid_char)

		produce_document(recovered_text, target_font, recovery_input_data, document_data)

	print()
	print("********")

	print("all")
	print(len(count_cid))
	print(count_cid.most_common())

	print("start")
	print(len(count_start))
	print(count_start.most_common())

	print("last")
	print(len(count_last))
	print(count_last.most_common())

	print("cidline")
	print(len(count_cidline))
	print(count_cidline.most_common())
	print("lines", len(all_lines))

	return status


def remap_cid(list_cid, keep_punctuation=False):
	map_old_new = {}
	for i, old in enumerate(list_cid):
		new = "(newcid:"+str(i)+")"
		if keep_punctuation and old in [" ", ".", ","]:
			map_old_new[old] = old
		else:
			map_old_new[old] = new
	return map_old_new

def process_font(target_font, recovery_input_data, document_data, force_cid=False, keep_punctuation=False):

	list_lines, document_lines, map_font_alllines = document_data
	
	all_lines = map_font_alllines[target_font]

	all_cid = all(["cid" in char for line in map_font_alllines[target_font] for char in line])

	count_cid = sum(["cid" in char for line in map_font_alllines[target_font] for char in line])
	count_tot = sum([True for line in map_font_alllines[target_font] for char in line])

	print("cid", count_cid)
	print("tot", count_tot)
	print("lines", len(all_lines))

	most_cid = count_cid > 1/3. * count_tot

	if force_cid:
		print("FORCE CONVERTION TO CID")

	if most_cid or force_cid:
		print("MOST CID CONVERT")

		all_lines = map_font_alllines[target_font]
		list_cid = sorted(list(set([x for y in all_lines for x in y])))

		convert = remap_cid(list_cid, keep_punctuation)

		print(convert)
		
		all_lines = [ [convert[old] for old in line] for line in all_lines]
		map_font_alllines[target_font] = all_lines

	all_cid = all(["cid" in char for line in map_font_alllines[target_font] for char in line])
		
	if all_cid or force_cid:
		print(json.dumps(map_font_alllines[target_font], indent=4))
		status = process_font_allcid(target_font, recovery_input_data, document_data, map_font_alllines[target_font], keep_punctuation)

	return status

def main():

	# READ DOCUMENT

	print("==== STEP 1: Read PDF2XML output of the document to recover")

	if len(sys.argv) != 2:
		print("usage:", sys.argv[0], "file.xml")
		sys.exit(1)

	try:
		xml_fp = sys.argv[1]
		xml_data = open(xml_fp).read()

		document_data = process_document_xml(xml_data)
	except:
		print("ERROR: the file in argument must be producedd by applying pdf2xml to the pdf (e.g. pdf2txt.py -t xml Nivkh.pdf > niv.xml)")
		sys.exit(1)


	list_lines, document_lines, map_font_alllines = document_data

	# RECOVERY INPUT DATA

	### the folowing fields to be completed interactively to perform recovery of document, see example bellow
	list_queries = []
	list_sure_words = []
	map_char_combining = {}
	fixed_map = {}
	target_font = None

	### example of input data for recoveering the UDHR in Nivkh (iso:niv) (https://www.ohchr.org/sites/default/files/UDHR/Documents/UDHR_Translations/Nivkh.pdf)
	#list_queries = ["221=>ӿымди қ`оӻл уйгид", "Ниғвӊ дуфтоӿ вылӊуд Санги", "Нивӊ қ`атьгун ӿара, чуғун ӿара сик намадивӊчоғҏ", "Организация Объединенных Наций цельғундоӿ ёскиндфурнд", "эна положенияяғун ивӻай напы п`ӿатьӿать қаврна, п`ӊафқ-ӊафқ", "самоуправляющаяся ӿа ӷаврд лу,", "Генеральная Ассамблея туӊ сик", "Декларация задача ӿагун провозглашайдра", "Чу п`ӿоӻара, сикак маӊра ӿаӊ общество"]
	#list_sure_words = ["ӿекинд", "удовлетворить", "зақоўид.", "Произвольно", "Техническое", "п`Уставух", "Конституцияғиҏ", "Ин", "Қ`атьӊгун", "Эӻлгун", "Ӿаӊы", "Ыткғун", "Ҏаӊӷымкмунд"]
	#map_char_combining = {"ҏ": "р̌", "Ҏ": "Р̌"}
	#fixed_map = {}
	#target_font = "OTOUXR+HeliosNivkh"

	#
	recovery_input_data = [list_queries, map_char_combining, list_sure_words, fixed_map]

	# FONT SELECTION

	print("==== STEP 2: Choosing font to recover")
	print("fonts and number of assosciated lines in the document:")
	for font, values in map_font_alllines.items():
		print(font, len(values))

	print("----")
	if target_font is None:
		if len(map_font_alllines) == 1:
			print("WARNING: only on font in the document, set the font parameter to:", list(map_font_alllines.keys())[0], "to proceed with the recovery")
			sys.exit(1)
		else:
			print("WARNING: document has several fonts, specify which font from", list(map_font_alllines.keys()), "to recover before proceding")
			sys.exit(1)
	else:
		if target_font in map_font_alllines:
			print("target font:", target_font)
		else:
			print("ERROR: target font", target_font, "is not part of the fonts of the document")

	# RECOVERY

	print("==== STEP 3: specify input data to start the recovery process")
	no_data = len(list_queries) + len(list_sure_words) + len(fixed_map) == 0

	if no_data:
		print("WARNING: no input data")
		sys.exit(1)
	else:
		print("using input data:")
		print(recovery_input_data)

	print("==== STEP 4: Automatic font recovery based on input data")
	status = process_font(target_font, recovery_input_data, document_data, force_cid=True, keep_punctuation=False)

	print(map_font_alllines.keys())
	
	print("==== STEP 5: Interactively, if recovery is not complete, based on the output information select the next words/lines to add to the input data")

	if status:
		print("RECOVERY COMPLETED")
	else:
		print("recovery not completed")

if __name__ == "__main__":
	main()
