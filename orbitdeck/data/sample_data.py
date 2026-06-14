"""
sample_data.py - a small bundled GP catalog + transponders so the desktop app
runs immediately offline. Replace via File > Update (online) for live elements.

Elements are representative recent amateur-satellite GP/OMM records. They are
fine for demonstrating every screen; for on-the-air accuracy fetch fresh GP.
"""

import json

SAMPLE_GP = [
    {
        "AMSAT_NAME": "ISS", "OBJECT_NAME": "ISS (ZARYA)", "OBJECT_ID": "1998-067A",
        "EPOCH": "2024-06-01T12:00:00.000000", "MEAN_MOTION": 15.50103472,
        "ECCENTRICITY": 0.0004364, "INCLINATION": 51.6393,
        "RA_OF_ASC_NODE": 210.0, "ARG_OF_PERICENTER": 80.0,
        "MEAN_ANOMALY": 280.0, "BSTAR": 0.00025, "MEAN_MOTION_DOT": 0.0001,
        "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 25544, "REV_AT_EPOCH": 45000,
        "ELEMENT_SET_NO": 999
    },
    {
        "AMSAT_NAME": "SO-50", "OBJECT_NAME": "SAUDISAT 1C", "OBJECT_ID": "2002-058C",
        "EPOCH": "2024-06-01T06:00:00.000000", "MEAN_MOTION": 14.81000000,
        "ECCENTRICITY": 0.0065000, "INCLINATION": 64.5550,
        "RA_OF_ASC_NODE": 120.0, "ARG_OF_PERICENTER": 250.0,
        "MEAN_ANOMALY": 110.0, "BSTAR": 0.00012, "MEAN_MOTION_DOT": 0.00001,
        "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 27607, "REV_AT_EPOCH": 60000,
        "ELEMENT_SET_NO": 999
    },
    {
        "AMSAT_NAME": "AO-91", "OBJECT_NAME": "FOX-1B", "OBJECT_ID": "2017-073E",
        "EPOCH": "2024-06-01T08:00:00.000000", "MEAN_MOTION": 14.78000000,
        "ECCENTRICITY": 0.0220000, "INCLINATION": 97.7000,
        "RA_OF_ASC_NODE": 200.0, "ARG_OF_PERICENTER": 90.0,
        "MEAN_ANOMALY": 270.0, "BSTAR": 0.00010, "MEAN_MOTION_DOT": 0.00001,
        "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 43017, "REV_AT_EPOCH": 35000,
        "ELEMENT_SET_NO": 999
    },
    {
        "AMSAT_NAME": "CAS-4B", "OBJECT_NAME": "ZHUHAI-1 OVS-1B", "OBJECT_ID": "2017-034B",
        "EPOCH": "2024-06-01T05:00:00.000000", "MEAN_MOTION": 14.60000000,
        "ECCENTRICITY": 0.0012000, "INCLINATION": 43.0200,
        "RA_OF_ASC_NODE": 60.0, "ARG_OF_PERICENTER": 180.0,
        "MEAN_ANOMALY": 200.0, "BSTAR": 0.00008, "MEAN_MOTION_DOT": 0.00001,
        "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 42761, "REV_AT_EPOCH": 38000,
        "ELEMENT_SET_NO": 999
    },
    {
        "AMSAT_NAME": "RS-44", "OBJECT_NAME": "DOSAAF-85", "OBJECT_ID": "2019-038D",
        "EPOCH": "2024-06-01T04:00:00.000000", "MEAN_MOTION": 11.85000000,
        "ECCENTRICITY": 0.0220000, "INCLINATION": 82.5200,
        "RA_OF_ASC_NODE": 150.0, "ARG_OF_PERICENTER": 100.0,
        "MEAN_ANOMALY": 260.0, "BSTAR": 0.00002, "MEAN_MOTION_DOT": 0.000001,
        "MEAN_MOTION_DDOT": 0.0, "NORAD_CAT_ID": 44909, "REV_AT_EPOCH": 25000,
        "ELEMENT_SET_NO": 999
    },
]

# Minimal transponder data keyed by NORAD (mirrors SatNOGS fields the app uses).
SAMPLE_TX = {
    25544: [
        {"description": "Voice Repeater", "downlink_low": 437800000,
         "uplink_low": 145990000, "mode": "FM", "status": "active"},
    ],
    27607: [
        {"description": "FM Voice", "downlink_low": 436795000,
         "uplink_low": 145850000, "mode": "FM", "status": "active"},
    ],
    43017: [
        {"description": "FM Voice", "downlink_low": 145960000,
         "uplink_low": 435250000, "mode": "FM", "status": "active"},
    ],
    42761: [
        {"description": "Linear Transponder", "downlink_low": 145855000,
         "downlink_high": 145875000, "uplink_low": 435210000,
         "uplink_high": 435230000, "mode": "USB", "invert": True,
         "status": "active"},
    ],
    44909: [
        {"description": "Linear Transponder", "downlink_low": 435610000,
         "downlink_high": 435670000, "uplink_low": 145935000,
         "uplink_high": 145995000, "mode": "USB", "invert": True,
         "status": "active"},
    ],
}


def sample_gp_json():
    return json.dumps(SAMPLE_GP)


def sample_tx_for(norad):
    return json.dumps(SAMPLE_TX.get(norad, []))
