#pragma once
#include <cmath>

/**
 * Draw the page-indicator dots and left/right navigation chevrons.
 * Adapted for the M5Stack CoreS3's 320×240 rectangular display.
 * (Display hardware is the same ILI9342C as on the Core2/Core Basic.)
 *
 * @param it            ESPHome display reference
 * @param current_page  Index of the currently active page (0-based)
 * @param num_pages     Total number of pages
 * @param active_color  Colour for the active dot
 * @param dim_color     Colour for inactive dots and chevrons
 * @param left_chevron  Pointer to the left-chevron image
 * @param right_chevron Pointer to the right-chevron image
 */
inline void draw_chrome(esphome::display::Display &it,
                         int current_page,
                         int num_pages,
                         esphome::Color active_color,
                         esphome::Color dim_color,
                         esphome::image::Image *left_chevron,
                         esphome::image::Image *right_chevron) {
  // Centre dots horizontally (12 px spacing) near the bottom of the screen
  int dot_start = 160 - ((num_pages - 1) * 12) / 2;
  for (int i = 0; i < num_pages; i++)
    it.filled_circle(dot_start + i * 12, 232, 3,
                     (i == current_page) ? active_color : dim_color);
  // Navigation chevrons (24×24) at left and right edges, vertically centred
  it.image(8,   108, left_chevron,  dim_color);
  it.image(288, 108, right_chevron, dim_color);
}

/**
 * Draw a horizontal progress bar.
 * This replaces the circular arc used on the M5 Dial.
 * Bar spans x: 70 – 250, y: 162 – 170 (8 px tall, 180 px wide).
 *
 * Function is intentionally named draw_arc so the YAML pages require no changes.
 *
 * @param it         ESPHome display reference
 * @param normalized Fill level 0.0 – 1.0  (pass 0.0 to draw an empty bar)
 * @param active     Colour for the filled portion
 * @param bg         Colour for the unfilled portion
 */
inline void draw_arc(esphome::display::Display &it,
                     float normalized,
                     esphome::Color active,
                     esphome::Color bg) {
  const int x = 70, y = 162, w = 180, h = 8;
  if (normalized < 0.0f) normalized = 0.0f;
  if (normalized > 1.0f) normalized = 1.0f;
  // Background track
  it.filled_rectangle(x, y, w, h, bg);
  // Active fill
  const int fw = (int)(normalized * (float)w);
  if (fw > 0)
    it.filled_rectangle(x, y, fw, h, active);
}

