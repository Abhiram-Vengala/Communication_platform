import logging
import time

from django.core.management.base import BaseCommand

from messaging.services import process_due

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sends queued/scheduled messages and retries temporary failures. Run alongside the web server."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process due messages once and exit.")
        parser.add_argument("--interval", type=float, default=2.0, help="Seconds between polls.")

    def handle(self, *args, **options):
        self.stdout.write("Worker started. Ctrl+C to stop.")
        try:
            while True:
                try:
                    count = process_due()
                    if count:
                        self.stdout.write(f"Processed {count} message(s).")
                except Exception:
                    logger.exception("Worker tick failed; continuing.")
                if options["once"]:
                    break
                time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write("Worker stopped.")
