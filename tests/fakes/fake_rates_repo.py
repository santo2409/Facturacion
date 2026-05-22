class FakeRatesRepo:
    def __init__(self):
        self._data = {}

    def save_batch(self, rates):
        for r in rates:
            key = (r.rateable_id, r.city_id, r.cup_id, r.activity_id, r.rateable_type)
            self._data[key] = r.rate
        return len(rates)

    def find_by_name(self, rate):
        key = (rate.rateable_id, rate.city_id, rate.cup_id, rate.activity_id, rate.rateable_type)
        val = self._data.get(key)
        if val is None:
            return None
        return (rate.rateable_id, rate.city_id, rate.cup_id, val, rate.activity_id, rate.rateable_type)

    def find_batch(self, keys):
        result = {}
        for k in keys:
            if k in self._data:
                result[k] = self._data[k]
        return result
