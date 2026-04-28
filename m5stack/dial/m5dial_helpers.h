#pragma once
#include <cmath>

/**
 * Draw the page-indicator dots and left/right navigation chevrons.
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
  for (int i = 0; i < num_pages; i++)
    it.filled_circle(102 + i * 10 - 1, 232, 3, (i == current_page) ? active_color : dim_color);
  it.image(20, 108, left_chevron, dim_color);
  it.image(196, 108, right_chevron, dim_color);
}

/**
 * Draw the ring-arc used on every control page.
 *
 * @param it         ESPHome display reference (captured from page lambda)
 * @param normalized Fill level 0.0 – 1.0  (pass 0.0 to draw an empty arc)
 * @param active     Colour for the filled portion
 * @param bg         Colour for the unfilled portion (typically color_arc_bg)
 */
inline void draw_arc(esphome::display::Display &it,
                     float normalized,
                     esphome::Color active,
                     esphome::Color bg) {
  const float kStart = 150.0f;
  const float kRange = 240.0f;
  const float fill_to = kStart + kRange * normalized;
  for (float a = kStart; a < kStart + kRange; a += 3.0f) {
    const float rad = a * (3.14159265f / 180.0f);
    const esphome::Color c = (a < fill_to) ? active : bg;
    for (int r = 104; r <= 108; r++)
      it.draw_pixel_at(120 + (int)(r * cosf(rad)), 120 + (int)(r * sinf(rad)), c);
  }
}


