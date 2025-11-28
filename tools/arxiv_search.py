import os
from typing import List, Dict, Any
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

class ArxivSearcher:
    """
    Arxiv 学术搜索工具
    - 用于 Analyst Agent 发现一手学术资料
    - 免费，无需 API Key
    """

    BASE_URL = "http://export.arxiv.org/api/query"

    def search(self, query: str, max_results: int = 5, category: str = "") -> List[Dict[str, Any]]:
        """
        搜索 Arxiv 论文

        Args:
            query: 搜索关键词（如: "Retrieval Augmented Generation"）
            max_results: 返回结果数量
            category: 限定类别（如: cs.AI, cs.CL, 留空则全领域）

        Returns:
            List of papers with: title, authors, summary, url, published, category
        """

        # 构建查询参数
        search_query = f"all:{query}"
        if category:
            search_query = f"cat:{category} AND {search_query}"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",  # relevance | lastUpdatedDate | submittedDate
            "sortOrder": "descending"
        }

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        try:
            # 发起请求
            with urllib.request.urlopen(url, timeout=10) as response:
                xml_data = response.read().decode('utf-8')

            # 解析 XML
            root = ET.fromstring(xml_data)
            namespace = {'atom': 'http://www.w3.org/2005/Atom',
                        'arxiv': 'http://arxiv.org/schemas/atom'}

            results = []
            for entry in root.findall('atom:entry', namespace):
                # 提取作者
                authors = [author.find('atom:name', namespace).text
                          for author in entry.findall('atom:author', namespace)]

                # 提取分类
                categories = [cat.get('term')
                            for cat in entry.findall('atom:category', namespace)]

                # 提取发布时间
                published = entry.find('atom:published', namespace)
                published_date = published.text if published is not None else ""

                # 提取更新时间
                updated = entry.find('atom:updated', namespace)
                updated_date = updated.text if updated is not None else ""

                # 提取 PDF 链接
                pdf_link = ""
                for link in entry.findall('atom:link', namespace):
                    if link.get('title') == 'pdf':
                        pdf_link = link.get('href')
                        break

                # 提取摘要和标题
                title_elem = entry.find('atom:title', namespace)
                summary_elem = entry.find('atom:summary', namespace)
                id_elem = entry.find('atom:id', namespace)

                paper = {
                    "title": title_elem.text.strip() if title_elem is not None else "",
                    "authors": authors,
                    "summary": summary_elem.text.strip() if summary_elem is not None else "",
                    "url": id_elem.text if id_elem is not None else "",
                    "pdf_url": pdf_link,
                    "published": published_date,
                    "updated": updated_date,
                    "categories": categories,
                    "source": "arxiv"
                }

                results.append(paper)

            return results

        except Exception as e:
            print(f"⚠️ Arxiv Search Failed: {e}")
            return []

    def search_by_category_and_date(
        self,
        category: str,
        start_date: str = "",
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        按分类和日期搜索最新论文

        Args:
            category: 分类代码（如: cs.AI, cs.LG）
            start_date: 起始日期（YYYYMMDD格式，留空则不限）
            max_results: 返回结果数量

        Returns:
            List of recent papers in the category
        """

        # 构建查询
        search_query = f"cat:{category}"
        if start_date:
            search_query += f" AND submittedDate:[{start_date} TO *]"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                xml_data = response.read().decode('utf-8')

            root = ET.fromstring(xml_data)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}

            results = []
            for entry in root.findall('atom:entry', namespace):
                authors = [author.find('atom:name', namespace).text
                          for author in entry.findall('atom:author', namespace)]

                title_elem = entry.find('atom:title', namespace)
                summary_elem = entry.find('atom:summary', namespace)
                id_elem = entry.find('atom:id', namespace)
                published_elem = entry.find('atom:published', namespace)

                paper = {
                    "title": title_elem.text.strip() if title_elem is not None else "",
                    "authors": authors,
                    "summary": summary_elem.text.strip() if summary_elem is not None else "",
                    "url": id_elem.text if id_elem is not None else "",
                    "published": published_elem.text if published_elem is not None else "",
                    "source": "arxiv"
                }

                results.append(paper)

            return results

        except Exception as e:
            print(f"⚠️ Arxiv Category Search Failed: {e}")
            return []


# 便捷函数
def search_arxiv(query: str, max_results: int = 5, category: str = "") -> List[Dict[str, Any]]:
    """便捷搜索函数"""
    searcher = ArxivSearcher()
    return searcher.search(query, max_results, category)


if __name__ == "__main__":
    # 测试代码
    print("=== Testing Arxiv Search ===\n")

    # 测试 1: 搜索 RAG 相关论文
    print("Test 1: Searching for 'Retrieval Augmented Generation'")
    results = search_arxiv("Retrieval Augmented Generation", max_results=3, category="cs.CL")

    for i, paper in enumerate(results, 1):
        print(f"\n[{i}] {paper['title']}")
        print(f"    Authors: {', '.join(paper['authors'][:3])}")
        print(f"    Published: {paper['published'][:10]}")
        print(f"    URL: {paper['url']}")
        print(f"    Summary: {paper['summary'][:150]}...")

    print("\n" + "="*50)
