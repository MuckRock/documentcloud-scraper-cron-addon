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

SITE = "https://www.ssa.gov/foia/readingroom.html"
PROJECT = 207338


def title(url):
    parsed_url = urlparse.urlparse(url)
    basename = os.path.basename(parsed_url.path)
    root, _ext = os.path.splitext(basename)
    return root


# https://stackoverflow.com/questions/33049729/how-to-handle-links-containing-space-between-them-in-python
def url_fix(s):
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
    path = urlparse.quote(path, "/%")
    qs = urlparse.quote_plus(qs, ":&=")
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))


class Scraper(CronAddOn):

    def load_data(self):
        try:
            with open("data.json", "r") as file_:
                return json.load(file_)
        except FileNotFoundError:
            return {}

    def store_data(self, data):
        with open("data.json", "w") as file_:
            json.dump(data, file_, indent=2, sort_keys=True)

    def main(self):
        resp = requests.get(SITE)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []
        data = self.load_data()
        now = datetime.now().isoformat()
        for link in soup.find_all("a"):
            href = link.get("href")
            if href.endswith(".pdf"):
                doc = urlparse.urljoin(resp.url, href)
                # track when we first and last saw this document
                # on this page
                if doc not in data:
                    # only download if haven't seen before
                    docs.append(doc)
                    data[doc] = {"first_seen": now}
                data[doc]["last_seen"] = now

        print(f"Found {len(docs)} new documents")
        for doc_group in grouper(docs, BULK_LIMIT):
            doc_group = [
                d for d in doc_group if d
            ]  # filter out None's from grouper padding
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


if __name__ == "__main__":
    Scraper().main()
