"""
ATC Clearance Module
"""


def issue_clearance():

    print("\n======================================")
    print("         ATC CLEARANCE")
    print("======================================")

    flight_number = input("Flight Number : ").upper()

    destination = input("Cleared To (ICAO) : ").upper()

    sid = input("SID : ").upper()

    runway = input("Runway : ").upper()

    initial_climb = input("Initial Climb (FT) : ")

    squawk = input("Squawk : ")

    frequency = input("Tower Frequency : ")

    print("\n======================================")
    print("        ATC CLEARANCE ISSUED")
    print("======================================")

    print("CALLSIGN :", flight_number)
    print("CLEARED TO :", destination)
    print("SID :", sid)
    print("RUNWAY :", runway)
    print("INITIAL CLIMB :", initial_climb, "FT")
    print("SQUAWK :", squawk)
    print("CONTACT TOWER :", frequency)

    print("======================================")
