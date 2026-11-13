"""Shared projection: lat/lon -> base-map pixel grid."""
import math

LON_MIN, LON_MAX = -122.5175, -122.3550
LAT_MIN, LAT_MAX = 37.7050, 37.8400
COS = math.cos(math.radians(37.77))
W = 720
K = W / ((LON_MAX - LON_MIN) * COS)  # px per degree latitude
H = int(round((LAT_MAX - LAT_MIN) * K))


def proj(lon, lat):
    return ((lon - LON_MIN) * COS * K, (LAT_MAX - lat) * K)


def unproj(x, y):
    return (x / (COS * K) + LON_MIN, LAT_MAX - y / K)
