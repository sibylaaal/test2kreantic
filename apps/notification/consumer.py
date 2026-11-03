def handle_event(event: dict) -> dict:
    """Placeholder consumer for telecom events."""
    print(f"Received event: {event.get('event_name')} from {event.get('source')}")
    return {"status": "processed", "event": event.get("event_name")}
