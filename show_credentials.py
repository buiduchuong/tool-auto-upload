# -*- coding: utf-8 -*-
from __future__ import annotations

from web_panel import ensure_gpt_api_token, ensure_web_auth


def main() -> None:
    username, password = ensure_web_auth()
    token = ensure_gpt_api_token()
    print("MSTAR WEB PANEL CREDENTIALS")
    print(f"Web panel username: {username}")
    print(f"Web panel password: {password}")
    print()
    print("CHATGPT API")
    print(f"Bearer token: {token}")
    print()
    print("Hay giu kin cac thong tin nay. Doi mat khau/token trong panel_settings.json neu bi lo.")


if __name__ == "__main__":
    main()
