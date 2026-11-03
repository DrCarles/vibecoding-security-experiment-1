-- Overview: row counts, activity and storage.
\echo '== Counts =='
SELECT
  (SELECT count(*) FROM users)                                  AS users,
  (SELECT count(*) FROM users WHERE avatar_path IS NOT NULL)    AS users_with_avatar,
  (SELECT count(*) FROM posts)                                  AS posts,
  (SELECT count(*) FROM posts WHERE image_path IS NOT NULL)     AS posts_with_image,
  (SELECT count(*) FROM posts WHERE created_at > now() - interval '24 hours') AS posts_last_24h;

\echo '== Activity =='
SELECT
  (SELECT max(created_at) FROM users) AS last_signup,
  (SELECT max(created_at) FROM posts) AS last_post,
  (SELECT round(avg(char_length(body)), 1) FROM posts WHERE body <> '') AS avg_post_length;

\echo '== Most active users =='
SELECT u.username, u.display_name, count(p.id) AS posts
FROM users u LEFT JOIN posts p ON p.author_id = u.id
GROUP BY u.id
ORDER BY posts DESC, u.username
LIMIT 5;

\echo '== Storage =='
SELECT relname AS table,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       n_live_tup AS approx_rows
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size,
       (SELECT version_num FROM alembic_version) AS migration;
