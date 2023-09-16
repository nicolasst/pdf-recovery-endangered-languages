# Recovering Text from Endangered Languages Corrupted PDF documents

Interactive recovery of the text associated to a specific font in a corrupted PDF document when language models can not be used

scientific article: https://aclanthology.org/2022.computel-1.10/

## Introduction

Corrupted PDF are actually PDF whose font are corrupted, which means that the associated from CID (Character ID) as encoded in the PDF to the Unicode codepoint (i.e character) to display is incorrect.
The whole purpose of this program is to help hasten the recovery of a correcte CID to Unicode mapping, and hence of the full text.
It requires the user to enter parts of text or some of the wordverbatim as seen in the text. The programs then matches input text by the user to CID sequences in the PDF, performs inferences and uses heuristics to guess the mapping.
As such it is possible to recover the entirety of a ducment by transcribring only a tiny fraction of the text.

## Requirements

requires the installation of the command line tool from PDFMINER: https://pdfminersix.readthedocs.io/en/latest/tutorial/commandline.html, networkx and pandas

## Procedure

1) extract codepoint+layout from PDF to xml
   
    `pdf2txt.py -t xml Nivkh.pdf  > niv.xml`
  
3) recover interatctively the text

    `python3 recover_text.py niv.xml`

In order to recover the text, it necessary to set the variables:

    list_queries = []       : list of sentences (actually continugous sequence of characters over a line) exactly as seen in the text
    list_sure_words = []    : list of words (contiguous sequences of characters separated by as space/start of line/end of line) for which the presence in the text is certain
    map_char_combining = {} : if the text uses combining char to represent letters not existing in unicode, specify the mapping here
    fixed_map = {}          : mapping of CID to unicode characters (to be avoided to do manually as much as possible, but sometimes faster and sometimes mandatorry)
    target_font = None      : the font for which the recovery is made must be specified (list of possible fonts displayed when running first time on the document)

This script produce extensive output on stdout and several files:

    <stdout>                : contains most of the information useful to selected next char/word/line candidate to add to the input data
    recovered_text.txt      : contains only the recovered text of the target font with line number to help specify the information in the input data
    recovered_document.txt  : the final (or partial until recovery is not complete) document contains all the text in the document for all the fonts
    document_raw.csv        : convertion of PDFMINER output to a csv file for a quick look at the structure
    bigrams_graph.gexf      : the graph made from the bigrams of all the lines, in case of difficulty to determine the punctuation and characters

These outputs must be checked to consider the best candidate of character, word or line to encode in the input data, several iteration are necessary.

Firstly, it is mandatory to specify the font to recover, a set of choice will be presented to the user

Secondly, it is mandatory to correctly guess with the implemented heuristics (whose output must be checked) or fix manually in order to further proceed.

Only after the dot and space characters the recovery can continue with the users updating the iteratively the above mentioned variables
