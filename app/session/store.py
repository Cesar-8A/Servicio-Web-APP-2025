from uuid import uuid4
from flask import session

# In-memory store: { user_session_id: user_data_dict }
# Lives at module level so it persists for the lifetime of the server process.
SERVER_SIDE_SESSION_STORE: dict = {}


def get_user_data() -> dict:
    """
    Retrieve (or create) the data dictionary for the current user session.

    Flask's signed cookie holds only a lightweight session ID.
    The actual volumetric data lives here in SERVER_SIDE_SESSION_STORE,
    keyed by that ID, to keep cookie size small and data server-side.
    """
    if 'user_session_id' not in session:
        user_id = str(uuid4())
        session['user_session_id'] = user_id
        SERVER_SIDE_SESSION_STORE[user_id] = {}
    user_id = session['user_session_id']
    return SERVER_SIDE_SESSION_STORE.setdefault(user_id, {})
