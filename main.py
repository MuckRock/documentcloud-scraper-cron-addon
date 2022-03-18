"""
This is an example of a DocumentCloud Cron Add-On

It runs periodically based on a schedule, rather than being triggered manually.

This one will alert of new documents matching a given search query
"""

from datetime import datetime

from documentcloud.addon import CronAddOn

QUERY = "+user:mitchell-kotler-20080"


class Alert(CronAddOn):
    def main(self):
        documents = self.client.documents.search(f"{QUERY} created_at:[NOW-1HOUR TO *]")
        documents = list(documents)
        if documents:
            message = [f"Documents found at {datetime.now()}"]
            message.extend([f"{d.title} - {d.canonical_url}" for d in documents])
            self.send_mail(f"New documents found for: {QUERY}", "\n".join(message))


if __name__ == "__main__":
    Alert().main()
