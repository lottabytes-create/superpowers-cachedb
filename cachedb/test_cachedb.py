from cacheDB import CacheDB


def test_new_cache_instance():
    db = CacheDB()
    assert isinstance(db, CacheDB)
