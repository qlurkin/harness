"""Log in to GitHub Copilot: harness connect_copilot"""

from harness.auth import AUTH_PATH
from harness.copilot_auth import get_session, login


def main() -> None:
    login()
    session = get_session()
    print(f"Logged in. Token saved in {AUTH_PATH}. API: {session['api_base']}")


if __name__ == "__main__":
    main()
