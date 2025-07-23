# app/core/cache.py - Simplified version without Redis
class CacheManager:
    def __init__(self):
        self.memory_cache = {}
        self.use_redis = False
    
    async def connect(self):
        """Initialize cache connection"""
        pass
    
    async def get(self, key: str):
        """Get value from cache"""
        return self.memory_cache.get(key)
    
    async def set(self, key: str, value: str, expire: int = 3600):
        """Set value in cache"""
        self.memory_cache[key] = value
    
    async def delete(self, key: str):
        """Delete key from cache"""
        self.memory_cache.pop(key, None)
    
    async def delete_pattern(self, pattern: str):
        """Delete keys matching pattern"""
        keys_to_delete = [k for k in self.memory_cache.keys() if pattern.replace('*', '') in k]
        for key in keys_to_delete:
            del self.memory_cache[key]

cache_manager = CacheManager()

