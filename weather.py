"""
Weather Module
"""

from api import get_metar


def show_metar(icao):
    """Display METAR for an airport"""

    metar = get_metar(icao)

    if metar is None:
        print("\n✗ No METAR available for", icao)
        return

    print("\n" + "=" * 60)
    print("          LIVE METAR")
    print("=" * 60)

    # ICAO
    print(f"  ICAO        : {metar.get('station', icao)}")

    # Time
    if metar.get("time"):
        print(f"  Time        : {metar['time'].get('repr', 'N/A')}")

    # Temperature
    if metar.get("temperature"):
        temp = metar["temperature"].get("value")
        if temp is not None:
            print(f"  Temperature : {temp} °C")

    # Dewpoint
    if metar.get("dewpoint"):
        dew = metar["dewpoint"].get("value")
        if dew is not None:
            print(f"  Dewpoint    : {dew} °C")

    # Wind
    if metar.get("wind_direction") and metar.get("wind_speed"):
        direction = metar["wind_direction"].get("value")
        speed = metar["wind_speed"].get("value")
        gust = metar["wind_speed"].get("gust")

        if direction is not None and speed is not None:
            wind_str = f"{direction}° {speed} KT"
            if gust:
                wind_str += f" (Gust {gust} KT)"
            print(f"  Wind        : {wind_str}")

    # Visibility
    if metar.get("visibility"):
        vis = metar["visibility"].get("value")
        if vis is not None:
            print(f"  Visibility  : {vis} m")

    # Altimeter (QNH)
    if metar.get("altimeter"):
        alt = metar["altimeter"].get("value")
        if alt is not None:
            print(f"  QNH         : {alt} hPa")

    # Clouds
    if metar.get("clouds"):
        clouds = metar["clouds"]
        cloud_str = []
        for cloud in clouds:
            if cloud.get("type") and cloud.get("altitude"):
                cloud_str.append(f"{cloud['type']} at {cloud['altitude']} ft")
        if cloud_str:
            print(f"  Clouds      : {', '.join(cloud_str)}")

    # Flight Category (VFR, MVFR, IFR, LIFR)
    if metar.get("flight_rules"):
        rules = metar.get("flight_rules")
        print(f"  Flight Rules: {rules}")

    # RAW METAR
    print("\n" + "-" * 60)
    print("  RAW METAR")
    print("-" * 60)
    print(f"  {metar.get('raw', 'N/A')}")
    print("=" * 60)

    # Decoded summary (also remembered for dashboard / alerts / AI support)
    import metar_parser
    decoded = metar_parser.parse_metar(metar.get("raw", ""))
    if decoded:
        metar_parser.set_latest(decoded)
        print("\n" + "-" * 60)
        print("  DECODED")
        print("-" * 60)
        for key, value in metar_parser.summary_lines(decoded).items():
            print(f"  {key:<13}: {value}")
        print("=" * 60)


def show_taf(icao):
    """Display the decoded TAF groups"""
    from api import get_taf
    import metar_parser

    taf = get_taf(icao)
    if not taf or not taf.get("raw"):
        print("\n✗ No TAF available for", icao)
        return
    print("\n" + "=" * 60)
    print(f"          TAF {icao}")
    print("=" * 60)
    print(f"  {taf['raw']}\n")
    for g in metar_parser.parse_taf(taf["raw"]):
        wx = ", ".join(g["weather"]) or "-"
        print(f"  {g['type']:<6} wind {metar_parser.describe_wind(g):<16} vis {metar_parser.describe_visibility(g):<8} "
              f"{g['flight_rules']:<5} {wx}")
    print("=" * 60)
