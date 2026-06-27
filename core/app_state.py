IDLE = "idle"
SYNCING = "syncing"
ERROR = "error"
SETUP = "setup"
CONNECTING = "connecting"


class AppState:
    def __init__(self):
        self.state = IDLE
        self.error_message = ""
        self.last_sync_count = 0

    def transition(self, new_state: str, error_message: str = "") -> None:
        self.state = new_state
        self.error_message = error_message

    @property
    def is_syncing(self) -> bool:
        return self.state == SYNCING

    @property
    def has_error(self) -> bool:
        return self.state == ERROR
