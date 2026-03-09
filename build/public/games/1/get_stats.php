<?php
// Set the content type to JSON so the browser understands the response.
header('Content-Type: application/json');

$stats_file = 'stats.json';
$default_stats = ['gamesPlayed' => 0, 'highScore' => 0];

// If the stats file doesn't exist, create it with default values.
if (!file_exists($stats_file)) {
    // The JSON_PRETTY_PRINT makes the file human-readable.
    file_put_contents($stats_file, json_encode($default_stats, JSON_PRETTY_PRINT));
}

// Read the contents of the file and send it to the client.
echo file_get_contents($stats_file);
?>