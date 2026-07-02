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

    def find_any_rate(self, keys):
        result = {}
        for city_id, cup_id, activity_id in keys:
            for (rid, cid, cuid, aid, rtype), rate in self._data.items():
                if cid == city_id and cuid == cup_id and aid == activity_id:
                    result[(city_id, cup_id, activity_id)] = (rate, rtype, rid)
                    break
        return result

    def find_rate_by_cup_activity(self, keys):
        result = {}
        for cup_id, activity_id in keys:
            for (rid, cid, cuid, aid, rtype), rate in self._data.items():
                if cuid == cup_id and aid == activity_id:
                    result[(cup_id, activity_id)] = (rate, rtype, rid)
                    break
        return result
