# database/models/route.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Route:
    id: str
    tg_id: int
    points: str = field(default="0")
    status: str = field(default="new")
    number_auto: str = field(default="")
    temperature: str = field(default="")
    dispatcher_contacts: str = field(default="")
    # Номер для регистрации и номер прицепа (формат 1С и ручной ввод)
    registration_number: str = field(default="")
    trailer_number: str = field(default="")

    @classmethod
    def from_row(cls, row) -> 'Route':
        keys = set(row.keys())
        def _get(key: str, default: str = "") -> str:
            if key not in keys or row[key] is None:
                return default
            v = row[key]
            return str(v).strip() if v else default
        return cls(
            id=str(row['id']),
            tg_id=int(row['tg_id']),
            points=row['points'],
            status=row['status'],
            number_auto=_get('number_auto'),
            temperature=_get('temperature'),
            dispatcher_contacts=_get('dispatcher_contacts'),
            registration_number=_get('registration_number'),
            trailer_number=_get('trailer_number'),
        )

@dataclass
class Point:
    id: int
    id_route: str
    type_point: str
    place_point: str
    date_point: str
    time_accepted: Optional[str] = field(default=None)
    time_departure: Optional[str] = field(default=None)
    time_registration: Optional[str] = field(default=None)
    time_put_on_gate: Optional[str] = field(default=None)
    time_docs: Optional[str] = field(default=None)
    photo_docs: Optional[str] = field(default=None)
    status: str = field(default="new")
    lat: Optional[float] = field(default=None)
    lng: Optional[float] = field(default=None)
    odometer: Optional[str] = field(default=None)
    
    @classmethod
    def from_row(cls, row) -> 'Point':
        keys = row.keys() if hasattr(row, 'keys') else []
        def _get(key: str):
            if key not in keys:
                return None
            v = row[key]
            if v is None or v == '' or v == '0':
                return None
            return str(v).strip()
        def _get_float(key):
            if key not in keys or row[key] is None:
                return None
            try:
                return float(row[key])
            except (TypeError, ValueError):
                return None
        return cls(
            id=int(row['id']),
            id_route=str(row['id_route']),
            type_point=str(row['type_point']),
            place_point=str(row['place_point']),
            date_point=str(row['date_point']),
            time_accepted=_get('time_accepted'),
            time_departure=_get('time_departure'),
            time_registration=_get('time_registration'),
            time_put_on_gate=_get('time_put_on_gate'),
            time_docs=_get('time_docs'),
            photo_docs=row['photo_docs'] if 'photo_docs' in keys else None,
            status=str(row['status']),
            lat=_get_float('lat') if 'lat' in keys else None,
            lng=_get_float('lng') if 'lng' in keys else None,
            odometer=_get('odometer') if 'odometer' in keys else None,
        )