import os
import re
import json
from lxml import etree
from html import escape, unescape

reWords = re.compile('((?:<[^<>\r\n]+>)*)'
                     '([^\\w<>]+|N:r\\b|t\\.o\\.m\\.|o\\.s\\.v\\.|bl\\.a\\.|'
                     'fr\\.o\\.m\\.|t\\.ex\\.|[\\w-]+)((?:[.?!:;() ]*</[^<>\r\n]+>)*)',
                     flags=re.DOTALL)
reWordsSimple = re.compile('(?:^|\\b)[^<>]+?(?:\\b|$)', flags=re.DOTALL)


def xml2txt(fnameIn, fnameOut):
    xmlTree = etree.parse(fnameIn)
    text = ''
    sentences = xmlTree.xpath('/html/body/para/se[@lang="sv"] | /html/body/p/para/se[@lang="sv"]')
    for sentence in sentences:
        text += sentence.xpath('string()').replace('\n', '<br>') + '\r\n'
    fOut = open(fnameOut, 'w', encoding='utf-8')
    fOut.write(text)
    fOut.close()


def parsed2xml_old(fnameInXml, fnameInParsed, fnameOut):
    fXml = open(fnameInXml, 'r', encoding='utf-8-sig')
    fParsed = open(fnameInParsed, 'r', encoding='utf-8')
    parsedWords = []
    for line in fParsed:
        if len(line) < 3:
            continue
        try:
            numToken, token, lemma, pos1, pos2, gramm,\
                _1, _2, _3, _4, _5, _6, address = line.strip().split(u'\t')
        except ValueError:
            continue
        address = int(address.split(':')[-1])
        for token in token.split():
            ana = token
            if token in ['…', '“', '„', '~', '’', '»', '«', '—', '•', '√', '–']:
                continue
            if pos1 not in ['PAD', 'MAD', 'MID', 'PID']:
                ana = '<w><ana lex="' + lemma + '" gr="' +\
                      pos1
                if len(gramm) > 0 and gramm != '_':
                    ana += ',' + gramm.lower().replace('|', ',')
                ana += '" />' + escape(token) + '</w>'
                parsedWords.append((address, token, ana))
    fParsed.close()
    fOut = open(fnameOut, 'w', encoding='utf-8')
    paraId = -1
    iSe = -1
    iWord = 0
    lang = 'ru'
    successiveNonAnalyzed = 0
    bTokenizationProblem = False
    for line in fXml:
        if re.search('^ *</?(body|head|html)> *\n', line) is not None:
            fOut.write(line)
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
        lineOut = m.group(1)
        # print m.group(2)
        words = reWords.findall(m.group(2).replace('&quot;', '"').replace('&apos;', "'"))
        for i in range(len(words) - 2, -1, -1):
            # print words[i]
            if ((words[i][1] == '-' or words[i+1][1].startswith('-') or
                     words[i][1].endswith(':') or (words[i+1][1].startswith(':')
                                                   and len(words[i+1][1]) > 1
                                                   and not (re.search('[0-9]$', words[i][1]) is not None
                                                            and re.search('^:[0-9 ]', words[i+1][1]) is not None)) or
                     words[i][1].endswith("'") or words[i+1][1].startswith("'")) and
                    words[i][2] != ' ') or words[i][2] == "'":
                words[i] = list(words[i])
                words[i][1] = words[i][1] + words[i+1][1]
                words.pop(i+1)
                words[i] = tuple(words[i])
        for word in words:
            wordStripped = word[1].strip()
            if len(wordStripped) <= 0 or iWord >= len(parsedWords):
                lineOut += word[0] + word[1] + word[2]
                continue
            # print wordStripped, iWord, parsedWords[iWord]
            anaWritten = False
            for i in range(iWord, min(iWord + 2, len(parsedWords))):
                address, token, ana = parsedWords[i]
                if token == wordStripped:
                    lineOut += word[0] + ana + word[2]
                    iWord = i + 1
                    anaWritten = True
                    break
            if anaWritten:
                successiveNonAnalyzed = 0
                continue
            if re.search('\\w', word[1]) is not None:
                iWord += 1
                lineOut += word[0] + '<w>' + escape(word[1]) + '</w>' + word[2]
                successiveNonAnalyzed += 1
                if successiveNonAnalyzed > 200:
                    bTokenizationProblem = True
            else:
                lineOut += word[0] + escape(word[1]) + word[2]
        lineOut = lineOut.replace('," />', '" />')
        lineOut += m.group(3)
        fOut.write(lineOut)
    fOut.close()
    if bTokenizationProblem:
        print('Possible tokenization problem.')


