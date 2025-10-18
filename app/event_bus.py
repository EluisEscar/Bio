from collections import defaultdict

class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)

    def subscribe(self, event_name, callback):
        self._subs[event_name].append(callback)

    def publish(self, event_name, **kwargs):
        for cb in list(self._subs.get(event_name, [])):
            cb(**kwargs)

# Singleton simple
bus = EventBus()
