#pragma once
// Helpers for the guest room e-ink display (guest-eink.yaml).
#include <string>

// Material Design Icons glyph (UTF-8) for a Home Assistant weather condition.
// Every glyph returned here must also be listed in the icon fonts' glyphs.
inline const char *wx_icon(const std::string &c) {
  if (c == "sunny") return "\U000F0599";            // weather-sunny
  if (c == "clear-night") return "\U000F0594";      // weather-night
  if (c == "partlycloudy") return "\U000F0595";     // weather-partly-cloudy
  if (c == "cloudy") return "\U000F0590";           // weather-cloudy
  if (c == "fog") return "\U000F0591";              // weather-fog
  if (c == "hail") return "\U000F0592";             // weather-hail
  if (c == "lightning") return "\U000F0593";        // weather-lightning
  if (c == "lightning-rainy") return "\U000F067E";  // weather-lightning-rainy
  if (c == "pouring") return "\U000F0596";          // weather-pouring
  if (c == "rainy") return "\U000F0597";            // weather-rainy
  if (c == "snowy") return "\U000F0598";            // weather-snowy
  if (c == "snowy-rainy") return "\U000F067F";      // weather-snowy-rainy
  if (c == "windy" || c == "windy-variant") return "\U000F059D";  // weather-windy
  return "\U000F0590";                              // fallback: cloudy
}

// Human-readable label for a Home Assistant weather condition.
inline const char *wx_label(const std::string &c) {
  if (c == "sunny") return "Sunny";
  if (c == "clear-night") return "Clear night";
  if (c == "partlycloudy") return "Partly cloudy";
  if (c == "cloudy") return "Cloudy";
  if (c == "fog") return "Fog";
  if (c == "hail") return "Hail";
  if (c == "lightning") return "Thunderstorms";
  if (c == "lightning-rainy") return "Thunder and rain";
  if (c == "pouring") return "Heavy rain";
  if (c == "rainy") return "Rain";
  if (c == "snowy") return "Snow";
  if (c == "snowy-rainy") return "Sleet";
  if (c == "windy" || c == "windy-variant") return "Windy";
  if (c == "exceptional") return "Severe weather";
  return "";
}

// Escape a value for the WIFI: QR payload (backslash, semicolon, comma,
// colon and double quote must be backslash-escaped per the de facto spec).
inline std::string wifi_escape(const std::string &s) {
  std::string out;
  out.reserve(s.size() + 4);
  for (char ch : s) {
    if (ch == '\\' || ch == ';' || ch == ',' || ch == ':' || ch == '"') out.push_back('\\');
    out.push_back(ch);
  }
  return out;
}

// True if a Home Assistant text state carries no usable value.
inline bool ha_empty(const std::string &s) {
  return s.empty() || s == "unknown" || s == "unavailable";
}
