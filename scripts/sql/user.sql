-- One user's full record (minus password hash) and their latest posts.
\x on
SELECT id, username, display_name, email, first_name, last_name, age, address,
       avatar_path, token_version, created_at
FROM users
WHERE username = lower(:'username');
\x off

SELECT p.id, p.body, coalesce(p.image_path, '') AS image,
       to_char(p.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created
FROM posts p
JOIN users u ON u.id = p.author_id
WHERE u.username = lower(:'username')
ORDER BY p.id DESC
LIMIT :limit;
