-- All users, newest first. Password hashes are never shown.
SELECT u.id,
       u.username,
       u.display_name,
       u.email,
       u.first_name || ' ' || u.last_name AS full_name,
       u.age,
       left(u.address, 40) AS address,
       (u.avatar_path IS NOT NULL) AS avatar,
       count(p.id) AS posts,
       u.token_version AS pw_changes,
       to_char(u.created_at, 'YYYY-MM-DD HH24:MI') AS joined
FROM users u
LEFT JOIN posts p ON p.author_id = u.id
GROUP BY u.id
ORDER BY u.id DESC
LIMIT :limit;
