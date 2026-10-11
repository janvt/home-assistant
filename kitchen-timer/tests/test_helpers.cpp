// Off-device tests for kitchen_timer_helpers.h, compiled and run by
// tests/test_kitchen_timer_helpers.py.
//
// The parsers sit on a seam: they read Home Assistant's `finishes_at` and
// `remaining` attributes. Get the timezone sign or the fractional seconds wrong
// and nothing errors: the display is just hours off, or rings a second early.
#include "../kitchen_timer_helpers.h"
#include <cassert>
#include <ctime>
#include <cstdio>
using namespace kitchen_timer;
int main() {
  int64_t e;
  assert(parse_iso8601("1970-01-01T00:00:00+00:00", e) && e == 0);
  assert(parse_iso8601("2026-10-10T05:30:00+00:00", e) && e == 1791610200);
  assert(parse_iso8601("2026-10-10T07:30:00+02:00", e) && e == 1791610200);
  assert(parse_iso8601("2026-10-10T05:30:00Z", e) && e == 1791610200);
  assert(parse_iso8601("2026-10-10T05:29:59.000001+00:00", e) && e == 1791610200);
  assert(parse_iso8601("2026-10-10T05:30:00.000000+00:00", e) && e == 1791610200);
  assert(parse_iso8601("2024-02-29T23:59:59-05:00", e) && e == 1709269199);
  assert(!parse_iso8601("", e));
  assert(!parse_iso8601("unknown", e));
  // cross-check against timegm for many timestamps
  for (int64_t t = 0; t < 4102444800; t += 86400 * 37 + 12345) {
    struct tm tmv; time_t tt = t; gmtime_r(&tt, &tmv);
    char buf[40]; strftime(buf, sizeof buf, "%Y-%m-%dT%H:%M:%S+00:00", &tmv);
    assert(parse_iso8601(buf, e) && e == t);
  }
  int s;
  assert(parse_hms("0:04:59", s) && s == 299);
  assert(parse_hms("1:30:00", s) && s == 5400);
  assert(!parse_hms("1 day, 2:00:00", s));
  assert(!parse_hms("", s));
  assert(!parse_hms("0:04:59x", s));
  puts("all helper tests passed");
}
