#pragma once
// Translations for the guest room e-ink display (guest-eink.yaml).
// Language index = option order of the "Language" select:
//   0 English, 1 Deutsch, 2 Français, 3 Italiano
// Every character used here must exist in the fonts (GF_Latin_Core covers all of them).
#include <string>

enum TrKey {
  T_GREETING,     // default greeting when the Greeting field is empty
  T_IDLE,         // idle card
  T_TOMORROW,
  T_WIND,         // "Wind 6 km/h"
  T_RAIN,         // "Rain 40%"
  T_DRY,          // no meaningful rain chance
  T_SCAN,         // under the QR code
  T_PASSWORD,     // "Password  xyz"
  T_PW_MISSING_1, // placeholder box, line 1
  T_PW_MISSING_2, // placeholder box, line 2
  T_COUNT
};

static const char *const TR[4][T_COUNT] = {
  {"Welcome,", "Ready for the next guest", "Tomorrow", "Wind", "Rain", "Dry",
   "Scan with your camera to join", "Password", "Wi-Fi password", "not set yet"},
  {"Willkommen,", "Bereit für den nächsten Gast", "Morgen", "Wind", "Regen", "Kein Regen",
   "Mit der Kamera scannen", "Passwort", "WLAN-Passwort", "noch nicht gesetzt"},
  {"Bienvenue,", "Prêt pour le prochain invité", "Demain", "Vent", "Pluie", "Pas de pluie",
   "Scannez pour vous connecter", "Mot de passe", "Mot de passe Wi-Fi", "pas encore défini"},
  {"Benvenuti,", "Pronto per il prossimo ospite", "Domani", "Vento", "Pioggia", "Niente pioggia",
   "Inquadra per connetterti", "Password", "Password Wi-Fi", "non ancora impostata"},
};

inline int lang_clamp(int l) { return (l < 0 || l > 3) ? 0 : l; }

inline const char *tr(int lang, TrKey k) { return TR[lang_clamp(lang)][k]; }

// ESPTime::day_of_week: 1 = Sunday ... 7 = Saturday
inline const char *weekday_name(int lang, int dow) {
  static const char *const D[4][7] = {
    {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"},
    {"Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"},
    {"Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"},
    {"Domenica", "Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"},
  };
  if (dow < 1 || dow > 7) return "";
  return D[lang_clamp(lang)][dow - 1];
}

// Weather condition label in the selected language (HA condition names).
inline const char *wx_label_tr(int lang, const std::string &c) {
  static const char *const KEYS[] = {"sunny", "clear-night", "partlycloudy", "cloudy", "fog", "hail",
                                     "lightning", "lightning-rainy", "pouring", "rainy", "snowy",
                                     "snowy-rainy", "windy", "windy-variant", "exceptional"};
  static const char *const L[4][15] = {
    {"Sunny", "Clear night", "Partly cloudy", "Cloudy", "Fog", "Hail", "Thunderstorms",
     "Thunder and rain", "Heavy rain", "Rain", "Snow", "Sleet", "Windy", "Windy", "Severe weather"},
    {"Sonnig", "Klare Nacht", "Leicht bewölkt", "Bewölkt", "Nebel", "Hagel", "Gewitter",
     "Gewitterregen", "Starkregen", "Regen", "Schnee", "Schneeregen", "Windig", "Windig", "Unwetter"},
    {"Ensoleillé", "Nuit claire", "Éclaircies", "Nuageux", "Brouillard", "Grêle", "Orages",
     "Orage et pluie", "Forte pluie", "Pluie", "Neige", "Pluie et neige", "Venteux", "Venteux",
     "Intempéries"},
    {"Soleggiato", "Notte serena", "Poco nuvoloso", "Nuvoloso", "Nebbia", "Grandine", "Temporali",
     "Temporale", "Pioggia forte", "Pioggia", "Neve", "Nevischio", "Ventoso", "Ventoso", "Maltempo"},
  };
  for (int i = 0; i < 15; i++)
    if (c == KEYS[i]) return L[lang_clamp(lang)][i];
  return "";
}
