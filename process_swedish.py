import os
import re
import json
from lxml import etree
from html import escape, unescape


rxWord = re.compile('\\w', flags=re.DOTALL)
rxNewline = re.compile('^\n+$', flags=re.DOTALL)


def xml2txt(fnameIn, fnameOut):
    xmlTree = etree.parse(fnameIn)
    text = ''
    sentences = xmlTree.xpath('/html/body/para/se[@lang="sv"] | /html/body/p/para/se[@lang="sv"]')
    for sentence in sentences:
        text += sentence.xpath('string()').replace('\n', '<br>') + '\r\n'
    fOut = open(fnameOut, 'w', encoding='utf-8')
    fOut.write(text)
    fOut.close()


def build_ana(token, lemma, pos1, gramm, curAddr, prevAddr):
    if rxNewline.search(lemma) is not None:
        return ''
    bWord = True
    if pos1 in ['PAD', 'MAD', 'MID', 'PID'] or rxWord.search(token) is None:
        bWord = False
    ana = ' ' * (curAddr - prevAddr)
    if bWord:
        ana += '<w><ana lex="' + escape(lemma) + '" gr="' + \
              pos1
        if len(gramm) > 0 and gramm != '_':
            ana += ',' + gramm.lower().replace('|', ',')
        ana += '" />'
    ana += token
    if bWord:
        ana += '</w>'
    return ana


def parsed2xml(fnameInXml, fnameInParsed, fnameOut):
    """
    Read a file analyzed by stagger and the aligned Swedish/Russian XML.
    Generate an XML where the Swedish part is analyzed.
    It is assumed that sentence separation in the parallel XML was identical
    to the line separation in the input file given to stagger. The original
    line separation is deduced from the \r character in the stagger-analyzed
    file, so Windows newlines must be used in the stagger input file.
    """
    # print(fnameInXml)
    fParsed = open(fnameInParsed, 'r', encoding='utf-8', newline='')
    text = fParsed.read()
    fParsed.close()
    lines = re.findall('(?:[^\t]*\t){12}[^\t\n]*\n*', text, flags=re.DOTALL)
    sentences = ['']
    iSent = 0
    prevAddr = 0
    for line in lines:
        try:
            numToken, token, lemma, pos1, pos2, gramm,\
                _1, _2, _3, _4, _5, _6, address = line.strip('\n').split('\t')
        except ValueError:
            print('Error when splitting line: ' + line)
            continue
        if token == '\r':
            iSent += 1
            sentences.append('')
            continue
        curAddr = int(address.split(':')[-1])
        sentences[iSent] += build_ana(token, lemma, pos1, gramm, curAddr, prevAddr)
        prevAddr = curAddr + len(token)
    sentences = [s.strip() for s in sentences]
    if len(sentences[-1]) <= 0:
        sentences = sentences[:-1]
    # print(sentences)

    fOut = open(fnameOut, 'w', encoding='utf-8')
    paraId = -1
    iSe = 0
    lang = 'ru'
    fXml = open(fnameInXml, 'r', encoding='utf-8-sig')
    xmlText = fXml.read()
    xmlText = re.sub('(\n+)(?=</se>)',
                     lambda m: len(m.group(1)) * 2 * ' ',
                     xmlText, flags=re.DOTALL).split('\n')
    fXml.close()
    for line in xmlText:
        line += '\n'
        if re.search('^ *</?(body|head|html)> *\n|^[ \n]*$', line) is not None:
            fOut.write(line)
            continue
        if line.strip().startswith('<weight'):
            continue
        if 'lang="' in line:
            m = re.search('lang="([^\r\n"]*)"', line)
            lang = m.group(1)
        m = re.search('^([ \t]*<se +lang="sv[^<>]*>|^)([^\r\n]*?)'
                      '(</se>[ \t]*\n|\n)', line)
        if m is None or lang != 'sv' or '<para' in m.group(2) or '</para' in m.group(2):
            mPara = re.search('^([ \t]*<para id=")([^"]+)(.*)', line, flags=re.DOTALL)
            if mPara is not None:
                paraId += 1
                fOut.write(mPara.group(1) + str(paraId) + mPara.group(3))
            else:
                fOut.write(line)
            continue
        lineSrc = m.group(2)
        if iSe >= len(sentences):
            print('Error: senetce mismatch. Paragraph ID: ' + str(paraId))
        else:
            lineOut = m.group(1) + sentences[iSe] + m.group(3)
            fOut.write(lineOut)
        iSe += 1
        # print(paraId, lineSrc)
        # print(lineOut)
    fOut.close()


if __name__ == '__main__':
    nFiles2process = 0
    fnamesIn = ''
    for root, dirs, files in os.walk('./texts_2020/'):
        for fname in files:
            if not fname.endswith('.xml') or fname.endswith('analyzed.xml'):
                continue
            fnameFull = os.path.join(root, fname)
            print(fnameFull)
            xml2txt(fnameFull,
                    os.path.join(root, fname[:-3] + 'txt'))
            if not os.path.exists(os.path.join(root, fname[:-3]) + 'txt.conll'):
                fnamesIn += os.path.abspath(os.path.join(root, fname[:-4])) + '.txt '
                nFiles2process += 1
    print('Files to process:', nFiles2process)
    print('java -jar stagger/stagger.jar -modelfile swedish.bin -tag ' + fnamesIn)
    # TODO: Call stagger directly
    x = input('Press any key after tagging is complete...')
    for root, dirs, files in os.walk('./texts_2020/'):
        for fname in files:
            if not fname.endswith('.xml') or fname.endswith('analyzed.xml'):
                continue
            fnameFull = os.path.join(root, fname)
            print(fnameFull)
            nFiles2process += 1
            parsed2xml(fnameFull,
                       fnameFull[:-3] + 'txt.conll',
                       os.path.join('texts_2020/texts_2020_processed',
                                    fname[:-4] + '-analyzed.xml'))
