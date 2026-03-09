<?php
// Set the content type to JSON.
header('Content-Type: application/json');

// --- Basic Security: Only allow POST requests ---
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); // Method Not Allowed
    echo json_encode(['error' => 'Only POST method is accepted.']);
    exit;
}

$stats_file = 'stats.json';
$default_stats = ['gamesPlayed' => 0, 'highScore' => 0];

// --- Read the score from the incoming request ---
$input = json_decode(file_get_contents('php://input'), true);

if (!isset($input['score']) || !is_numeric($input['score'])) {
    http_response_code(400); // Bad Request
    echo json_encode(['error' => 'Invalid or missing score.']);
    exit;
}

$player_score = (int)$input['score'];
$is_new_high_score = false;
$current_stats = $default_stats;

// --- CRITICAL SECTION: Lock the file to prevent race conditions ---
$handle = fopen($stats_file, 'c+'); // 'c+' opens for read/write, creates if not exists

if (flock($handle, LOCK_EX)) { // Get an exclusive lock
    $file_content = fread($handle, filesize($stats_file) ?: 1);
    $stats = json_decode($file_content, true);

    // If file was empty or corrupt, start fresh.
    if (!is_array($stats)) {
        $stats = $default_stats;
    }

    // --- Update the stats ---
    $stats['gamesPlayed'] = ($stats['gamesPlayed'] ?? 0) + 1;
    if ($player_score > ($stats['highScore'] ?? 0)) {
        $stats['highScore'] = $player_score;
        $is_new_high_score = true;
    }

    // --- Write the updated stats back to the file ---
    ftruncate($handle, 0);      // Clear the file content
    rewind($handle);            // Move pointer to the beginning
    fwrite($handle, json_encode($stats, JSON_PRETTY_PRINT));
    fflush($handle);            // Ensure all data is written
    flock($handle, LOCK_UN);    // Release the lock
    
    $current_stats = $stats;
} else {
    // This should rarely happen, but it's good practice to handle it.
    http_response_code(503); // Service Unavailable
    echo json_encode(['error' => 'Could not get a lock on the stats file. Please try again.']);
    fclose($handle);
    exit;
}
fclose($handle);
// --- END CRITICAL SECTION ---


// --- Send back the final response ---
$response = [
    'newStats' => $current_stats,
    'isNewHighScore' => $is_new_high_score
];

echo json_encode($response);
?>