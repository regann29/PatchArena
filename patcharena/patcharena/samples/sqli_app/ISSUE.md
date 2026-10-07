SQL injection in get_user

Looking up a user with the name x' OR '1'='1 returns every row in the users table instead of nothing. The query is built with string formatting.
