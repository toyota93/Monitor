import requests
import time
import json
import os
from datetime import datetime, timezone

# =========================================================
# CONFIG
# =========================================================

MM2_WEBHOOK = "https://discord.com/api/webhooks/1544142494692802660/VlCsdLJOxAvKqlPQ0DJlBMHj5M6wVmJryXC_3Ns8rS5hOqq5ccMvUnsomEsUk1d6SCJY"
NIKILIS_WEBHOOK = "https://discord.com/api/webhooks/1544142698892632074/2kFsS_-Xbm8I4PcZwxMTvF4LlaP1kAA6ya8wo8zOb6g8nFFZ31UFM7-pM3zEUR47_J9I"
TESTING_WEBHOOK = "https://discord.com/api/webhooks/1544142799098880130/PfjTtdvwZ6bkZ7F6H5DvrQdilklqRyCBdfZdWtyVPbpeBQ9iPh66nE_9KPjwKn4Rytpm"

CHECK_INTERVAL = 30

# Nikilis
NIKILIS_USER_ID = 1848960

# Murder Mystery 2
MM2_PLACE_ID = 142823291
MM2_UNIVERSE_ID = 66654135

# MM2 Testing Server
TESTING_PLACE_ID = 188331334

STATE_FILE = "mm2_monitor_state.json"

HEADERS = {
    "User-Agent": "MM2-Monitor/1.0"
}


# =========================================================
# DISCORD WEBHOOK
# =========================================================

def send_webhook(webhook_url, title, description, color=0x5865F2, url=None):

    if not webhook_url or "PASTE_NEW" in webhook_url:
        print(f"[WEBHOOK NOT SET] {title}")
        return

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {
            "text": "MM2 Monitor"
        }
    }

    if url:
        embed["url"] = url

    payload = {
        "username": "MM2 Monitor",
        "embeds": [embed]
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )

        if response.status_code not in (200, 204):
            print(
                f"[WEBHOOK ERROR] "
                f"{response.status_code}: {response.text}"
            )

    except Exception as e:
        print("[WEBHOOK ERROR]", e)


# =========================================================
# SAVE / LOAD STATE
# =========================================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r") as file:
            return json.load(file)

    except Exception:
        return {}


def save_state(state):

    try:
        with open(STATE_FILE, "w") as file:
            json.dump(state, file, indent=4)

    except Exception as e:
        print("[STATE SAVE ERROR]", e)


# =========================================================
# ROBLOX API
# =========================================================

