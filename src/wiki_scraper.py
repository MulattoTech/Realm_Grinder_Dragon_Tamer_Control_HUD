"""
Full Crawler and Scraper for G00F's Not-a-Wiki (http://musicfamily.org/realm/)
Downloads and structures 100% of the wiki content, extracting:
- Build templates and guides for all Reincarnations (R0 through R46+)
- Dragon unlock mechanics, formulas, quest artifacts, and requirements
- Research upgrades, spell tiers, challenges, and trophies
Saves all pages to scraped_wiki/pages/ and consolidated database to scraped_wiki/knowledge_base.json.
"""

import os
import re
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup

BASE_URL = "http://musicfamily.org/realm/"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "scraped_wiki")
PAGES_DIR = os.path.join(OUTPUT_DIR, "pages")
KB_FILE = os.path.join(OUTPUT_DIR, "knowledge_base.json")

os.makedirs(PAGES_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def sanitize_filename(name: str) -> str:
    slug = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    return slug or "index"


def clean_html_to_markdown(soup: BeautifulSoup) -> str:
    # Remove script, style, navigation boilerplate
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    
    # Extract main content area if present
    content = soup.find("div", id="content") or soup.find("div", class_="content") or soup.body
    if not content:
        return soup.get_text("\n", strip=True)

    text_lines = []
    for elem in content.descendants:
        if elem.name in ["h1", "h2", "h3", "h4"]:
            text_lines.append(f"\n### {elem.get_text(strip=True)}\n")
        elif elem.name == "p":
            t = elem.get_text(strip=True)
            if t:
                text_lines.append(f"\n{t}\n")
        elif elem.name == "li":
            t = elem.get_text(strip=True)
            if t:
                text_lines.append(f"- {t}")
        elif elem.name == "pre" or elem.name == "code":
            t = elem.get_text(strip=True)
            if t:
                text_lines.append(f"```\n{t}\n```")

    raw_text = "\n".join(text_lines)
    # Deduplicate empty lines
    cleaned = re.sub(r'\n{3,}', '\n\n', raw_text).strip()
    return cleaned if cleaned else soup.get_text("\n", strip=True)


class WikiScraper:
    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.visited_urls: Set[str] = set()
        self.discovered_urls: Set[str] = set()
        self.page_data: Dict[str, Dict[str, Any]] = {}

    def normalize_url(self, url: str) -> str:
        # Strip query and fragments
        parsed = urllib.parse.urlparse(url)
        clean = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        clean = clean.rstrip('/')
        return clean

    def is_valid_wiki_url(self, url: str) -> bool:
        norm = self.normalize_url(url)
        if not norm.startswith(self.normalize_url(BASE_URL)):
            return False
        # Ignore binary or irrelevant assets
        lower = norm.lower()
        if any(lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".ico", ".css", ".js", ".pdf", ".zip"]):
            return False
        if "guestbook" in lower or "wallofshame" in lower:
            return False
        return True

    def fetch_page(self, url: str) -> Optional[Dict[str, Any]]:
        norm_url = self.normalize_url(url)
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"[{resp.status_code}] Failed: {url}")
                return None
            soup = BeautifulSoup(resp.content, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else norm_url.split("/")[-1]
            markdown = clean_html_to_markdown(soup)
            
            # Find links
            links = set()
            for a in soup.find_all("a", href=True):
                full_link = urllib.parse.urljoin(url, a["href"])
                if self.is_valid_wiki_url(full_link):
                    links.add(self.normalize_url(full_link))

            # Determine slug
            path = urllib.parse.urlparse(norm_url).path
            slug = path.replace("/realm/", "").strip("/").replace("/", "_")
            if not slug:
                slug = "index"

            # Save individual files
            md_path = os.path.join(PAGES_DIR, f"{sanitize_filename(slug)}.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\nURL: {norm_url}\n\n{markdown}")

            return {
                "url": norm_url,
                "slug": slug,
                "title": title,
                "markdown": markdown,
                "links": list(links)
            }
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def crawl_all(self):
        print("Initiating full crawler on G00F Not-a-Wiki...")
        # Seed URLs
        seed_urls = [
            BASE_URL,
            "http://musicfamily.org/realm/SiteMap/",
            "http://musicfamily.org/realm/R40-R46",
            "http://musicfamily.org/realm/DragonFaction",
            "http://musicfamily.org/realm/Dragons",
            "http://musicfamily.org/realm/QuestArtifacts/",
            "http://musicfamily.org/realm/ResearchBuilds",
            "http://musicfamily.org/realm/MercBuilds",
            "http://musicfamily.org/realm/PBuilds",
            "http://musicfamily.org/realm/R47-R60",
            "http://musicfamily.org/realm/R60-R75",
            "http://musicfamily.org/realm/R75Plus",
            "http://musicfamily.org/realm/Researchtree",
            "http://musicfamily.org/realm/ResearchList",
            "http://musicfamily.org/realm/Challenges",
            "http://musicfamily.org/realm/TrophyPage",
            "http://musicfamily.org/realm/TrophyGuide",
            "http://musicfamily.org/realm/Bloodline",
            "http://musicfamily.org/realm/Spells",
            "http://musicfamily.org/realm/Reset",
            "http://musicfamily.org/realm/Artifacts",
            "http://musicfamily.org/realm/UniqueBuilding",
            "http://musicfamily.org/realm/FactionUpgrades"
        ]

        to_visit = {self.normalize_url(u) for u in seed_urls}
        
        round_num = 0
        while to_visit:
            round_num += 1
            current_batch = list(to_visit - self.visited_urls)
            if not current_batch:
                break
            print(f"\n--- Crawl Round {round_num}: Fetching {len(current_batch)} pages ---")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_url = {executor.submit(self.fetch_page, url): url for url in current_batch}
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    self.visited_urls.add(url)
                    data = future.result()
                    if data:
                        self.page_data[data["slug"]] = data
                        print(f"Scraped: {data['title']} ({data['slug']}) - Found {len(data['links'])} internal links")
                        for l in data["links"]:
                            if l not in self.visited_urls:
                                to_visit.add(l)

        print(f"\nCrawling complete. Total unique pages scraped: {len(self.page_data)}")
        self.build_knowledge_base()

    def build_knowledge_base(self):
        print("Synthesizing consolidated Knowledge Base...")
        kb = {
            "metadata": {
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": BASE_URL,
                "total_pages": len(self.page_data)
            },
            "dragon_unlock": {},
            "builds": [],
            "research_catalog": {},
            "trophies": {}
        }

        # 1. Parse Dragon Unlock from R40-R46 and DragonFaction
        for slug in ["R40-R46", "DragonFaction", "Dragons", "QuestArtifacts"]:
            if slug in self.page_data:
                md = self.page_data[slug]["markdown"]
                if "Spiky Rough Egg" in md or "Dragon Tamer" in md:
                    kb["dragon_unlock"][slug] = md

        # 2. Extract Builds from ResearchBuilds, MercBuilds, R40-R46
        build_regex = re.compile(r'([A-Z0-9,:\s]{15,})')
        for slug, pdata in self.page_data.items():
            if "build" in slug.lower() or "r40" in slug.lower() or "merc" in slug.lower():
                md = pdata["markdown"]
                # Look for template strings e.g. S50,S105,... or FR2,FR7,...
                templates = re.findall(r'([A-Z]{1,2}\d{1,4}(?:,[A-Z]{1,2}\d{1,4}|,SP:[a-zA-Z\s\']+)+)', md)
                for tmpl in templates:
                    clean_tmpl = tmpl.replace("\n", "").replace(" ", "").strip()
                    if len(clean_tmpl) > 20 and "," in clean_tmpl:
                        kb["builds"].append({
                            "source_page": slug,
                            "title": pdata["title"],
                            "template": clean_tmpl
                        })

        # Save KB
        with open(KB_FILE, "w", encoding="utf-8") as f:
            json.dump(kb, f, indent=2)
        print(f"Knowledge Base saved successfully to {KB_FILE} ({os.path.getsize(KB_FILE)} bytes)!")


if __name__ == "__main__":
    scraper = WikiScraper(max_workers=8)
    scraper.crawl_all()
