import requests
import time
import json
import os
from datetime import datetime, timezone

# =========================================================
# CONFIG
# =========================================================

# These are stored privately in Railway Variables
MM2_WEBHOOK = os.getenv("MM2_WEBHOOK")
NIKILIS_WEBHOOK = os.getenv("NIKILIS_WEBHOOK")
TESTING_WEBHOOK = os.getenv("TESTING_WEBHOOK")

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
    "User-Agent": "MM2-Monitor/2.0"
}


# =========================================================
# DISCORD WEBHOOK
# =========================================================

def send_webhook(
    webhook_url,
    title,
    description,
    color=0x5865F2,
    url=None,
    image_url=None,
    thumbnail_url=None,
    ping=False
):

    if not webhook_url:
        print(f"[WEBHOOK NOT SET] {title}")
        return

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {
            "text": "MM2 Monitor • Roblox Tracker"
        }
    }

    if url:
        embed["url"] = url

    if image_url:
        embed["image"] = {
            "url": image_url
        }

    if thumbnail_url:
        embed["thumbnail"] = {
            "url": thumbnail_url
        }

    payload = {
        "username": "MM2 Monitor",
        "embeds": [embed]
    }

    # Only real alerts ping everyone
    if ping:
        payload["content"] = "@everyone"
        payload["allowed_mentions"] = {
            "parse": ["everyone"]
        }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=15
        )

        if response.status_code not in (200, 204):
            print(
                f"[WEBHOOK ERROR] "
                f"{response.status_code}: {response.text}"
            )

    except Exception as e:
        print("[WEBHOOK ERROR]", e)


# =========================================================
# STATE
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

    data = response.json().get(
        "userPresences",
        []
    )

    if not data:
        return None

    return data[0]


# =========================================================
# ROBLOX IMAGES
# =========================================================

