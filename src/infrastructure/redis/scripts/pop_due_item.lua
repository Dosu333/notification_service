local items = redis.call('zrangebyscore', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
if #items > 0 then
    redis.call('zrem', KEYS[1], items[1])
    return items[1]
end
return nil
