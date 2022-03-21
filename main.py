"""
This add-on will monitor a website for documents and upload them to your DocumentCloud account
"""


import cgi
import json
import os
import urllib.parse as urlparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from documentcloud.addon import CronAddOn
from documentcloud.constants import BULK_LIMIT
from documentcloud.toolbox import grouper

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK")

# the site to scrape
SITE = "https://www.ssa.gov/foia/readingroom.html"
# the project to upload documents into
PROJECT = 207338
# keywords to generate additional notifications for
KEYWORDS = ["court", "foia"]
# file types to scrape
FILETYPES = (".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt")
# How many links to follow while crawling
CRAWL_DEPTH = 1
# Do not upload documents or store results
DRY_RUN = False


def title(url):
    """Get the base name of the file to use as a title"""
    parsed_url = urlparse.urlparse(url)
    basename = os.path.basename(parsed_url.path)
    root, _ext = os.path.splitext(basename)
    return root


# https://stackoverflow.com/questions/33049729/how-to-handle-links-containing-space-between-them-in-python
def url_fix(s):
    """Fixes quoting of characters in file names to use with requests"""
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
    path = urlparse.quote(path, "/%")
    qs = urlparse.quote_plus(qs, ":&=")
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))


class Scraper(CronAddOn):
    def load_data(self):
        """Load data from the file checked into the repository"""
        try:
            with open("data.json", "r") as file_:
                return json.load(file_)
        except FileNotFoundError:
            return {}

    def store_data(self, data):
        """Store data to be checked in to the repository"""
        if DRY_RUN:
            return
        with open("data.json", "w") as file_:
            json.dump(data, file_, indent=2, sort_keys=True)

    def check_crawl(self, url):
        # check if it is from the same site
        scheme, netloc, path, qs, anchor = urlparse.urlsplit(url)
        if netloc != self.base_netloc:
            return False
        # do not crawl the same site more than once
        if url in self.seen:
            return False
        self.seen.add(url)
        # do a head request to check for HTML
        resp = requests.head(url, allow_redirects=True)
        content = cgi.parse_header(resp.headers["Content-Type"])[0]
        return content == "text/html"

    def scrape(self, site=SITE, depth=0):
        """Scrape the site for new documents"""
        print(f"Scraping {site} (depth {depth})")
        resp = requests.get(site)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []
        sites = []
        now = datetime.now().isoformat()
        for link in soup.find_all("a"):
            href = link.get("href")
            if href is None:
                continue
            full_href = urlparse.urljoin(resp.url, href)
            if href.endswith(FILETYPES):
                # track when we first and last saw this document
                # on this page
                if full_href not in self.data:
                    # only download if haven't seen before
                    docs.append(full_href)
                    self.data[full_href] = {"first_seen": now}
                self.data[full_href]["last_seen"] = now
            elif depth < CRAWL_DEPTH:
                # if not a document, check to see if we should crawl
                if self.check_crawl(full_href):
                    sites.append(full_href)

        self.new_docs[site] = docs
        for doc_group in grouper(docs, BULK_LIMIT):
            # filter out None's from grouper padding
            doc_group = [d for d in doc_group if d]
            doc_group = [
                {
                    "file_url": url_fix(d),
                    "source": f"Scraped from {site}",
                    "title": title(d),
                    "projects": [PROJECT],
                }
                for d in doc_group
            ]
            # do a bulk upload
            if not DRY_RUN:
                resp = self.client.post("documents/", json=doc_group)

        # recurse on sites we want to crawl
        for site_ in sites:
            self.scrape(site_, depth=depth+1)

    def send_notification(self, subject, message):
        """Send notifications via slack and email"""
        self.send_mail(subject, message)
        if SLACK_WEBHOOK:
            requests.post(SLACK_WEBHOOK, json={"text": f"{subject}\n\n{message}"})

    def send_scrape_message(self):
        msg = []
        for site, docs in self.new_docs.items():
            if docs:
                msg.append(f"\n\nFound {len(docs)} new documents from {site}\n")
                msg.extend(docs)
        if msg:
            self.send_notification(
                f"Found new documents from {SITE}", "\n".join(msg)
            )

    def alert(self):
        """Run queries for the keywords to generate additional alerts"""
        for keyword in KEYWORDS:
            query = f"+project:{PROJECT} {keyword} created_at:[NOW-1HOUR TO *]"
            documents = self.client.documents.search(query)
            documents = list(documents)
            if documents:
                message = [
                    f"Documents containing {keyword} found at {datetime.now()} "
                    f"from {SITE}"
                ]
                message.extend([f"{d.title} - {d.canonical_url}" for d in documents])
                self.send_notification(
                    f"New documents found for: {keyword} from {SITE}",
                    "\n".join(message),
                )

    def main(self):
        # grab the base of the URL to stay on site during crawling
        _scheme, netloc, _path, _qs, _anchor = urlparse.urlsplit(SITE)
        self.base_netloc = netloc
        self.seen = set()
        self.new_docs = {}

        self.data = self.load_data()
        self.scrape()
        self.store_data(self.data)
        self.send_scrape_message()

        self.alert()


if __name__ == "__main__":
    Scraper().main()
