from dataclasses import dataclass


@dataclass
class Rate:
    rateable_id: int
    city_id: int
    cup_id: int
    rate: int
    activity_id: int
    rateable_type: str
