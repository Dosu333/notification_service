-- KEYS[1]: Redis Key (e.g., rate_limit:ip:192.168.1.1)
-- ARGV[1]: Current timestamp (now)
-- ARGV[2]: Window size in seconds (e.g., 60)
-- ARGV[3]: Max limit (e.g., 100)
-- ARGV[4]: Unique random value (to prevent ZSET collisions)

-- Remove timestamps older than the sliding window
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, tonumber(ARGV[1]) - tonumber(ARGV[2]))

-- Count remaining timestamps in the window
local count = redis.call('ZCARD', KEYS[1])

-- If under limit, add the new request and extend TTL
if count < tonumber(ARGV[3]) then
    redis.call('ZADD', KEYS[1], ARGV[1], ARGV[1] .. '-' .. ARGV[4])
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
    return {1, tonumber(ARGV[3]) - count - 1}
end

-- Rate limit exceeded
return {0, 0}