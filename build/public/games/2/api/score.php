<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');

const DB_PATH = __DIR__ . DIRECTORY_SEPARATOR . 'leaderboard.sqlite';
const INIT_SQL = __DIR__ . DIRECTORY_SEPARATOR . 'init.sql';
const MAX_RESULTS = 10;

try {
    $db = open_database();

    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
    if ($method === 'GET') {
        respond([
            'success' => true,
            'scores' => fetch_scores($db),
        ]);
    }

    if ($method === 'POST') {
        $payload = read_payload();
        $name = sanitize_name((string)($payload['playerName'] ?? ''));
        $score = filter_var($payload['score'] ?? null, FILTER_VALIDATE_INT, ['options' => ['min_range' => 0]]);
        $survival = filter_var($payload['survivalSeconds'] ?? null, FILTER_VALIDATE_FLOAT);

        if ($name === '') {
            error_response('Name must be 2 to 20 safe characters.', 422);
        }

        if ($score === false) {
            error_response('Score must be a non-negative integer.', 422);
        }

        if ($survival === false || $survival < 0 || $survival > 86400) {
            error_response('Survival time is invalid.', 422);
        }

        $statement = $db->prepare(
            'INSERT INTO scores (player_name, score, survival_seconds, created_at) VALUES (:player_name, :score, :survival_seconds, :created_at)'
        );
        $statement->bindValue(':player_name', $name, SQLITE3_TEXT);
        $statement->bindValue(':score', (int)$score, SQLITE3_INTEGER);
        $statement->bindValue(':survival_seconds', round((float)$survival, 1), SQLITE3_FLOAT);
        $statement->bindValue(':created_at', gmdate('c'), SQLITE3_TEXT);

        if (!$statement->execute()) {
            throw new RuntimeException('Unable to save score entry.');
        }

        respond([
            'success' => true,
            'scores' => fetch_scores($db),
        ], 201);
    }

    error_response('Method not allowed.', 405);
} catch (Throwable $exception) {
    error_response('Server error: ' . $exception->getMessage(), 500);
}

function open_database(): SQLite3
{
    if (!is_dir(__DIR__)) {
        throw new RuntimeException('API directory missing.');
    }

    $db = new SQLite3(DB_PATH);
    $db->enableExceptions(true);
    $db->exec('PRAGMA journal_mode = WAL');
    $db->exec('PRAGMA busy_timeout = 5000');
    $db->exec('PRAGMA foreign_keys = ON');

    if (!file_exists(INIT_SQL)) {
        throw new RuntimeException('Missing init.sql schema file.');
    }

    $schema = file_get_contents(INIT_SQL);
    if ($schema === false) {
        throw new RuntimeException('Unable to read init.sql schema file.');
    }

    $db->exec($schema);

    return $db;
}

function read_payload(): array
{
    $contentType = $_SERVER['CONTENT_TYPE'] ?? '';
    if (stripos($contentType, 'application/json') !== false) {
        $raw = file_get_contents('php://input');
        if ($raw === false || $raw === '') {
            return [];
        }

        $decoded = json_decode($raw, true);
        if (!is_array($decoded)) {
            error_response('Malformed JSON payload.', 400);
        }

        return $decoded;
    }

    return $_POST;
}

function sanitize_name(string $name): string
{
    $name = trim($name);
    $name = preg_replace('/[^A-Za-z0-9 _\-\.]/', '', $name) ?? '';
    $name = preg_replace('/\s+/', ' ', $name) ?? '';

    if ($name === '') {
        return '';
    }

    $length = strlen($name);
    if ($length < 2 || $length > 20) {
        return '';
    }

    return $name;
}

function fetch_scores(SQLite3 $db): array
{
    $statement = $db->prepare(
        'SELECT player_name, score, survival_seconds, created_at
         FROM scores
         ORDER BY score DESC, survival_seconds DESC, created_at ASC
         LIMIT :limit'
    );
    $statement->bindValue(':limit', MAX_RESULTS, SQLITE3_INTEGER);
    $result = $statement->execute();

    $scores = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $scores[] = [
            'playerName' => (string)$row['player_name'],
            'score' => (int)$row['score'],
            'survivalSeconds' => round((float)$row['survival_seconds'], 1),
            'createdAt' => (string)$row['created_at'],
        ];
    }

    return $scores;
}

function respond(array $payload, int $status = 200): never
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function error_response(string $message, int $status): never
{
    respond([
        'success' => false,
        'error' => $message,
    ], $status);
}
