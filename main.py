"""
This add-on will monitor a website for documents and upload them to your DocumentCloud account
"""


import json
import os
import urllib.parse as urlparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from documentcloud.addon import CronAddOn
from documentcloud.constants import BULK_LIMIT
from documentcloud.toolbox import grouper

# the site to scrape
SITE = "https://www.ssa.gov/foia/readingroom.html"
# the project to upload documents into
PROJECT = 207338
# keywords to generate additional notifications for
KEYWORDS = ["court", "foia"]
# file types to scrape
FILETYPES = (".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt")


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
        with open("data.json", "w") as file_:
            json.dump(data, file_, indent=2, sort_keys=True)

    def scrape(self):
        """Scrape the site for new documents"""
        resp = requests.get(SITE)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []
        data = self.load_data()
        now = datetime.now().isoformat()
        for link in soup.find_all("a"):
            href = link.get("href")
            if href.endswith(FILETYPES):
                doc = urlparse.urljoin(resp.url, href)
                # track when we first and last saw this document
                # on this page
                if doc not in data:
                    # only download if haven't seen before
                    docs.append(doc)
                    data[doc] = {"first_seen": now}
                data[doc]["last_seen"] = now

        print(f"Found {len(docs)} new documents")
        self.send_mail(f"Found {len(docs)} new documents from {SITE}", "\n".join(docs))
        for doc_group in grouper(docs, BULK_LIMIT):
            # filter out None's from grouper padding
            doc_group = [d for d in doc_group if d]
            doc_group = [
                {
                    "file_url": url_fix(d),
                    "source": f"Scraped from {SITE}",
                    "title": title(d),
                    "projects": [PROJECT],
                }
                for d in doc_group
            ]
            # do a bulk upload
            resp = self.client.post("documents/", json=doc_group)

        self.store_data(data)

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
                self.send_mail(
                    f"New documents found for: {keyword} from {SITE}",
                    "\n".join(message),
                )

    def main(self):
        self.scrape()
        self.alert()


if __name__ == "__main__":
    Scraper().main()
