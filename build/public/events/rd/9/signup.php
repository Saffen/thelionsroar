<?php
// Adjust these two if your paths differ
$SITE_TITLE = "Roaring Days 9, Pet Rock Edition: Artist Application | The Lion's Roar";
$CSS_HREF   = "/assets/css/newbase.css";   // TODO: set to the same stylesheet as your news pages
$LOGO_HREF  = "/logo.svg";              // repo root has logo.svg

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title><?= htmlspecialchars($SITE_TITLE) ?></title>

  <link rel="stylesheet" href="<?= htmlspecialchars($CSS_HREF) ?>" />
  <link rel="icon" href="/assets/favicon.svg" />
</head>

<body>

  <header class="site-header">
    <div class="site-header-inner">
      <a class="site-brand" href="/">
        <img src="<?= htmlspecialchars($LOGO_HREF) ?>" alt="The Lion's Roar" style="height:156px; width:auto;" />
      </a>
    </div>
  </header>

  <main>
    <section class="article-grid" style="padding-top:20px;">
      <div style="margin-left: 1rem;">

        <h1>Roaring Days 9, Pet Rock Edition: Artist Application</h1>
        <p class="article-teaser">
          April 17–19, 2026 (Friday to Sunday).
        </p>

        <p class="article-byline">
          Stage hours: Fri 20:00–01:00 · Sat 20:00–01:00 · Sun 20:00–23:00
        </p>

        <hr />

        <div class="article-content">
          <h2>Before you apply</h2>
          <p>
            Roaring Days 9 is shorter than Roaring Days 8, which means we cannot guarantee a slot for all applicants.
            Scheduling will be curated to create a good flow across the weekend, with a balance of genres, tones, and set lengths.
          </p>
          <p>
            Artists may be offered a <strong>showcase set</strong> (10–15 min), a <strong>standard set</strong> (20–30 min),
            or a <strong>feature set</strong> (40–45 min), depending on availability and weekend pacing.
          </p>

          <h2>Application form</h2>

          <form method="post" action="submit.php" class="form">

            <!-- Honeypot -->
            <div style="position:absolute; left:-10000px; top:auto; width:1px; height:1px; overflow:hidden;">
              <label>Leave this empty <input type="text" name="website" tabindex="-1" autocomplete="off" /></label>
            </div>

            <fieldset>
              <legend><strong>A. Basic details</strong></legend>

              <p>
                <label for="artist_name"><strong>Artist / Band name</strong></label><br />
                <input id="artist_name" name="artist_name" type="text" required autocomplete="off" />
              </p>

              <p>
                <label for="contact_discord"><strong>Primary contact (Discord)</strong></label><br />
                <input id="contact_discord" name="contact_discord" type="text" required placeholder="example: thesaffen" autocomplete="off" />
              </p>

              <p>
                <label for="genre"><strong>Primary genre / style / tempo</strong></label><br />
                <input id="genre" name="genre" type="text" required placeholder="Examples: metal, folk, tavern songs, orchestral, etc." autocomplete="off" />
              </p>
            </fieldset>

            <fieldset>
              <legend><strong>B. Set length and flexibility</strong></legend>

              <p><strong>Which set lengths are you comfortable performing? (Select all that apply)</strong><br />
                <label><input type="checkbox" name="length_ok[]" value="10-15" /> 10–15 min showcase</label><br />
                <label><input type="checkbox" name="length_ok[]" value="20-30" /> 20–30 min standard</label><br />
                <label><input type="checkbox" name="length_ok[]" value="40-45" /> 40–45 min feature</label><br />
                <label><input type="checkbox" name="length_ok[]" value="60" /> 60 min headliner-level</label>
              </p>

              <p>
                <label for="length_preferred"><strong>Preferred set length (one choice)</strong></label><br />
                <select id="length_preferred" name="length_preferred" required>
                  <option value="" selected disabled>Select one…</option>
                  <option value="10-15">10–15 min showcase</option>
                  <option value="20-30">20–30 min standard</option>
                  <option value="40-45">40–45 min feature</option>
                  <option value="60">60 min headliner-level</option>
                </select>
              </p>

              <p>
                <label for="length_minimum"><strong>Minimum viable set length</strong></label><br />
                <input id="length_minimum" name="length_minimum" type="text" required placeholder="Example: 20 minutes" autocomplete="off" />
              </p>

              <p>
                <label for="short_slot_ok"><strong>If space is limited, would you accept a shorter showcase slot?</strong></label><br />
                <select id="short_slot_ok" name="short_slot_ok" required>
                  <option value="" selected disabled>Select one…</option>
                  <option value="yes">Yes</option>
                  <option value="maybe">Possibly, depending on timing</option>
                  <option value="no">Prefer full-length only</option>
                </select>
              </p>
              <p>
                <label for="performance">Please describe the performance</label><br />
                <textarea id="performance" name="performance" rows="4" placeholder="A short description of your act, tone, and what the audience can expect."></textarea>
              </p>

            </fieldset>

            <fieldset>
              <legend><strong>C. Availability</strong></legend>

              <p><strong>Friday April 17 (20:00–01:00)</strong><br />
                <label><input type="radio" name="avail_fri" value="all" required /> Available all evening</label><br />
                <label><input type="radio" name="avail_fri" value="before_22" /> Available before 22:00</label><br />
                <label><input type="radio" name="avail_fri" value="after_22" /> Available after 22:00</label><br />
                <label><input type="radio" name="avail_fri" value="no" /> Not available</label>
              </p>

              <p><strong>Saturday April 18 (20:00–01:00)</strong><br />
                <label><input type="radio" name="avail_sat" value="all" required /> Available all evening</label><br />
                <label><input type="radio" name="avail_sat" value="before_22" /> Available before 22:00</label><br />
                <label><input type="radio" name="avail_sat" value="after_22" /> Available after 22:00</label><br />
                <label><input type="radio" name="avail_sat" value="no" /> Not available</label>
              </p>

              <p><strong>Sunday April 19 (20:00–23:00)</strong><br />
                <label><input type="radio" name="avail_sun" value="all" required /> Available all evening</label><br />
                <label><input type="radio" name="avail_sun" value="early" /> Only available early (20:00–21:30)</label><br />
                <label><input type="radio" name="avail_sun" value="late" /> Only available late (21:30–23:00)</label><br />
                <label><input type="radio" name="avail_sun" value="no" /> Not available</label>
              </p>
            </fieldset>

            <fieldset>
              <legend><strong>D. Technical and practical notes</strong></legend>

              <p><strong>Do you use musician addon, or watch2gether?</strong><br />
                <label><input type="radio" name="addon" value="musician" required /> Musician</label><br />
                <label><input type="radio" name="addon" value="w2g" /> Watch 2 Gether</label>
              </p>

              <p><strong>Have you performed at Roaring Days before?</strong><br />
                <label><input type="radio" name="performed_before" value="yes" required /> Yes</label><br />
                <label><input type="radio" name="performed_before" value="no" /> No</label>
              </p>
            </fieldset>

            <p>
              <button type="submit">Submit application</button>
            </p>

            <p>
              <small>
                Privacy: Your application details are used only for Roaring Days 9 programming and logistics.
              </small>
            </p>
          </form>

          <hr />

          <h2>What happens next?</h2>
          <ul>
            <li>Applications will be reviewed as we get closer to the event.</li>
            <li>Selected artists will receive a proposed day, time window, and set length for confirmation.</li>
            <li>If we cannot fit everyone, some applicants may be offered a waitlist spot or priority consideration for a future Roaring Days.</li>
          </ul>
        </div>

        <p class="article-footer-note">© The Lion's Roar</p>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="site-footer-inner">
    </div>
  </footer>

</body>
</html>
