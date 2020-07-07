import codecs
import os
import re
import json
from lxml import etree
from xml.sax.saxutils import escape, unescape

reWords = re.compile(u'((?:<[^<>\r\n]+>)*)(?:^|\\b)([^<>]+?)(?:\\b|$)((?:</[^<>\r\n]+>)*)', flags=re.U | re.DOTALL)
reWordsSimple = re.compile(u'(?:^|\\b)[^<>]+?(?:\\b|$)', flags=re.U | re.DOTALL)


def xml2json(fnameIn, fnameOut):
    xmlTree = etree.parse(fnameIn)
    jsonText = {u'paragraphs': [{u'sentences': []}]}
    sentences = xmlTree.xpath(u'/html/body/para/se[@lang="et"] | /html/body/para/se[@lang="ee"]')
    for sentence in sentences:
        jsonText[u'paragraphs'][0][u'sentences'].append({u'words': []})
        text = sentence.xpath(u'string()')
        words = reWordsSimple.findall(text)
        for word in words:
            word = word.strip()
            if len(word) <= 0:
                continue
            jsonText[u'paragraphs'][0][u'sentences'][-1][u'words'].append({u'text': word})
    fOut = codecs.open(fnameOut, 'w', 'utf-8')
    fOut.write(json.dumps(jsonText, ensure_ascii=False, indent=4))
    fOut.close()


def json2xml(fnameInXml, fnameInJson, fnameOut):
    fXml = codecs.open(fnameInXml, 'r', 'utf-8-sig')
    fJson = codecs.open(fnameInJson, 'r', 'utf-8')
    jsonSentences = json.loads(fJson.read())[u'paragraphs'][0][u'sentences']
    fJson.close()
    fOut = codecs.open(fnameOut, 'w', 'utf-8')
    paraId = -1
    iSe = -1
    iWord = 0
    lang = u'ru'
    for line in fXml:
        if u'lang="ru' in line:
            lang = u'ru'
        if u'lang="e' in line:
            lang = u'ee'
        m = re.search(u'([ \t]*<se +lang="e[^<>]*>|^)([^\r\n]*?)'
                      u'(</se>[ \t]*\r?\n|\r?\n)', line, flags=re.U)
        if m is None or lang == u'ru' or u'<para' in m.group(2) or u'</para' in m.group(2):
            mPara = re.search(u'^([ \t]*<para id=")([^"]+)(.*)', line, flags=re.U)
            if mPara is not None:
                paraId += 1
                fOut.write(mPara.group(1) + str(paraId) + mPara.group(3))
            else:
                fOut.write(line)
            continue
        lineOut = m.group(1)
        if u'<se' in line:
            iSe += 1
            if re.search(u'\\w', m.group(2), flags=re.U) is not None:
                while iSe < len(jsonSentences) and\
                      len(jsonSentences[iSe][u'words']) <= 0:
                    iSe += 1
            iWord = 0
        words = reWords.findall(m.group(2).replace(u'&quot;', u'"').replace(u'&apos', u"'"))
        for word in words:
            wordStripped = word[1].strip()
            if len(wordStripped) <= 0 or iWord >= len(jsonSentences[iSe][u'words']) or\
               (iWord == 0 and jsonSentences[iSe][u'words'][iWord][u'text'] != wordStripped):
                lineOut += word[0] + word[1] + word[2]
                continue
            # print word, jsonSentences[iSe][u'words'][iWord]
            anas = jsonSentences[iSe][u'words'][iWord][u'analysis']
            iWord += 1
            if len(anas) <= 0:
                if re.search(u'\\w', word[1], flags=re.U) is not None:
                    lineOut += word[0] + u'<w>' + escape(word[1]) + u'</w>' + word[2]
                else:
                    lineOut += word[0] + escape(word[1]) + word[2]
                continue
            lineOut += word[0] + u'<w>'
            for ana in anas:
                lineOut += u'<ana lex="' + ana[u'root'] + u'" gr="' +\
                           ana[u'partofspeech'] + u',' + ana[u'form'].replace(u' ', u',') +\
                           u'" />'
            lineOut += escape(word[1]).strip() + u'</w>' + word[2]
        lineOut = lineOut.replace(u'," />', u'" />')
        lineOut += m.group(3)
        fOut.write(lineOut)
    fOut.close()


if __name__ == u'__main__':
    #xml2json(u'texts/keisrihull.xml', u'texts/keisrihull.json')
    json2xml(u'texts/keisrihull.xml', u'texts/keisrihull-analyzed.json', u'texts/keisrihull-analyzed.xml')
    #json2xml(u'texts/kompromiss.xml', u'texts/kompromiss-analyzed.json', u'texts/kompromiss-analyzed.xml')
    # for fname in os.listdir(u'texts'):
    #     if not fname.endswith(u'.xml') or fname.endswith(u'analyzed.xml'):
    #         continue
    #     fname = u'texts/' + fname
    #     print fname
    #     json2xml(fname, fname[:-4] + u'-analyzed.json', fname[:-4] + u'-analyzed.xml')
