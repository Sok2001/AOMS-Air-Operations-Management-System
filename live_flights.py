"""
Live Flights Module
"""

import requests

URL = "https://opensky-network.org/api/states/all"


def live_flights():
    """Get and display live flights from OpenSky Network"""
    print("\n" + "=" * 42)
    print("     LIVE FLIGHTS (OpenSky)")
    print("=" * 42)
    print("\nDownloading live flights...\n")

    try:
        response = requests.get(URL, timeout=15)
        data = response.json()

        # OpenSky returns a dict with 'states' key
        if isinstance(data, dict) and "states" in data:
            states = data["states"]
        else:
            print("✗ Unexpected data format from API.")
            return

        if not states:
            print("No flights found.")
            return

        print(f"Showing first 10 live flights (Total: {len(states)})\n")
        print("-" * 42)

        count = 0
        for flight in states:
            if count >= 10:
                break

            callsign = flight[1] if len(flight) > 1 else "N/A"
            country = flight[2] if len(flight) > 2 else "N/A"
            altitude = flight[7] if len(flight) > 7 else "N/A"
            velocity = flight[9] if len(flight) > 9 else "N/A"

            # Skip flights without callsign
            if not callsign or callsign.strip() == "":
                continue

            print("-" * 42)
            print(f"  Callsign : {callsign.strip()}")
            print(f"  Country  : {country}")
            print(f"  Altitude : {altitude} ft" if altitude != "N/A" else "  Altitude : N/A")
            print(f"  Speed    : {velocity} kt" if velocity != "N/A" else "  Speed    : N/A")

            count += 1

        if count == 0:
            print("  No flights with callsign found.")

        print("-" * 42)

    except requests.exceptions.Timeout:
        print("✗ Connection Timeout")
    except requests.exceptions.ConnectionError:
        print("✗ No Internet Connection")
    except Exception as e:
        print(f"✗ Error: {e}")
