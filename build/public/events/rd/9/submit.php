<?php
declare(strict_types=1);

// =========================
// CONFIG
// =========================
$storageDir = __DIR__ . "/rd9-submissions";  // will save JSON files here

// Optional Discord webhook relay (leave empty to disable)
$discordWebhookUrl = ""; // e.g. "https://discord.com/api/webhooks/...."

// Honeypot field name (must match the form)
$honeypotFieldName = "website";

// =========================
// HELPERS
// =========================
function ensure_dir(string $dir): void {
  if (!is_dir($dir)) mkdir($dir, 0755, true);
}

function fail(string $msg, int $code = 400): void {
  http_response_code($code);
  header("Content-Type: text/html; charset=utf-8");
  echo "<h1>Submission failed</h1><p>" . htmlspecialchars($msg) . "</p>";
  echo '<p><a href="./">Go back</a></p>';
  exit;
}

function post_str(string $key, int $maxLen = 5000): string {
  $v = $_POST[$key] ?? "";
  if (is_array($v)) return "";
  $v = trim((string)$v);
  if (mb_strlen($v) > $maxLen) $v = mb_substr($v, 0, $maxLen);
  return $v;
}

function post_arr(string $key, int $maxItems = 10): array {
  $v = $_POST[$key] ?? [];
  if (!is_array($v)) return [];
  $out = [];
  foreach ($v as $item) {
    if (count($out) >= $maxItems) break;
    $s = trim((string)$item);
    if ($s !== "") $out[] = mb_substr($s, 0, 50);
  }
  return $out;
}

function discord_send(string $webhookUrl, array $payload): void {
  $ch = curl_init($webhookUrl);
  curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => ["Content-Type: application/json"],
    CURLOPT_POSTFIELDS => json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 8,
  ]);
  curl_exec($ch);
  curl_close($ch);
}

// =========================
// MAIN
// =========================
if ($_SERVER["REQUEST_METHOD"] !== "POST") {
  fail("Invalid request method.", 405);
}

// Honeypot check
if (post_str($honeypotFieldName) !== "") {
  fail("Spam detected.");
}

// Read fields (matching your form)
$artist_name      = post_str("artist_name", 200);
$contact_discord  = post_str("contact_discord", 200);
$genre            = post_str("genre", 250);

$length_ok        = post_arr("length_ok"); // checkbox name="length_ok[]"
$length_preferred = post_str("length_preferred", 20);
$length_minimum   = post_str("length_minimum", 50);
$short_slot_ok    = post_str("short_slot_ok", 20);

$performance      = post_str("performance", 4000);

$avail_fri        = post_str("avail_fri", 20);
$avail_sat        = post_str("avail_sat", 20);
$avail_sun        = post_str("avail_sun", 20);

$addon            = post_str("addon", 20);
$performed_before = post_str("performed_before", 10);

// Validate required fields (based on your HTML required attributes)
if ($artist_name === "" || $contact_discord === "" || $genre === "") {
  fail("Missing required fields (artist name, contact, or genre).");
}
if ($length_preferred === "" || $length_minimum === "" || $short_slot_ok === "") {
  fail("Missing required set length fields.");
}
if ($avail_fri === "" || $avail_sat === "" || $avail_sun === "") {
  fail("Missing availability selection.");
}
if ($addon === "" || $performed_before === "") {
  fail("Missing technical selection fields.");
}

// Optional: restrict allowed values lightly (keeps your data clean)
$allowed_avail_fri = ["all","before_22","after_22","no"];
$allowed_avail_sat = ["all","before_22","after_22","no"];
$allowed_avail_sun = ["all","early","late","no"];
$allowed_short     = ["yes","maybe","no"];
$allowed_addon     = ["musician","w2g"];
$allowed_before    = ["yes","no"];

if (!in_array($avail_fri, $allowed_avail_fri, true)) fail("Invalid Friday availability value.");
if (!in_array($avail_sat, $allowed_avail_sat, true)) fail("Invalid Saturday availability value.");
if (!in_array($avail_sun, $allowed_avail_sun, true)) fail("Invalid Sunday availability value.");
if (!in_array($short_slot_ok, $allowed_short, true)) fail("Invalid showcase flexibility value.");
if (!in_array($addon, $allowed_addon, true)) fail("Invalid addon value.");
if (!in_array($performed_before, $allowed_before, true)) fail("Invalid performed-before value.");

ensure_dir($storageDir);

// Build submission object
$submission = [
  "timestamp_utc" => gmdate("c"),
  "ip"            => $_SERVER["REMOTE_ADDR"] ?? "",
  "artist_name"   => $artist_name,
  "contact_discord" => $contact_discord,
  "genre"         => $genre,

  "set_lengths_ok"  => $length_ok,
  "set_length_preferred" => $length_preferred,
  "set_length_minimum"   => $length_minimum,
  "accept_short_showcase" => $short_slot_ok,

  "performance_description" => $performance,

  "availability" => [
    "fri" => $avail_fri,
    "sat" => $avail_sat,
    "sun" => $avail_sun,
  ],

  "playback_method"   => $addon,            // musician | w2g
  "performed_before"  => $performed_before, // yes | no
];

// Save JSON
$slug = preg_replace("/[^a-zA-Z0-9_-]+/", "-", strtolower($artist_name));
$slug = trim($slug, "-");
if ($slug === "") $slug = "artist";

$filename = $storageDir . "/" . gmdate("Ymd_His") . "_" . $slug . ".json";
file_put_contents($filename, json_encode($submission, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

// Optional Discord ping
if ($discordWebhookUrl !== "") {
  $content =
    "**New RD9 Artist Application**\n" .
    "**Artist:** {$artist_name}\n" .
    "**Contact:** {$contact_discord}\n" .
    "**Genre:** {$genre}\n" .
    "**Preferred:** {$length_preferred} (min: {$length_minimum}, showcase: {$short_slot_ok})\n" .
    "**Availability:** Fri {$avail_fri} | Sat {$avail_sat} | Sun {$avail_sun}\n" .
    "**Method:** {$addon}\n" .
    "**Performed before:** {$performed_before}\n\n" .
    "**Description:** " . ($performance !== "" ? $performance : "(none provided)");

  discord_send($discordWebhookUrl, ["content" => mb_substr($content, 0, 1900)]);
}

// Redirect to thanks page (create thanks.php, or change this)
header("Location: thanks.php", true, 303);
exit;
