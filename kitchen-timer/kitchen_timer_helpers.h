#pragma once
// Helpers for kitchen-timer.yaml. Plain C++ with no ESPHome dependencies, so
// they can be compiled and tested off-device (see the tests in the README).

#include <cstdint>
#include <cstdio>
#include <string>

namespace kitchen_timer {

// Device-side view of the Home Assistant timer. HA owns the timer; this only
// mirrors it, plus RINGING, which is purely local (HA is already idle by then).
enum Mode : int { IDLE = 0, ACTIVE = 1, PAUSED = 2, RINGING = 3 };

// Days since 1970-01-01 for a proleptic Gregorian date. Howard Hinnant's
// algorithm: exact, branch-light, and independent of libc's timezone state,
// which on the ESP is whatever TZ the time component last set.
inline int64_t days_from_civil(int64_t y, unsigned m, unsigned d) {
  y -= m <= 2;
  const int64_t era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = static_cast<unsigned>(y - era * 400);
  const unsigned doy = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + static_cast<int64_t>(doe) - 719468;
}

// Parses HA's `finishes_at`, e.g. "2026-10-10T05:30:00+00:00" or
// "2026-10-10T07:30:00.123456+02:00", into a Unix timestamp (UTC seconds).
// Fractional seconds are rounded UP: ringing a fraction of a second late is
// fine, showing 0:00 while the timer is still running is not.
inline bool parse_iso8601(const std::string &s, int64_t &epoch) {
  int y, mo, d, h, mi, se;
  if (std::sscanf(s.c_str(), "%d-%d-%dT%d:%d:%d", &y, &mo, &d, &h, &mi, &se) != 6)
    return false;
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59 || se > 60)
    return false;
  int64_t t = days_from_civil(y, mo, d) * 86400 + h * 3600 + mi * 60 + se;

  const size_t tpos = s.find('T');
  const size_t frac = s.find('.', tpos);
  const size_t zone = s.find_first_of("+-Z", tpos);  // after 'T': date dashes don't count
  if (frac != std::string::npos && (zone == std::string::npos || frac < zone)) {
    for (size_t i = frac + 1; i < s.size() && s[i] >= '0' && s[i] <= '9'; i++) {
      if (s[i] != '0') {
        t += 1;
        break;
      }
    }
  }
  if (zone != std::string::npos && s[zone] != 'Z') {
    int oh = 0, om = 0;
    if (std::sscanf(s.c_str() + zone + 1, "%d:%d", &oh, &om) < 1)
      return false;
    const int offset = oh * 3600 + om * 60;
    t += (s[zone] == '+') ? -offset : offset;  // local time minus offset = UTC
  }
  epoch = t;
  return true;
}

// Parses HA's `remaining` / `duration`, e.g. "0:04:59" or "1:30:00", to seconds.
// HA renders durations of a day or more as "1 day, 2:00:00"; those return false.
inline bool parse_hms(const std::string &s, int &seconds) {
  int h, m, sec;
  char trailing;
  if (std::sscanf(s.c_str(), "%d:%d:%d%c", &h, &m, &sec, &trailing) != 3)
    return false;
  if (h < 0 || m < 0 || m > 59 || sec < 0 || sec > 59)
    return false;
  seconds = h * 3600 + m * 60 + sec;
  return true;
}

}  // namespace kitchen_timer