def build_ana(token, lemma, pos1, gramm, curAddr, prevAddr):
    if re.search('^\n+$', lemma, flags=re.DOTALL) is not None:
        return ''
    ana = ' ' * (curAddr - prevAddr)
    if pos1 not in ['PAD', 'MAD', 'MID', 'PID']:
        ana += '<w><ana lex="' + escape(lemma) + '" gr="' + \
              pos1
        if len(gramm) > 0 and gramm != '_':
            ana += ',' + gramm.lower().replace('|', ',')
        ana += '" />'
    ana += token
    if pos1 not in ['PAD', 'MAD', 'MID', 'PID']:
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
    print(fnameInXml)
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
    print(sentences)

    #fOut = open(fnameOut, 'w', encoding='utf-8')
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
        if re.search('^ *</?(body|head|html)> *\n', line) is not None:
            #fOut.write(line)
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
                #fOut.write(mPara.group(1) + str(paraId) + mPara.group(3))
            #else:
                #fOut.write(line)
            continue
        lineSrc = m.group(2)
        lineOut = m.group(1) + sentences[iSe] + m.group(3)
        iSe += 1
        print(paraId, lineSrc)
        print(lineOut)
        #fOut.write(lineOut)
    #fOut.close()


if __name__ == '__main__':
    nFiles2process = 0
    for root, dirs, files in os.walk('./texts_2020/'):
        for fname in files:
            if not fname.endswith('.xml') or fname.endswith('analyzed.xml'):
                continue
            fnameFull = os.path.join(root, fname)
            print(fnameFull)
            xml2txt(fnameFull,
                    os.path.join(root, fname[:-3] + 'txt'))
            if not os.path.exists(os.path.join(root, fname[:-4]) + '-out.txt'):
                print('java -jar stagger/stagger.jar -modelfile swedish.bin -tag '
                      + os.path.abspath(os.path.join(root, fname[:-4])) + '.txt >'
                      + os.path.abspath(os.path.join(root, fname[:-4])) + '-out.txt')
                nFiles2process += 1
            # nFiles2process += 1
            # parsed2xml(fnameFull,
            #            fnameFull[:-4] + '-out.txt',
            #            os.path.join('texts_2019.02/texts_2019.02_processed',
            #                         fname[:-4] + '-analyzed.xml'))
    print('Files to process:', nFiles2process)
    #xml2txt(u'text_multi/chajka.xml', u'text_multi/chajka.txt')
    #xml2txt(u'text_multi/sad.xml', u'text_multi/sad.txt')
    #xml2txt(u'text_multi/rodarummet.xml', u'text_multi/rodarummet.txt')
    #xml2txt(u'text_multi/veschi.xml', u'text_multi/veschi.txt')
    # parsed2xml(u'text_multi/3sestry.xml', u'text_multi/3sestry-out.txt',
    #            u'text_multi/3sestry-analyzed.xml')
    # parsed2xml(u'text_multi/vania.xml', u'text_multi/vania-out.txt',
    #            u'text_multi/vania-analyzed.xml')
##    parsed2xml(u'text_multi/rodarummet.xml', u'text_multi/rodarummet-out.txt',
##               u'text_multi/rodarummet-analyzed.xml')
##    parsed2xml(u'text_multi/chajka.xml', u'text_multi/chajka-out.txt',
##               u'text_multi/chajka-analyzed.xml')
    # parsed2xml(u'text_multi/sad.xml', u'text_multi/sad-out.txt',
    #            u'text_multi/sad-analyzed.xml')
    # json2xml(u'texts/kompromiss.xml', u'texts/kompromiss-analyzed.json', u'texts/kompromiss-analyzed.xml')
    # for fname in os.listdir(u'texts'):
    #     if not fname.endswith(u'.xml') or fname.endswith(u'analyzed.xml'):
    #         continue
    #     fname = u'texts/' + fname
    #     print fname
    #     json2xml(fname, fname[:-4] + u'-analyzed.json', fname[:-4] + u'-analyzed.xml')