def get_game_thumbnail(universe_id):

    try:

        url = (
            "https://thumbnails.roblox.com/v1/"
            "games/icons"
        )

        response = requests.get(
            url,
            params={
                "universeIds": universe_id,
                "returnPolicy": "PlaceHolder",
                "size": "512x512",
                "format": "Png",
                "isCircular": "false"
            },
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        data = response.json().get("data", [])

        if data:
            return data[0].get("imageUrl")

    except Exception as e:
        print(
            "[GAME THUMBNAIL ERROR]",
            e
        )

    return None


def get_avatar_headshot(user_id):

    try:

        url = (
            "https://thumbnails.roblox.com/v1/"
            "users/avatar-headshot"
        )

        response = requests.get(
            url,
            params={
                "userIds": user_id,
                "size": "420x420",
                "format": "Png",
                "isCircular": "false"
            },
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        data = response.json().get("data", [])

        if data:
            return data[0].get("imageUrl")

    except Exception as e:
        print(
            "[AVATAR ERROR]",
            e
        )

    return None


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

    presence = get_presence(
        NIKILIS_USER_ID
    )

    if not presence:
        return

    current_presence = presence.get(
        "userPresenceType",
        0
    )

    previous_presence = state.get(
        "nikilis_presence"
    )

    # ---------------------------------------------
    # First run
    # ---------------------------------------------

    if previous_presence is None:

        state["nikilis_presence"] = (
            current_presence
        )

        print(
            "[INIT] Nikilis status:",
            PRESENCE_NAMES.get(
                current_presence,
                "Unknown"
            )
        )

        return

    # ---------------------------------------------
    # Nikilis came online
    # ---------------------------------------------

    if (
        previous_presence == 0
        and current_presence != 0
    ):

        status = PRESENCE_NAMES.get(
            current_presence,
            "Online"
        )

        location = presence.get(
            "lastLocation",
            "Roblox"
        )

        avatar = get_avatar_headshot(
            NIKILIS_USER_ID
        )

        description = (
            "### 👤 Nikilis Activity Detected\n\n"
            "Nikilis just came online on Roblox.\n\n"
            f"🟢 **Status:** `{status}`\n"
            f"📍 **Location:** `{location}`"
        )

        place_id = presence.get("placeId")

        if place_id:

            description += (
                "\n\n"
                f"🎮 **Current Place:** "
                f"[Join / View Game]"
                f"(https://www.roblox.com/games/"
                f"{place_id})"
            )

        send_webhook(
            NIKILIS_WEBHOOK,
            "🟢 Nikilis Is Online!",
            description,
            0x57F287,
            (
                "https://www.roblox.com/users/"
                "1848960/profile"
            ),
            thumbnail_url=avatar,
            ping=True
        )

        print(
            "[ALERT] Nikilis came online."
        )

    # ---------------------------------------------
    # Went offline
    # ---------------------------------------------

    elif (
        previous_presence != 0
        and current_presence == 0
    ):

        print(
            "[INFO] Nikilis went offline."
        )

    state["nikilis_presence"] = (
        current_presence
    )


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
    color,
    icon
):

    info = get_game_info(
        universe_id
    )

    if not info:
        return

    updated = info.get("updated")

    name = info.get(
        "name",
        display_name
    )

    playing = info.get(
        "playing",
        0
    )

    visits = info.get(
        "visits",
        0
    )

    previous_update = state.get(
        state_key
    )

    # ---------------------------------------------
    # First run
    # ---------------------------------------------

    if previous_update is None:

        state[state_key] = updated

        print(
            f"[INIT] {display_name}: "
            f"{updated}"
        )

        return

    # ---------------------------------------------
    # UPDATE DETECTED
    # ---------------------------------------------

    if updated != previous_update:

        game_thumbnail = (
            get_game_thumbnail(
                universe_id
            )
        )

        game_url = (
            f"https://www.roblox.com/"
            f"games/{place_id}"
        )

        description = (
            f"### {icon} Update Detected\n\n"
            f"**{name}** was just updated "
            f"on Roblox!\n\n"
            f"👥 **Players Online:** "
            f"`{playing:,}`\n"
            f"👁️ **Total Visits:** "
            f"`{visits:,}`\n"
            f"🕒 **Roblox Updated:** "
            f"`{updated}`\n\n"
            f"🎮 **[OPEN GAME]({game_url})**"
        )

        send_webhook(
            webhook_url,
            f"{icon} {display_name} Updated!",
            description,
            color,
            game_url,
            image_url=game_thumbnail,
            ping=True
        )

        print()
        print(
            "=" * 55
        )

        print(
            f"[UPDATE] {display_name}"
        )

        print(
            f"OLD: {previous_update}"
        )

        print(
            f"NEW: {updated}"
        )

        print(
            "=" * 55
        )

        print()

        state[state_key] = updated


# =========================================================
# STARTUP MESSAGES
# =========================================================

def startup_messages(
    testing_universe_id
):

    mm2_thumbnail = (
        get_game_thumbnail(
            MM2_UNIVERSE_ID
        )
    )

    testing_thumbnail = (
        get_game_thumbnail(
            testing_universe_id
        )
    )

    nikilis_avatar = (
        get_avatar_headshot(
            NIKILIS_USER_ID
        )
    )

    # ---------------------------------------------
    # MM2
    # ---------------------------------------------

    send_webhook(
        MM2_WEBHOOK,
        "🔪 MM2 Monitor Online",
        (
            "### Murder Mystery 2\n\n"
            "✅ Update monitoring is active.\n\n"
            "I'll send an alert as soon as "
            "Roblox reports a new update.\n\n"
            f"⏱️ **Check interval:** "
            f"`{CHECK_INTERVAL} seconds`"
        ),
        0xED4245,
        (
            "https://www.roblox.com/games/"
            f"{MM2_PLACE_ID}"
        ),
        image_url=mm2_thumbnail,
        ping=False
    )

    # ---------------------------------------------
    # NIKILIS
    # ---------------------------------------------

    send_webhook(
        NIKILIS_WEBHOOK,
        "👤 Nikilis Monitor Online",
        (
            "### Nikilis Presence Tracker\n\n"
            "✅ Presence monitoring is active.\n\n"
            "I'll send an alert when Nikilis "
            "comes online on Roblox.\n\n"
            f"⏱️ **Check interval:** "
            f"`{CHECK_INTERVAL} seconds`"
        ),
        0x57F287,
        (
            "https://www.roblox.com/users/"
            "1848960/profile"
        ),
        thumbnail_url=nikilis_avatar,
        ping=False
    )

    # ---------------------------------------------
    # TESTING SERVER
    # ---------------------------------------------

    send_webhook(
        TESTING_WEBHOOK,
        "🧪 Testing Server Monitor Online",
        (
            "### MM2 Testing Server\n\n"
            "✅ Update monitoring is active.\n\n"
            "I'll send an alert as soon as "
            "the testing server changes.\n\n"
            f"⏱️ **Check interval:** "
            f"`{CHECK_INTERVAL} seconds`"
        ),
        0x5865F2,
        (
            "https://www.roblox.com/games/"
            f"{TESTING_PLACE_ID}"
        ),
        image_url=testing_thumbnail,
        ping=False
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=" * 55
    )

    print(
        "MM2 MONITOR V2 STARTING"
    )

    print(
        "=" * 55
    )

    state = load_state()

    # ---------------------------------------------
    # Resolve Testing Server universe
    # ---------------------------------------------

    try:

        testing_universe_id = (
            get_universe_id(
                TESTING_PLACE_ID
            )
        )

        print(
            "[OK] Testing Server Universe ID:",
            testing_universe_id
        )

    except Exception as e:

        print(
            "[ERROR] Could not get "
            "Testing Server Universe ID:",
            e
        )

        return

    print()
    print("Monitoring:")
    print("🔪 Murder Mystery 2")
    print("🧪 MM2 Testing Server")
    print("👤 Nikilis")
    print()

    print(
        f"Checking every "
        f"{CHECK_INTERVAL} seconds."
    )

    print()

    # ---------------------------------------------
    # Send startup messages
    # ---------------------------------------------

    startup_messages(
        testing_universe_id
    )

    # ---------------------------------------------
    # Monitor forever
    # ---------------------------------------------

    while True:

        try:

            # =====================================
            # MAIN MM2
            # =====================================

            check_game_update(
                state,
                "mm2_updated",
                MM2_UNIVERSE_ID,
                MM2_PLACE_ID,
                "Murder Mystery 2",
                MM2_WEBHOOK,
                0xED4245,
                "🔪"
            )

            # =====================================
            # TESTING SERVER
            # =====================================

            check_game_update(
                state,
                "testing_updated",
                testing_universe_id,
                TESTING_PLACE_ID,
                "MM2 Testing Server",
                TESTING_WEBHOOK,
                0x5865F2,
                "🧪"
            )

            # =====================================
            # NIKILIS
            # =====================================

            check_nikilis(
                state
            )

            # Save current state
            save_state(
                state
            )

            print(
                f"["
                f"{datetime.now().strftime('%I:%M:%S %p')}"
                f"] Roblox checked ✓"
            )

        except requests.exceptions.RequestException as e:

            print(
                "[ROBLOX API ERROR]",
                e
            )

        except KeyboardInterrupt:

            print()
            print(
                "Monitor stopped."
            )

            break

        except Exception as e:

            print(
                "[ERROR]",
                e
            )

        time.sleep(
            CHECK_INTERVAL
        )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
