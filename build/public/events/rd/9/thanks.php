<?php
declare(strict_types=1);

// Adjust if your stylesheet path differs
$SITE_TITLE = "Application received | Roaring Days 9";
$CSS_HREF   = "/assets/css/style.css";
$LOGO_HREF  = "/logo.svg";
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title><?= htmlspecialchars($SITE_TITLE) ?></title>

  <link rel="stylesheet" href="<?= htmlspecialchars($CSS_HREF) ?>" />
  <link rel="icon" href="/favicon.ico" />
</head>

<body>
  <header class="site-header">
    <div class="site-header-inner">
      <a class="site-brand" href="/">
        <img src="<?= htmlspecialchars($LOGO_HREF) ?>" alt="The Lion's Roar" style="height:56px; width:auto;" />
      </a>
    </div>
  </header>

  <main>
    <section class="article-grid" style="padding-top:20px;">
      <div>
        <h1>Application received</h1>
        <p class="article-teaser">
          Thank you. Your Roaring Days 9 artist application has been recorded.
        </p>

        <div class="article-content">
          <p>
            If you need to correct anything, contact Hardhy on Discord and include your artist name.
          </p>

          <p>
            <a href="signup.php">Back to the application page</a>
          </p>
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
