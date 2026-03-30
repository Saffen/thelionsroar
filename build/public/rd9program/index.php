<?php
// Change this to the URL you want to redirect to
$target_url = "https://docs.google.com/spreadsheets/d/17E_qGDQouE0DEr6rjIG-zMKH-mxDAsLVebYe9BG5vdo/edit?usp=sharing/";

// Perform the redirect
header("Location: $target_url");
exit();
?>
