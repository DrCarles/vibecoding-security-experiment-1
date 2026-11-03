-- Latest posts with their authors.
SELECT p.id,
       u.username AS author,
       CASE WHEN char_length(p.body) > 60 THEN left(p.body, 57) || '...' ELSE p.body END AS body,
       char_length(p.body) AS len,
       coalesce(p.image_path, '') AS image,
       to_char(p.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created
FROM posts p
JOIN users u ON u.id = p.author_id
ORDER BY p.id DESC
LIMIT :limit;
