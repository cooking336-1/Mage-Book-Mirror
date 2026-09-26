"""Celery Asynchronous Task Application Configuration.

Initializes the distributed worker runtime for Mage Books SAAS:
- GRA E-VAT asynchronous invoice clearance
- Periodic ledger reconciliation
- Audit PBC package export compression
"""

import os

from celery import Celery

# Set default Django settings module for 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("magebooks")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task for verifying worker health."""
    print(f"Request: {self.request!r}")
