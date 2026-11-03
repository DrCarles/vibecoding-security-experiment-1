-- Data-quality checks. Every row in the result should show problems = 0.
SELECT check_name, problems FROM (
  SELECT 1 AS ord, 'posts with no text and no image' AS check_name,
         count(*) AS problems FROM posts WHERE body = '' AND image_path IS NULL
  UNION ALL
  SELECT 2, 'posts longer than 280 characters',
         count(*) FROM posts WHERE char_length(body) > 280
  UNION ALL
  SELECT 3, 'posts with leading/trailing whitespace',
         count(*) FROM posts WHERE body <> btrim(body)
  UNION ALL
  SELECT 4, 'posts whose author is missing',
         count(*) FROM posts p LEFT JOIN users u ON u.id = p.author_id WHERE u.id IS NULL
  UNION ALL
  SELECT 5, 'posts dated in the future',
         count(*) FROM posts WHERE created_at > now() + interval '1 minute'
  UNION ALL
  SELECT 6, 'users with age outside 13-130',
         count(*) FROM users WHERE age NOT BETWEEN 13 AND 130
  UNION ALL
  SELECT 7, 'usernames not lowercase or invalid',
         count(*) FROM users WHERE username !~ '^[a-z0-9_]{3,30}$'
  UNION ALL
  SELECT 8, 'emails not lowercase',
         count(*) FROM users WHERE email <> lower(email)
  UNION ALL
  SELECT 9, 'blank display names',
         count(*) FROM users WHERE btrim(display_name) = ''
  UNION ALL
  SELECT 10, 'passwords not hashed with argon2',
         count(*) FROM users WHERE password_hash NOT LIKE '$argon2%'
  UNION ALL
  SELECT 11, 'image paths outside posts/ folder',
         count(*) FROM posts WHERE image_path IS NOT NULL AND image_path !~ '^posts/[0-9a-f]{32}\.webp$'
  UNION ALL
  SELECT 12, 'avatar paths outside avatars/ folder',
         count(*) FROM users WHERE avatar_path IS NOT NULL AND avatar_path !~ '^avatars/[0-9a-f]{32}\.webp$'
) checks
ORDER BY ord;
