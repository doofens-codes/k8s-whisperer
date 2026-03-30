import threading

class SyncState:
    def __init__(self):
        self.approval_event = threading.Event()
        self.approval_decision = False
        
    def reset(self):
        """Reset the state before a new HITL cycle."""
        self.approval_decision = False
        self.approval_event.clear()

# Global singleton
state = SyncState()
