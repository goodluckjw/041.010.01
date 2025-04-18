import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import re

OC = "chetera"
BASE = "http://www.law.go.kr"

def get_law_list_from_api(query):
    encoded_query = quote(query.split("&")[0].split(",")[0].split("-")[0].strip())
    url = f"{BASE}/DRF/lawSearch.do?OC={OC}&target=law&type=XML&display=100&search=2&knd=A0002&query={encoded_query}"
    res = requests.get(url, timeout=10)
    res.encoding = 'utf-8'
    laws = []
    if res.status_code == 200:
        root = ET.fromstring(res.content)
        for law in root.findall("law"):
            laws.append({
                "법령명": law.findtext("법령명한글", "").strip(),
                "MST": law.findtext("법령일련번호", ""),
                "URL": BASE + law.findtext("법령상세링크", "")
            })
    return laws

def get_law_text_by_mst(mst):
    url = f"{BASE}/DRF/lawService.do?OC={OC}&target=law&MST={mst}&type=XML"
    res = requests.get(url, timeout=10)
    res.encoding = 'utf-8'
    return res.content if res.status_code == 200 else None

def clean(text):
    return re.sub(r"\s+", "", text or "")

def highlight(text, terms):
    if not text:
        return ""
    for term in terms:
        text = text.replace(term, f"<span style='color:red'>{term}</span>")
    return text

def logic_match(text, query):
    text = clean(text)
    include = [t.strip() for t in re.split(r"[,&\-]", query) if not t.startswith("-") and t.strip() in text]
    exclude = [t[1:].strip() for t in query.split() if t.startswith("-") and t[1:] in text]
    return all(word in text for word in include) and not any(word in text for word in exclude)

def get_highlighted_articles(mst, query):
    xml_data = get_law_text_by_mst(mst)
    if not xml_data:
        return "⚠️ 본문을 불러올 수 없습니다."

    tree = ET.fromstring(xml_data)
    articles = tree.findall(".//조문단위")
    terms = [t.strip() for t in re.split(r"[,&\-]", query) if t.strip()]
    results = []

    for article in articles:
        조번호 = article.findtext("조문번호", "").strip()
        조제목 = article.findtext("조문제목", "") or ""
        조내용 = article.findtext("조문내용", "") or ""
        항들 = article.findall("항")

        조출력 = logic_match(조제목 + 조내용, query)
        항출력 = []

        for 항 in 항들:
            항번호 = 항.findtext("항번호", "").strip()
            항내용 = 항.findtext("항내용", "") or ""
            호출력 = []

            if logic_match(항내용, query):
                조출력 = True

            for 호 in 항.findall("호"):
                호내용 = 호.findtext("호내용", "") or ""
                if logic_match(호내용, query):
                    조출력 = True
                    호출력.append(f"{highlight(호내용, terms)}")
                for 목 in 호.findall("목"):
                    목내용 = 목.findtext("목내용", "") or ""
                    if logic_match(목내용, query):
                        조출력 = True
                        호출력.append(f"&nbsp;&nbsp;{highlight(목내용, terms)}")

            for 목 in 항.findall("목"):
                목내용 = 목.findtext("목내용", "") or ""
                if logic_match(목내용, query):
                    조출력 = True
                    호출력.append(f"&nbsp;&nbsp;{highlight(목내용, terms)}")

            if logic_match(항내용, query) or 호출력:
                항출력.append(f"ⓞ{항번호} {highlight(항내용, terms)}<br>" + "<br>".join(호출력))

        if 조출력 or 항출력:
            output = f"제{조번호}조({조제목})"
            if not 항들:
                output += f" {highlight(조내용, terms)}"
            else:
                output += "<br>" + "<br>".join(항출력)
            results.append(output)

    return "<br><br>".join(results) if results else "🔍 해당 검색어를 포함한 조문이 없습니다."
