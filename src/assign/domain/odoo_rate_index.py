from dataclasses import dataclass
from datetime import date

from src.shared.utils.text_normalizer import normalize_text_key

_ACTIVITY_TO_INTRA = {"INTRA": True, "EXTRA": False}


@dataclass(frozen=True)
class OdooRateHit:
    price: int
    rate_id: int
    rate_name: str | None = None
    start_date: date | None = None
    finish_date: date | None = None
    state: str | None = None


def _to_date(value) -> date | None:
    """Odoo devuelve las fechas vacías como False y las demás como 'AAAA-MM-DD'."""
    if not value:
        return None
    return value if isinstance(value, date) else date.fromisoformat(value)


class OdooRateIndex:
    """Índice de precios de líneas `account.base.rate.line` de Odoo.

    Clave: (tarifa, ciudad normalizada, CUP, intra). Los precios <= 0 se ignoran
    y, ante claves duplicadas, gana la primera línea. `rates_info` (opcional)
    aporta nombre y vigencia de cada tarifa (`account.base.rate`).
    """

    def __init__(self, lines: list[dict], rates_info: list[dict] | None = None):
        self._info = {info["rate_id"]: info for info in rates_info or []}
        self._prices: dict[tuple[int, str, str, bool], int] = {}
        for line in lines:
            price = line.get("price") or 0
            if price <= 0:
                continue
            key = (
                line["rate_id"],
                normalize_text_key(line["city"]),
                str(line["cup"]).strip(),
                bool(line["intra"]),
            )
            self._prices.setdefault(key, int(price))

    def lookup(self, rate_id: int | None, city: str, cup: str, activity: str) -> OdooRateHit | None:
        intra = _ACTIVITY_TO_INTRA.get(activity)
        if rate_id is None or intra is None:
            return None
        price = self._prices.get((rate_id, normalize_text_key(city), str(cup).strip(), intra))
        if price is None:
            return None
        info = self._info.get(rate_id, {})
        return OdooRateHit(
            price=price,
            rate_id=rate_id,
            rate_name=info.get("name"),
            start_date=_to_date(info.get("start_date")),
            finish_date=_to_date(info.get("finish_date")),
            state=info.get("state") or None,
        )

    def price(self, rate_id: int | None, city: str, cup: str, activity: str) -> int | None:
        hit = self.lookup(rate_id, city, cup, activity)
        return hit.price if hit else None
