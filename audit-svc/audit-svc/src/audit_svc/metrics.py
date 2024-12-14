from prometheus_client import Counter

EVENTS_INSERTED = Counter(
    "events_inserted", "Number of events inserted", ("application",)
)