def get_universe_id(place_id):

    url = (
        f"https://apis.roblox.com/universes/v1/"
        f"places/{place_id}/universe"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    return response.json()["universeId"]


def get_game_info(universe_id):

    url = "https://games.roblox.com/v1/games"

    response = requests.get(
        url,
        params={
            "universeIds": universe_id
        },
        headers=HEADERS,
        timeout=10
    )

    response.raise_for_status()

    data = response.json().get("data", [])

    if not data:
        return None

    return data[0]


def get_presence(user_id):

    url = "https://presence.roblox.com/v1/presence/users"

    response = requests.post(
        url,
        json={
            "userIds": [user_id]
        },
        headers={
            **HEADERS,
            "Content-Type": "application/json"
        },
        timeout=10
    )

    response.raise_for_status()

    data = response.json().get("userPresences", [])

    if not data:
        return None

    return data[0]


# =========================================================
# NIKILIS PRESENCE
# =========================================================

PRESENCE_NAMES = {
    0: "Offline",
    1: "Online",
    2: "In Game",
    3: "In Studio"
}


def check_nikilis(state):

    presence = get_presence(NIKILIS_USER_ID)

    if not presence:
        return

    current_presence = presence.get(
        "userPresenceType",
        0
    )

    previous_presence = state.get(
        "nikilis_presence"
    )

    # First run
    if previous_presence is None:
        state["nikilis_presence"] = current_presence

        print(
            "[INIT] Nikilis status:",
            PRESENCE_NAMES.get(
                current_presence,
                "Unknown"
            )
        )

        return

    # Came online
    if previous_presence == 0 and current_presence != 0:

        status = PRESENCE_NAMES.get(
            current_presence,
            "Online"
        )

        location = presence.get(
            "lastLocation",
            "Roblox"
        )

        description = (
            f"**Nikilis just came online!**\n\n"
            f"Status: `{status}`\n"
            f"Location: `{location}`"
        )

        place_id = presence.get("placeId")

        if place_id:
            description += (
                f"\n\n🎮 "
                f"https://www.roblox.com/games/{place_id}"
            )

        send_webhook(
            NIKILIS_WEBHOOK,
            "🟢 Nikilis is Online",
            description,
            0x57F287,
            "https://www.roblox.com/users/1848960/profile"
        )

        print("[ALERT] Nikilis came online.")

    # Went offline
    elif previous_presence != 0 and current_presence == 0:

        print("[INFO] Nikilis went offline.")

        # If you WANT an offline Discord alert too,
        # uncomment this section:

        """
        send_webhook(
            NIKILIS_WEBHOOK,
            "🔴 Nikilis went Offline",
            "Nikilis is no longer online on Roblox.",
            0xED4245,
            "https://www.roblox.com/users/1848960/profile"
        )
        """

    state["nikilis_presence"] = current_presence


# =========================================================
# GAME UPDATE CHECK
# =========================================================

def check_game_update(
    state,
    state_key,
    universe_id,
    place_id,
    display_name,
    webhook_url,
    color
):

    info = get_game_info(universe_id)

    if not info:
        return

    updated = info.get("updated")
    name = info.get("name", display_name)
    playing = info.get("playing", 0)
    visits = info.get("visits", 0)

    previous_update = state.get(state_key)

    # First run
    if previous_update is None:

        state[state_key] = updated

        print(
            f"[INIT] {display_name}: "
            f"{updated}"
        )

        return

    # Update detected
    if updated != previous_update:

        description = (
            f"**{display_name} was updated!**\n\n"
            f"Game: `{name}`\n"
            f"Updated: `{updated}`\n"
            f"Players: `{playing:,}`\n"
            f"Visits: `{visits:,}`\n\n"
            f"🎮 https://www.roblox.com/games/{place_id}"
        )

        send_webhook(
            webhook_url,
            f"🚨 {display_name} Updated",
            description,
            color,
            f"https://www.roblox.com/games/{place_id}"
        )

        print(
            f"[UPDATE] {display_name}"
        )

        print(
            f"Old: {previous_update}"
        )

        print(
            f"New: {updated}"
        )

        state[state_key] = updated


# =========================================================
# STARTUP TEST
# =========================================================

def startup_messages():

    send_webhook(
        MM2_WEBHOOK,
        "✅ MM2 Monitor Started",
        "Now monitoring Murder Mystery 2 for updates.",
        0x57F287
    )

    send_webhook(
        NIKILIS_WEBHOOK,
        "✅ Nikilis Monitor Started",
        "Now monitoring Nikilis's Roblox presence.",
        0x57F287
    )

    send_webhook(
        TESTING_WEBHOOK,
        "✅ Testing Server Monitor Started",
        "Now monitoring the MM2 Testing Server for updates.",
        0x57F287
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 55)
    print("MM2 MONITOR STARTING")
    print("=" * 55)

    state = load_state()

    # Get testing server universe ID automatically
    try:

        testing_universe_id = get_universe_id(
            TESTING_PLACE_ID
        )

        print(
            "[OK] Testing Server Universe ID:",
            testing_universe_id
        )

    except Exception as e:

        print(
            "[ERROR] Could not get testing "
            "server universe ID:",
            e
        )

        return

    print()
    print("Monitoring:")
    print("• Murder Mystery 2 updates")
    print("• MM2 Testing Server updates")
    print("• Nikilis online status")
    print()
    print(
        f"Checking every {CHECK_INTERVAL} seconds."
    )
    print()

    startup_messages()

    while True:

        try:

            # ---------------------------------------------
            # Main Murder Mystery 2
            # ---------------------------------------------

            check_game_update(
                state,
                "mm2_updated",
                MM2_UNIVERSE_ID,
                MM2_PLACE_ID,
                "Murder Mystery 2",
                MM2_WEBHOOK,
                0xFEE75C
            )

            # ---------------------------------------------
            # Testing Server
            # ---------------------------------------------

            check_game_update(
                state,
                "testing_updated",
                testing_universe_id,
                TESTING_PLACE_ID,
                "MM2 Testing Server",
                TESTING_WEBHOOK,
                0x5865F2
            )

            # ---------------------------------------------
            # Nikilis
            # ---------------------------------------------

            check_nikilis(state)

            # Save everything
            save_state(state)

            print(
                f"[{datetime.now().strftime('%I:%M:%S %p')}] "
                "Checked Roblox."
            )

        except requests.exceptions.RequestException as e:

            print(
                "[ROBLOX API ERROR]",
                e
            )

        except KeyboardInterrupt:

            print()
            print("Monitor stopped.")
            break

        except Exception as e:

            print(
                "[ERROR]",
                e
            )

        time.sleep(CHECK_INTERVAL)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()