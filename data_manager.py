import copy
import json
import os
import tempfile
from threading import Lock
from typing import Any


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

PLAYERS_FILE = os.path.join(DATA_DIR, "players.json")
TEAMS_FILE = os.path.join(DATA_DIR, "teams.json")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")
ACTIVE_MATCHES_FILE = os.path.join(DATA_DIR, "active_matches.json")
DISPUTED_FILE = os.path.join(DATA_DIR, "disputed.json")
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")


DEFAULT_PLAYERS = {}
DEFAULT_TEAMS = {}
DEFAULT_QUEUE = {
    "1v1": [],
    "2v2": [],
    "3v3": [],
    "rankup": {
        "1v1": [],
        "2v2": [],
        "3v3": []
    }
}
DEFAULT_ACTIVE_MATCHES = {}
DEFAULT_DISPUTED = {}
DEFAULT_MATCHES = {}

_FILE_LOCKS: dict[str, Lock] = {}
_FILE_LOCKS_GUARD = Lock()


def get_file_lock(filename: str) -> Lock:
    with _FILE_LOCKS_GUARD:
        if filename not in _FILE_LOCKS:
            _FILE_LOCKS[filename] = Lock()
        return _FILE_LOCKS[filename]


def ensure_data_folder() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def ensure_file_exists(filename: str, default_data: Any) -> None:
    ensure_data_folder()

    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)


def load_json(filename: str, default_data: Any) -> Any:
    ensure_file_exists(filename, default_data)
    lock = get_file_lock(filename)

    with lock:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            save_json(filename, default_data)
            return copy.deepcopy(default_data)


def save_json(filename: str, data: Any) -> None:
    ensure_data_folder()
    lock = get_file_lock(filename)

    with lock:
        fd, temp_path = tempfile.mkstemp(
            dir=DATA_DIR,
            prefix=os.path.basename(filename) + ".",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            os.replace(temp_path, filename)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


def initialize_data_files() -> None:
    ensure_file_exists(PLAYERS_FILE, DEFAULT_PLAYERS)
    ensure_file_exists(TEAMS_FILE, DEFAULT_TEAMS)
    ensure_file_exists(QUEUE_FILE, DEFAULT_QUEUE)
    ensure_file_exists(ACTIVE_MATCHES_FILE, DEFAULT_ACTIVE_MATCHES)
    ensure_file_exists(DISPUTED_FILE, DEFAULT_DISPUTED)
    ensure_file_exists(MATCHES_FILE, DEFAULT_MATCHES)
